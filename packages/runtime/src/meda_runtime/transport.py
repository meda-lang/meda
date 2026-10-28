"""Bounded HTTPS JSON/JSON-RPC transport for the evidence-to-report profile.

No redirects, proxy environment, implicit retries, or relaxed TLS verification.
This is deliberately independent of the SDK-based reference peers.
"""
from __future__ import annotations

import base64
import http.client
import json
import re
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from urllib.parse import urlsplit


class TransportError(Exception):
    def __init__(self, code: str, *, dispatched: bool = False, received: int = 0):
        super().__init__(code)
        self.code, self.dispatched, self.received = code, dispatched, received


@dataclass(frozen=True)
class Response:
    status: int
    value: object
    received: int
    notifications: int = 0


def encode_header(value: str) -> str:
    """MCP printable ASCII, preserving edge whitespace and sentinel-shaped data."""
    if (value and all(32 <= ord(c) <= 126 for c in value)
            and value == value.strip() and not re.fullmatch(r"=\?base64\?.*\?=", value)):
        return value
    return "=?base64?" + base64.b64encode(value.encode()).decode("ascii") + "?="


def decode_json(raw: bytes, max_depth: int = 16) -> object:
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        stack = [(value, 0)]
        while stack:
            item, depth = stack.pop()
            if depth > max_depth:
                raise TransportError("ResponseLimit")
            if isinstance(item, dict):
                stack.extend((v, depth + 1) for v in item.values())
            elif isinstance(item, list):
                stack.extend((v, depth + 1) for v in item)
        return value
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise TransportError("ProtocolRejected") from exc


class _OwnedHTTPSConnection(http.client.HTTPSConnection):
    def connect(self):
        # stdlib's HTTPSConnection assigns its SSLSocket only after the
        # handshake. Expose it first so root cancellation can interrupt TLS.
        http.client.HTTPConnection.connect(self)
        self.check_connection()
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host,
                                             do_handshake_on_connect=False)
        self.check_connection()
        self.sock.do_handshake()


