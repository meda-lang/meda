"""Bounded, local TLS fault injection around the real upstream SDK peers.

The proxy never dispatches a replacement business implementation. It forwards the
original request body and authorization to the configured loopback SDK process,
reads its response, then changes the response bytes. Live progress/cancellation
cases instead forward the real SDK stream incrementally without mutation. A
complete SDK response is an independent wire witness; task commitment must also
be checked in the peer ledger. This is not a general purpose HTTP proxy.
"""
from __future__ import annotations

import contextlib
import copy
import http.client
import http.server
import json
import socket
import ssl
import threading
import time


MAX_REQUEST = 65_536
MAX_UPSTREAM = 1_048_576
MAX_EVENTS = 512
IO_SECONDS = 5
HOP_HEADERS = frozenset({"connection", "keep-alive", "proxy-authenticate",
    "proxy-authorization", "te", "trailer", "transfer-encoding", "upgrade"})
METHODS = {"tools/list": "discover", "server/discover": "discover",
           "tools/call": "readEvidence", "GetTask": "observe",
           "CancelTask": "cancel", "SendMessage": "submit"}


def _json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def _sse(value):
    return b"event: message\ndata: " + _json(value) + b"\n\n"


class _Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    request_queue_size = 4

    def get_request(self):
        raw, address = super().get_request()
        raw.settimeout(1)
        try:
            connection = self.proxy.server_context.wrap_socket(raw, server_side=True)
        except BaseException:
            raw.close()
            raise
        connection.settimeout(IO_SECONDS)
        with self.proxy._lock:
            self.proxy._sockets.add(connection)
        return connection, address

    def process_request(self, request, client_address):
        if not self.proxy._slots.acquire(blocking=False):
            self.proxy._event("connection_rejected", reason="concurrency")
            self.shutdown_request(request)
            with self.proxy._lock:
                self.proxy._sockets.discard(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.proxy._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            with self.proxy._lock:
                self.proxy._sockets.discard(request)
            self.proxy._slots.release()

    def handle_error(self, request, client_address):
        # No exception text, headers, body, URL or credential can enter logs.
        self.proxy._event("handler_error")


class FaultProxy:
    """One fixed upstream, one inventory scenario, separate safe witness list.

    ``response_ready`` / ``release_response`` coordinate the observation race.
    ``stream_started`` witnesses the first delivered live SDK stream bytes. All gates
    have finite waits and are released during shutdown. ``serve`` yields self.
    """

    def __init__(self, protocol, port, upstream_port, certificates, scenario):
        if protocol not in ("mcp", "a2a"):
            raise ValueError("unsupported proxy protocol")
        for value in (port, upstream_port):
            if type(value) is not int or not 1 <= value <= 65535:
                raise ValueError("invalid local port")
        if port == upstream_port or not isinstance(scenario, dict):
            raise ValueError("invalid proxy configuration")
        self.protocol, self.port, self.upstream_port = protocol, port, upstream_port
        self.scenario = copy.deepcopy(scenario)
        self.events = []
        self._lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(4)
        self._sockets = set()
        self._upstreams = set()
        self._responses = set()
        self._counter = 0
        self._pages = 0
        self._stop = threading.Event()
        self.response_ready = threading.Event()
        self.release_response = threading.Event()
        self.stream_started = threading.Event()
        self.upstream_context = ssl.create_default_context(cafile=certificates["ca_file"])
        self.server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.server_context.minimum_version = ssl.TLSVersion.TLSv1_2
        self.server_context.load_cert_chain(certificates["cert_file"], certificates["key_file"])

    def _event(self, event, **fields):
        with self._lock:
            if len(self.events) < MAX_EVENTS - 1:
                self.events.append({"sequence": len(self.events), "protocol": self.protocol,
                                    "event": event, **fields})
            elif len(self.events) == MAX_EVENTS - 1:
                self.events.append({"sequence": len(self.events), "protocol": self.protocol,
                                    "event": "witness_limit"})

    @contextlib.contextmanager
    def serve(self):
        if self._stop.is_set():
            raise RuntimeError("a proxy instance serves once")
        proxy = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            server_version = "D0FaultProxy"

            def log_message(self, format, *args):
                pass

            def do_GET(self):
                proxy._handle(self)

            def do_POST(self):
                proxy._handle(self)

        server = _Server(("127.0.0.1", self.port), Handler)
        server.proxy = self
        thread = threading.Thread(target=server.serve_forever,
                                  kwargs={"poll_interval": .05}, daemon=True)
        thread.start()
        try:
            yield self
        finally:
            self._stop.set()
            self.release_response.set()
            with self._lock:
                sockets, upstreams = list(self._sockets), list(self._upstreams)
                responses = list(self._responses)
            for connection in upstreams:
                if connection.sock:
                    with contextlib.suppress(OSError):
                        connection.sock.shutdown(socket.SHUT_RDWR)
                connection.close()
            for response in responses:
                response.close()
            for connection in sockets:
                with contextlib.suppress(OSError):
                    connection.shutdown(socket.SHUT_RDWR)
                connection.close()
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            self._event("proxy_stopped", serverThreadRetired=not thread.is_alive())

    def _handle(self, handler):
        handler.close_connection = True
        request = 0
        operation = "unknown"
        try:
            expected_path = "/mcp" if self.protocol == "mcp" else "/a2a"
            is_card = self.protocol == "a2a" and handler.path == "/.well-known/agent-card.json"
            if handler.path != expected_path and not is_card:
                self._reply(handler, 404, [], b"{}")
                return
            lengths = handler.headers.get_all("Content-Length", [])
            if (len(lengths) > 1 or handler.headers.get("Transfer-Encoding")
                    or (lengths and not lengths[0].isdigit())):
                self._reply(handler, 400, [], b"{}")
                return
            length = int(lengths[0]) if lengths else 0
            if length > MAX_REQUEST:
                self._reply(handler, 413, [], b"{}")
                return
            raw = handler.rfile.read(length)
            if len(raw) != length:
                return
            payload = {}
            try:
                candidate = json.loads(raw) if raw else {}
                if isinstance(candidate, dict):
                    payload = candidate
            except (ValueError, UnicodeError, RecursionError):
                pass  # The unchanged bytes still reach the SDK parser.
            method = payload.get("method")
            operation = "discover" if is_card else METHODS.get(method, "unknown")
            params = payload.get("params")
            params = params if isinstance(params, dict) else {}
            message = params.get("message")
            if method == "SendMessage" and isinstance(message, dict) and message.get("taskId"):
                operation = "provideInput"
            with self._lock:
                self._counter += 1
                request = self._counter
            self._event("forward", request=request, operation=operation, requestBytes=len(raw))
            live = (self.protocol == "mcp" and operation == "readEvidence" and
                    (self.scenario.get("resourceFault") == "periodic_progress"
                     or self.scenario.get("barrier") == "abort_during_evidence_stream"))
            forwarded = self._forward(handler, raw, live=live, request=request)
            if forwarded is None:
                return
            status, headers, body = forwarded
            content_type = next((v for k, v in headers if k.lower() == "content-type"), "")
            envelope = self._decode(body, content_type)
            self._event("upstream_response", request=request, operation=operation,
                        status=status, responseBytes=len(body), complete=True,
                        rpcResult=isinstance(envelope, dict) and "result" in envelope)
            drop_requested = (self.scenario.get("dropResponseAfterPeerCommit") == operation
                    or operation == "cancel" and self.scenario.get("cleanupCancelResponse") == "lost")
            result = envelope.get("result") if isinstance(envelope, dict) else None
            task_result = result.get("task", result) if isinstance(result, dict) else None
            if (drop_requested and status == 200 and isinstance(task_result, dict)
                    and isinstance(task_result.get("id"), str) and isinstance(task_result.get("status"), dict)):
                self._event("response_dropped", request=request, operation=operation,
                            afterUpstreamResponse=True)
                return
            if operation == "observe" and self.scenario.get("barrier") == "close_before_observation_response":
                self._event("response_barrier", request=request, operation=operation)
                self.response_ready.set()
                if not self.release_response.wait(5) or self._stop.is_set():
                    self._event("barrier_expired", request=request, operation=operation)
                    return
            if operation == "discover" and self.scenario.get("discoveryResponse") == "redirect_to_ungranted_origin":
                # The proxy never follows this destination or forwards credentials.
                self._event("response_mutated", request=request, operation=operation, mutation="discovery_redirect")
                self._reply(handler, 307, [("Location", "https://127.0.0.1:1/ungranted")], b"{}")
                return
            body, content_type, mutations = self._mutate(operation, method, payload, envelope, body, content_type)
            for mutation in mutations:
                self._event("response_mutated", request=request, operation=operation, mutation=mutation)
            headers = [(k, v) for k, v in headers if k.lower() != "content-type"]
            headers.append(("Content-Type", content_type or "application/json"))
            if "too_many_tool_pages" in mutations:
                status = 200
            fault = self.scenario.get("resourceFault")
            if self.protocol == "mcp" and operation == "readEvidence" and status == 200 and (
                    fault in {"excess_sse_events", "oversized_sse_event"}):
                self._stream(handler, payload, envelope, request, fault)
            else:
                self._reply(handler, status, headers, body)
        except (OSError, http.client.HTTPException, ValueError, RecursionError):
            self._event("connection_closed", request=request, operation=operation)

    def _forward(self, handler, raw, *, live=False, request=0):
        connection = http.client.HTTPSConnection("127.0.0.1", self.upstream_port,
                    context=self.upstream_context, timeout=IO_SECONDS)
        response = None
        with self._lock:
            self._upstreams.add(connection)
        try:
            connection.putrequest(handler.command, handler.path, skip_host=True, skip_accept_encoding=True)
            connection.putheader("Host", f"127.0.0.1:{self.upstream_port}")
            connection_tokens = {v.strip().lower() for v in handler.headers.get("Connection", "").split(",")}
            for name, value in handler.headers.items():
                if name.lower() not in HOP_HEADERS | connection_tokens | {"host", "content-length"}:
                    connection.putheader(name, value)
            connection.putheader("Content-Length", str(len(raw)))
            connection.putheader("Connection", "close")
            connection.endheaders(raw)
            response = connection.getresponse()
            with self._lock:
                self._responses.add(response)
            if live and response.status == 200 and response.getheader("Content-Type", "").lower().startswith("text/event-stream"):
                self._forward_live(handler, response, request)
                return None
            body = response.read(MAX_UPSTREAM + 1)
            if len(body) > MAX_UPSTREAM:
                raise ValueError("upstream response limit")
            return response.status, response.getheaders(), body
        finally:
            if live and connection.sock:
                with contextlib.suppress(OSError):
                    connection.sock.shutdown(socket.SHUT_RDWR)
            if response is not None:
                response.close()
            connection.close()
            if live:
                self._event("upstream_closed", request=request, operation="readEvidence")
            with self._lock:
                self._upstreams.discard(connection)
                self._responses.discard(response)

    def _forward_live(self, handler, response, request):
        """Forward actual SDK progress and propagate a consumer disconnect."""
        self._event("upstream_headers", request=request, operation="readEvidence",
                    status=response.status, live=True)
        handler.send_response(response.status)
        for name, value in response.getheaders():
            if name.lower() not in HOP_HEADERS | {"content-length", "server", "date"}:
                handler.send_header(name, value)
        handler.send_header("Connection", "close")
        handler.end_headers()
        total, started, complete = 0, False, False
        end = time.monotonic() + 25
        try:
            while not self._stop.is_set() and time.monotonic() < end:
                data = response.read1(min(4096, MAX_UPSTREAM - total + 1))
                if not data:
                    complete = True
                    break
                total += len(data)
                if total > MAX_UPSTREAM:
                    self._event("stream_limit", request=request, operation="readEvidence")
                    break
                try:
                    handler.wfile.write(data)
                    handler.wfile.flush()
                except (OSError, ValueError):
                    self._event("stream_disconnect", request=request, operation="readEvidence", injected=False)
                    break
                if not started:
                    started = True
                    self._event("stream_begin", request=request, operation="readEvidence", injected=False)
                    self.stream_started.set()
        finally:
            self._event("upstream_response", request=request, operation="readEvidence",
                        status=response.status, responseBytes=total, complete=complete,
                        live=True)
            self._event("stream_end", request=request, operation="readEvidence", injected=False)

    @staticmethod
    def _decode(body, content_type):
        try:
            if content_type.lower().startswith("text/event-stream"):
                result = None
                for frame in body.replace(b"\r\n", b"\n").split(b"\n\n"):
                    data = b"\n".join(line[5:].lstrip(b" ") for line in frame.split(b"\n") if line.startswith(b"data:"))
                    if data:
                        candidate = json.loads(data)
                        if isinstance(candidate, dict) and "id" in candidate:
                            result = candidate
                return result
            return json.loads(body)
        except (ValueError, UnicodeError, RecursionError):
            return None

    def _mutate(self, operation, method, payload, value, body, content_type):
        s, mutations = self.scenario, []
        value = copy.deepcopy(value)
        if not isinstance(value, dict):
            return body, content_type, mutations
        result = value.get("result")
        drift = s.get("descriptorMutationBeforeAdmission")
        if self.protocol == "mcp" and method == "tools/list":
            if s.get("resourceFault") == "too_many_tool_pages":
                self._pages += 1
                value = {"jsonrpc": "2.0", "id": payload.get("id"),
                         "result": {"resultType": "complete", "tools": [],
                                    "nextCursor": f"proxy-page-{self._pages}"}}
                mutations.append("too_many_tool_pages")
            elif isinstance(result, dict) and result.get("tools"):
                tool = result["tools"][0]
                if drift == "tool_schema":
                    tool["inputSchema"]["properties"]["documentId"]["type"] = "integer"
                    mutations.append(drift)
                elif drift == "tool_header_annotation":
                    tool["inputSchema"]["properties"]["documentId"]["x-mcp-header"] = "ChangedDocumentId"
                    mutations.append(drift)
        if self.protocol == "a2a" and operation == "discover":
            if drift == "agent_endpoint":
                value["supportedInterfaces"][0]["url"] = "https://127.0.0.1:1/ungranted"
            elif drift == "agent_identity":
                value["name"] = "Changed fixture identity"
            elif drift == "agent_schema":
                value["defaultOutputModes"] = ["text/plain"]
            if drift in {"agent_endpoint", "agent_identity", "agent_schema"}:
                mutations.append(drift)
            extension = s.get("agentCardRequiredExtension")
            if drift == "agent_required_capability":
                extension = "unsupported.example/required"
            if extension:
                value.setdefault("capabilities", {}).setdefault("extensions", []).append({"uri": extension, "required": True})
                mutations.append("required_extension")
        if self.protocol == "mcp" and operation == "readEvidence" and isinstance(result, dict):
            if s.get("omitMcpResultType"):
                result.pop("resultType", None)
                mutations.append("omit_mcp_result_type")
            if "mcpResultType" in s:
                result["resultType"] = s["mcpResultType"]
                mutations.append("mcp_result_type")
                if s.get("inputRequest") == "unsupported_elicitation":
                    result.clear()
                    result.update({"resultType": s["mcpResultType"], "inputRequests": {
                        "fixture-input": {"method": "elicitation/create", "params": {
                            "mode": "form", "message": "Choose a fixture value.",
                            "requestedSchema": {"type": "object", "properties": {
                                "answer": {"type": "string"}}, "required": ["answer"]}}}}})
                    mutations.append("unsupported_elicitation")
            if s.get("wireMutation") == "evidence_response_id":
                value["id"] = "proxy-wrong-id"
                mutations.append("evidence_response_id")
            evidence = result.get("structuredContent")
            kind = s.get("evidenceMutation")
            if kind == "malformed_json":
                return b'{"jsonrpc":', "application/json", ["malformed_json"]
            if kind == "oversized_response":
                result["proxyPadding"] = "x" * 70_000
            elif kind == "over_depth":
                nested = None
                for _ in range(32):
                    nested = {"nested": nested}
                result["proxyNested"] = nested
            elif kind == "tool_error":
                result["isError"] = True
            elif kind == "missing_structured_content":
                result.pop("structuredContent", None)
            elif isinstance(evidence, dict):
                if kind == "wrong_field_type":
                    evidence["revision"] = "one"
                elif kind == "wrong_document":
                    evidence["documentId"] = "other-document"
                elif kind == "duplicate_fact_id":
                    evidence["facts"][1]["id"] = evidence["facts"][0]["id"]
                elif kind == "wrong_revision":
                    evidence["revision"] += 1
            if kind:
                mutations.append(kind)
        if self.protocol == "a2a" and isinstance(result, dict):
            task = result.get("task", result)
            wire = s.get("wireMutation")
            if operation == "observe" and isinstance(task, dict):
                if wire == "observe_taskId":
                    task["id"] = "proxy-wrong-task"
                    mutations.append(wire)
                elif wire == "observe_contextId":
                    task["contextId"] = "proxy-wrong-context"
                    mutations.append(wire)
            if operation == "submit" and wire == "a2a_pre_1_envelope" and "task" in result:
                value["result"] = {**result["task"], "kind": "task"}
                mutations.append(wire)
            kind = s.get("reportMutation")
            artifacts = task.get("artifacts", []) if isinstance(task, dict) else []
            if kind and artifacts:
                report = artifacts[0]["parts"][0]["data"]
                if kind == "wrong_value":
                    report["selected"][0]["value"] = "invented"
                elif kind == "missing_selected_id":
                    report["selected"].pop()
                elif kind == "reordered_ids":
                    report["selected"].reverse()
                elif kind == "extra_field":
                    report["unexpected"] = True
                elif kind == "wrong_revision":
                    report["revision"] += 1
                elif kind == "wrong_document":
                    report["documentId"] = "other-document"
                mutations.append(kind)
        if mutations:
            body = _sse(value) if content_type.lower().startswith("text/event-stream") else _json(value)
        if s.get("resourceFault") == "excess_total_bytes":
            # Legal JSON whitespace keeps each message below 65,536 bytes.
            # The controller must configure a cumulative allowance low enough to
            # fail during evidence, as required by the independent inventory.
            body = _json(value).ljust(60_000, b" ")
            content_type = "application/json"
            mutations.append("excess_total_bytes")
        return body, content_type, mutations

    def _stream(self, handler, payload, final, request, fault):
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream")
        handler.send_header("Connection", "close")
        handler.end_headers()
        params = payload.get("params") or {}
        token = (params.get("_meta") or {}).get("progressToken")
        notification = {"jsonrpc": "2.0", "method": "notifications/progress",
                        "params": {"progressToken": token, "progress": 0}}
        if fault == "oversized_sse_event":
            notification["params"]["message"] = "x" * 17_000
            handler.wfile.write(_sse(notification))
            handler.wfile.flush()
            self._event("response_mutated", request=request, operation="readEvidence", mutation=fault)
            return
        count = 17
        self._event("stream_begin", request=request, operation="readEvidence", injected=True)
        try:
            for index in range(count):
                if self._stop.is_set():
                    return
                notification["params"]["progress"] = index
                handler.wfile.write(_sse(notification))
                handler.wfile.flush()
                self.stream_started.set()
            if final is not None:
                handler.wfile.write(_sse(final))
                handler.wfile.flush()
        except (OSError, ValueError):
            self._event("stream_disconnect", request=request, operation="readEvidence", injected=True)
        finally:
            self._event("stream_end", request=request, operation="readEvidence")

    @staticmethod
    def _reply(handler, status, headers, body):
        handler.send_response(status)
        connection_tokens = {v.strip().lower() for k, values in headers if k.lower() == "connection" for v in values.split(",")}
        has_type = False
        for name, value in headers:
            if name.lower() not in HOP_HEADERS | connection_tokens | {"content-length", "server", "date"}:
                handler.send_header(name, value)
                has_type = has_type or name.lower() == "content-type"
        if not has_type:
            handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("Connection", "close")
        handler.end_headers()
        handler.wfile.write(body)
        handler.wfile.flush()