class HTTPSTransport:
    def __init__(self, ca_file: str, *, clock=time.monotonic):
        self.context = ssl.create_default_context(cafile=ca_file)
        self.clock = clock
        self._active_lock = threading.Lock()
        self._active = set()

    def cancel_active(self):
        """Interrupt currently owned sockets; later cleanup requests stay usable."""
        with self._active_lock:
            for interrupt in tuple(self._active):
                interrupt()

    def request(self, method: str, url: str, headers: dict, body: bytes | None,
                *, deadline: float, max_bytes: int, max_depth: int,
                max_events: int, max_event_bytes: int, request_id=None,
                progress_token=None, check_live=None, on_dispatch=None) -> Response:
        target = urlsplit(url)
        if target.scheme != "https" or not target.hostname or target.username or target.password or target.fragment:
            raise TransportError("AuthorityDenied")
        conn = _OwnedHTTPSConnection(target.hostname, target.port or 443,
                                    context=self.context,
                                    timeout=max(.001, deadline - self.clock()))
        dispatched = False
        received = 0
        notifications = 0
        cancelled, expired = threading.Event(), threading.Event()
        owned_socket = None

        def interrupt(*, timeout=False):
            (expired if timeout else cancelled).set()
            # getresponse may detach conn.sock when Connection: close is used.
            # Retain the socket so its response file is still interruptible.
            sock = owned_socket or conn.sock
            if sock is not None:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

        timer = threading.Timer(max(0, deadline - self.clock()), lambda: interrupt(timeout=True))
        timer.daemon = True

        def tick():
            if check_live is not None:
                check_live()
            if cancelled.is_set():
                raise TransportError("RootTerminated", dispatched=dispatched, received=received)
            left = deadline - self.clock()
            if left <= 0 or expired.is_set():
                raise TransportError("Timeout", dispatched=dispatched, received=received)
            if conn.sock:
                conn.sock.settimeout(left)

        conn.check_connection = tick

        try:
            with self._active_lock:
                self._active.add(interrupt)
            timer.start()
            tick()
            conn.connect()
            owned_socket = conn.sock
            tick()
            dispatched = True  # Conservatively charged before transmission starts.
            if on_dispatch is not None:
                on_dispatch()
            path = target.path or "/"
            if target.query:
                path += "?" + target.query
            conn.request(method, path, body=body, headers=headers)
            tick()
            response = conn.getresponse()
            tick()
            if 300 <= response.status < 400:
                raise TransportError("AuthorityDenied", dispatched=True)
            content_type = response.getheader("Content-Type", "").split(";", 1)[0].lower().strip()
            content_length = response.getheader("Content-Length")
            if content_length is not None:
                try:
                    if int(content_length) < 0 or int(content_length) > max_bytes:
                        raise TransportError("ResponseLimit", dispatched=True)
                except ValueError as exc:
                    raise TransportError("ProtocolRejected", dispatched=True) from exc
            if response.status in (401, 403):
                return Response(response.status, None, 0)
            if content_type not in ("application/json", "text/event-stream"):
                raise TransportError("ProtocolRejected", dispatched=True)
            is_sse = content_type == "text/event-stream"
            if is_sse and (method != "POST" or request_id is None):
                raise TransportError("ProtocolRejected", dispatched=True)
            chunks = bytearray()
            line_buffer = bytearray()
            event_lines = []
            event_size = 0
            event_count = 0
            first_line = True
            skip_leading_lf = False

            def event():
                nonlocal event_count, event_lines, event_size, notifications
                if not event_lines:
                    event_size = 0
                    return None
                event_count += 1
                if event_count > max_events:
                    raise TransportError("ResponseLimit")
                raw = b"\n".join(event_lines)
                event_lines, event_size = [], 0
                value = decode_json(raw, max_depth)
                if not isinstance(value, dict) or value.get("jsonrpc") != "2.0":
                    raise TransportError("ProtocolRejected")
                if "id" in value:
                    if value["id"] != request_id or type(value["id"]) is not type(request_id):
                        raise TransportError("ProtocolRejected")
                    return value
                if value.get("method") not in ("notifications/progress", "notifications/message"):
                    raise TransportError("ProtocolRejected")
                params = value.get("params", {})
                if not isinstance(params, dict):
                    raise TransportError("ProtocolRejected")
                if value["method"] == "notifications/progress" and params.get("progressToken") != progress_token:
                    raise TransportError("ProtocolRejected")
                notifications += 1
                return None

            while True:
                tick()
                data = response.read1(min(4096, max_bytes - received + 1))
                if not data:
                    break
                received += len(data)
                if received > max_bytes:
                    raise TransportError("ResponseLimit")
                if not is_sse:
                    chunks.extend(data)
                    continue
                line_buffer.extend(data)
                if skip_leading_lf:
                    if line_buffer.startswith(b"\n"):
                        del line_buffer[:1]
                    skip_leading_lf = False
                if len(line_buffer) + event_size > max_event_bytes and b"\n" not in line_buffer:
                    raise TransportError("ResponseLimit")
                while b"\n" in line_buffer or b"\r" in line_buffer:
                    separators = [i for i in (line_buffer.find(b"\n"), line_buffer.find(b"\r")) if i >= 0]
                    end_line = min(separators)
                    line = bytes(line_buffer[:end_line])
                    skip = 2 if line_buffer[end_line:end_line+2] == b"\r\n" else 1
                    skip_leading_lf = line_buffer[end_line:] == b"\r"
                    del line_buffer[:end_line + skip]
                    if first_line:
                        line = line.removeprefix(b"\xef\xbb\xbf")
                        first_line = False
                    event_size += len(line) + 1
                    if event_size > max_event_bytes:
                        raise TransportError("ResponseLimit")
                    if not line:
                        value = event()
                        if value is not None:
                            tick()
                            return Response(response.status, value, received, notifications)
                    elif line.startswith(b"data:"):
                        event_lines.append(bytes(line[5:]).removeprefix(b" "))
                    elif line.startswith(b":") or line.startswith((b"event:", b"id:", b"retry:")):
                        continue
                    else:
                        # SSE unknown fields are ignored by the standard event parser.
                        continue
            tick()
            if is_sse:
                raise TransportError("TransportFailure")  # EOF without final response.
            if content_length is not None and received != int(content_length):
                raise TransportError("TransportFailure")  # read1 permits truncated EOF.
            return Response(response.status, decode_json(bytes(chunks), max_depth), received)
        except TransportError as exc:
            exc.dispatched = exc.dispatched or dispatched
            exc.received = max(exc.received, received)
            raise
        except (socket.timeout, TimeoutError) as exc:
            raise TransportError("Timeout", dispatched=dispatched, received=received) from exc
        except (OSError, http.client.HTTPException, UnicodeError, ValueError) as exc:
            code = "Timeout" if expired.is_set() else "RootTerminated" if cancelled.is_set() else "TransportFailure"
            raise TransportError(code, dispatched=dispatched, received=received) from exc
        finally:
            timer.cancel()
            timer.join()
            with self._active_lock:
                self._active.discard(interrupt)
            conn.close()
