"""Shared, sequential host for the bounded evidence-to-report protocol profile."""
from __future__ import annotations

import copy
import base64
import hashlib
import json
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from .transport import HTTPSTransport, TransportError, encode_header


OPERATIONS = frozenset({"readEvidence", "submit", "observe", "provideInput", "cancel"})
STATES = {"TASK_STATE_" + key: value for key, value in [
    ("SUBMITTED", "Submitted"), ("WORKING", "Working"),
    ("INPUT_REQUIRED", "InputRequired"), ("AUTH_REQUIRED", "AuthRequired"),
    ("COMPLETED", "Completed"), ("FAILED", "Failed"),
    ("CANCELED", "Canceled"), ("REJECTED", "Rejected")]}
TERMINAL = {"Completed", "Failed", "Canceled", "Rejected"}


@dataclass(frozen=True)
class Limits:
    root_seconds: float = 15
    request_seconds: float = 2
    cleanup_seconds: float = 1
    max_requests: int = 16
    cleanup_requests: int = 2
    max_response_bytes: int = 65536
    max_request_bytes: int = 65536
    max_inbound_bytes: int = 262144
    max_depth: int = 16
    max_events: int = 16
    max_event_bytes: int = 16384
    max_pages: int = 2
    max_polls: int = 3
    poll_interval: float = .1

    def __post_init__(self):
        durations = {"root_seconds", "request_seconds", "cleanup_seconds", "poll_interval"}
        for name, value in self.__dict__.items():
            if (type(value) not in (int, float) or value < 0 or value != value
                    or value in (float("inf"), -float("inf"))):
                raise ValueError("invalid limit: " + name)
            if name not in durations and type(value) is not int:
                raise ValueError("count limit must be an integer: " + name)
            if name in durations:
                try:
                    finite = float(value) != float("inf")
                except OverflowError:
                    finite = False
                if not finite:
                    raise ValueError("invalid duration: " + name)
        if self.cleanup_requests > self.max_requests:
            raise ValueError("cleanup reserve exceeds total")
        if not self.root_seconds or not self.request_seconds or not self.cleanup_seconds:
            raise ValueError("deadline must be finite and positive")


@dataclass(frozen=True)
class HostConfig:
    mcp_url: str
    a2a_url: str
    mcp_token: str = field(repr=False)
    a2a_token: str = field(repr=False)
    ca_file: str
    tool_descriptor: dict
    agent_card: dict
    principal: str = "alice"
    tenant: str = "tenant-a"
    grants: frozenset[str] = OPERATIONS
    limits: Limits = field(default_factory=Limits)
    allowed_documents: frozenset[str] = frozenset({"evidence-42"})
    expected_revision: int = 1

    def __post_init__(self):
        for name in ("mcp_url", "a2a_url"):
            value = getattr(self, name)
            if type(value) is not str or any(ord(c) <= 32 or ord(c) == 127 for c in value):
                raise ValueError("trusted endpoint must be an explicit HTTPS URL")
            try:
                parsed = urlsplit(value)
                port = parsed.port
            except ValueError:
                raise ValueError("trusted endpoint must be an explicit HTTPS URL") from None
            if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                    or parsed.password or parsed.fragment or port == 0):
                raise ValueError("trusted endpoint must be an explicit HTTPS URL")
        for name in ("mcp_token", "a2a_token"):
            value = getattr(self, name)
            # Tokens are opaque credentials, but they must be usable as one
            # HTTP header value. Errors never interpolate a credential.
            if type(value) is not str or not value or any(ord(c) < 33 or ord(c) > 126 for c in value):
                raise ValueError("invalid bearer credential: " + name)
        if type(self.ca_file) is not str or not self.ca_file or "\x00" in self.ca_file:
            raise ValueError("ca_file must name an explicit CA file")
        for name in ("principal", "tenant"):
            if not text(getattr(self, name)):
                raise ValueError("invalid identity field: " + name)
        if not isinstance(self.limits, Limits):
            raise ValueError("limits must be a Limits value")
        for name in ("grants", "allowed_documents"):
            values = getattr(self, name)
            if (type(values) not in (list, tuple, set, frozenset)
                    or not all(text(value) for value in values)):
                raise ValueError("invalid collection: " + name)
            object.__setattr__(self, name, frozenset(values))
        if not self.grants <= OPERATIONS:
            raise ValueError("unknown operation grant")
        if type(self.expected_revision) is not int or not 0 <= self.expected_revision <= 1_000_000:
            raise ValueError("expected_revision must be a bounded integer")
        for name in ("tool_descriptor", "agent_card"):
            if type(getattr(self, name)) is not dict:
                raise ValueError("binding metadata must be a JSON object: " + name)
            try:
                digest(getattr(self, name))
            except (ValueError, TypeError, RecursionError):
                raise ValueError("binding metadata must be finite JSON: " + name) from None


class HostError(Exception):
    def __init__(self, code, remote="NotStarted", fatal=False):
        self.code, self.remote, self.fatal = code, remote, fatal
        super().__init__(code)


def digest(value) -> str:
    # This profile excludes floats/non-JSON values; this is its documented
    # canonical identity, not an assertion of general RFC8785 support.
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def text(value, max_length=256):
    return isinstance(value, str) and 0 < len(value) <= max_length and not any(0xD800 <= ord(c) <= 0xDFFF for c in value)


def evidence_valid(value, document=None):
    if not isinstance(value, dict) or set(value) != {"documentId", "revision", "facts"}:
        return False
    if not text(value["documentId"]) or (document is not None and value["documentId"] != document):
        return False
    if type(value["revision"]) is not int or not 0 <= value["revision"] <= 1_000_000:
        return False
    facts = value["facts"]
    if not isinstance(facts, list) or not 1 <= len(facts) <= 32:
        return False
    ids = set()
    for item in facts:
        if not isinstance(item, dict) or set(item) != {"id", "value"} or not text(item["id"]) or not text(item["value"]):
            return False
        if item["id"] in ids:
            return False
        ids.add(item["id"])
    return True


def ids_valid(value):
    return isinstance(value, list) and 1 <= len(value) <= 32 and all(text(x) for x in value) and len(set(value)) == len(value)


encode_header_value = encode_header


def validate_tool_descriptor(descriptor):
    """Validate the approved profile's descriptor and all header annotations."""
    if (not isinstance(descriptor, dict) or not text(descriptor.get("name"))
            or not isinstance(descriptor.get("inputSchema"), dict)
            or descriptor["inputSchema"].get("type") != "object"
            or not isinstance(descriptor.get("outputSchema"), dict)):
        raise HostError("BindingChanged")
    Host._parameter_headers(descriptor, {})
    return True


def normalize_task_state(value):
    if not isinstance(value, str) or value not in STATES:
        raise HostError("UnsupportedRemoteState", "Completed")
    return STATES[value]


def _protocol(valid):
    if not valid:
        raise HostError("ProtocolRejected", "Unknown")


def _a2a_envelope(value, fields, *, strings=(), lists=()):
    _protocol(isinstance(value, dict) and not set(value) - set(fields))
    for key in strings:
        _protocol(key not in value or isinstance(value[key], str))
    for key in lists:
        _protocol(key not in value or isinstance(value[key], list)
                  and all(isinstance(item, str) for item in value[key]))
    _protocol("metadata" not in value or isinstance(value["metadata"], dict))


def _a2a_parts(parts):
    _protocol(isinstance(parts, list) and len(parts) > 0)
    for part in parts:
        _a2a_envelope(part, {"data", "text", "raw", "url", "metadata", "filename", "mediaType"},
                      strings=("text", "raw", "url", "filename", "mediaType"))
        _protocol(len(set(part) & {"data", "text", "raw", "url"}) == 1)
        if "raw" in part:
            try:
                base64.b64decode(part["raw"], validate=True)
            except (ValueError, UnicodeError):
                raise HostError("ProtocolRejected", "Unknown") from None


def _a2a_message(message, *, agent=False):
    _a2a_envelope(message, {"messageId", "contextId", "taskId", "role", "parts", "metadata", "extensions", "referenceTaskIds"},
                  strings=("messageId", "contextId", "taskId", "role"), lists=("extensions", "referenceTaskIds"))
    _protocol(text(message.get("messageId")) and message.get("role") in ({"ROLE_AGENT"} if agent else {"ROLE_AGENT", "ROLE_USER"}))
    _a2a_parts(message.get("parts"))


def _a2a_task_envelope(value):
    """Validate the D0 JSON representation against the pinned A2A field shapes."""
    _a2a_envelope(value, {"id", "contextId", "status", "artifacts", "history", "metadata"}, strings=("id", "contextId"))
    _protocol(text(value.get("id")) and text(value.get("contextId")))
    status = value.get("status")
    _a2a_envelope(status, {"state", "message", "timestamp"}, strings=("state", "timestamp"))
    _protocol(isinstance(status.get("state"), str))
    if "timestamp" in status:
        from datetime import datetime
        try:
            _protocol(bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z", status["timestamp"])))
            datetime.fromisoformat(status["timestamp"].replace("Z", "+00:00"))
        except ValueError:
            raise HostError("ProtocolRejected", "Unknown") from None
    if "message" in status:
        _a2a_message(status["message"])
    for key in ("artifacts", "history"):
        _protocol(key not in value or isinstance(value[key], list))
    for message in value.get("history", []):
        _a2a_message(message)
    for artifact in value.get("artifacts", []):
        _a2a_envelope(artifact, {"artifactId", "name", "description", "parts", "metadata", "extensions"},
                      strings=("artifactId", "name", "description"), lists=("extensions",))
        _protocol(text(artifact.get("artifactId")))
        _a2a_parts(artifact.get("parts"))


def _mcp_result_envelope(result):
    """Check supported MCP content shapes before accepting structured content."""
    _protocol(isinstance(result.get("content"), list))
    _protocol("isError" not in result or type(result["isError"]) is bool)
    for item in [result, *result["content"]]:
        _protocol(isinstance(item, dict))
        _protocol(item.get("_meta") is None or isinstance(item["_meta"], dict))
    for item in result["content"]:
        kind = item.get("type")
        required = {"text": ("text",), "image": ("data", "mimeType"), "audio": ("data", "mimeType"),
                    "resource_link": ("name", "uri"), "resource": ()}
        _protocol(isinstance(kind, str) and kind in required)
        _protocol(all(isinstance(item.get(key), str) for key in required[kind]))
        annotations = item.get("annotations")
        if annotations is not None:
            _protocol(isinstance(annotations, dict))
            audience, priority = annotations.get("audience"), annotations.get("priority")
            _protocol(audience is None or isinstance(audience, list) and all(x in ("user", "assistant") for x in audience))
            _protocol(priority is None or type(priority) in (int, float) and 0 <= priority <= 1)
            _protocol(annotations.get("lastModified") is None or isinstance(annotations["lastModified"], str))
        if kind == "resource":
            resource = item.get("resource")
            _protocol(isinstance(resource, dict) and isinstance(resource.get("uri"), str))
            _protocol(isinstance(resource.get("text"), str) or isinstance(resource.get("blob"), str))
            _protocol(resource.get("mimeType") is None or isinstance(resource["mimeType"], str))
            _protocol(resource.get("_meta") is None or isinstance(resource["_meta"], dict))
        if kind == "resource_link":
            for key in ("title", "description", "mimeType"):
                _protocol(item.get(key) is None or isinstance(item[key], str))
            _protocol(item.get("size") is None or type(item["size"]) is int)
            if item.get("icons") is not None:
                _protocol(isinstance(item["icons"], list))
                for icon in item["icons"]:
                    _protocol(isinstance(icon, dict) and isinstance(icon.get("src"), str))
                    _protocol(icon.get("mimeType") is None or isinstance(icon["mimeType"], str))
                    _protocol(icon.get("theme") is None or icon["theme"] in ("light", "dark"))
                    _protocol(icon.get("sizes") is None or isinstance(icon["sizes"], list) and all(isinstance(x, str) for x in icon["sizes"]))


class Host:
    def __init__(self, config: HostConfig | dict, *, transport=None, clock=time.monotonic, sleep=time.sleep):
        if isinstance(config, dict):
            config = dict(config)
            if isinstance(config.get("limits"), dict):
                config["limits"] = Limits(**config["limits"])
            config = HostConfig(**config)
        if not isinstance(config, HostConfig):
            raise ValueError("config must be HostConfig or a configuration dictionary")
        self.config = copy.deepcopy(config)
        config = self.config
        self.limits = config.limits
        self.clock, self.sleep = clock, sleep
        self.tool_digest = digest(config.tool_descriptor)
        self.card_digest = digest(config.agent_card)
        self.transport = transport or HTTPSTransport(config.ca_file, clock=clock)
        self.trace = []
        self.root_id = secrets.token_hex(16)
        self.deadline = clock() + self.limits.root_seconds
        self.closed = False
        self.fatal = None
        self.requests = self.normal_requests = self.cleanup_count = self.inbound = 0
        self.submitted = self.continued = self.polls = 0
        self.last_poll = None
        self.refs = {}
        self.evidence = None
        self.finished = None
        self.remote_started = False
        self.remote_unknown = False
        # A dispatched request stays unresolved until its operation's typed
        # response has been validated. Receiving bytes is not completion proof.
        self._pending_deliveries = set()
        self._lock = threading.RLock()
        self._activity = threading.Condition(self._lock)
        self._finish_lock = threading.Lock()
        self._active = False
        self._event("root_open")

    def _event(self, event, **fields):
        # Fixed metadata only. Never pass raw errors, tokens, request bodies or URLs.
        self.trace.append({"sequence": len(self.trace), "event": event, **fields})

    def _live(self):
        if self.closed:
            raise HostError(self.fatal["outcome"] if self.fatal else "RootTerminated", self._remote_outcome(), True)
        if self.clock() >= self.deadline:
            self.fatal = {"outcome": "Timeout", "remoteOutcome": self._remote_outcome(), "fatal": True}
            raise HostError("Timeout", self.fatal["remoteOutcome"], True)

    def abort(self, code="RootTerminated"):
        with self._lock:
            if self.finished is not None:
                return
            if self.fatal is None:
                self.fatal = {"outcome": code, "remoteOutcome": self._remote_outcome(), "fatal": True}
            self.closed = True
            self._event("root_abort", code=code)
        self._cancel_active()

    def _cancel_active(self):
        cancel = getattr(self.transport, "cancel_active", None)
        if cancel is not None:
            cancel()

    def _remote_outcome(self):
        return "Unknown" if self.remote_unknown or self._pending_deliveries else "Completed" if self.remote_started else "NotStarted"

    def _resolve_delivery(self, remote="Completed"):
        with self._lock:
            if remote == "Unknown":
                self.remote_unknown = True
            self._pending_deliveries.clear()

    @staticmethod
    def _error(exc):
        return {"kind": "Error", "code": exc.code, "remoteOutcome": exc.remote, "fatal": exc.fatal}

    def _reserve(self, cleanup=False):
        with self._lock:
            if not cleanup:
                self._live()
            if self.requests >= self.limits.max_requests:
                raise HostError("BudgetDenied")
            if cleanup:
                if self.cleanup_count >= self.limits.cleanup_requests:
                    raise HostError("BudgetDenied")
                self.cleanup_count += 1
            else:
                if self.normal_requests >= self.limits.max_requests - self.limits.cleanup_requests:
                    raise HostError("BudgetDenied")
                self.normal_requests += 1
            self.requests += 1

    def _request(self, protocol, method, params=None, *, cleanup=False, cleanup_deadline=None):
        limits = self.limits
        if not cleanup:
            self._live()
        request_id = str(self.requests + 1)
        progress = "request-" + request_id
        if protocol == "mcp":
            endpoint, token = self.config.mcp_url, self.config.mcp_token
            params = copy.deepcopy(params or {})
            params["_meta"] = {
                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                "io.modelcontextprotocol/clientInfo": {"name": "meda-d0", "version": "1"},
                "io.modelcontextprotocol/clientCapabilities": {},
                "progressToken": progress,
            }
            headers = {"MCP-Protocol-Version": "2026-07-28", "Mcp-Method": method,
                       "Accept": "application/json, text/event-stream"}
            if method == "tools/call":
                headers["Mcp-Name"] = encode_header(params["name"])
                headers.update(self._parameter_headers(self.config.tool_descriptor, params["arguments"]))
        else:
            endpoint, token = self.config.a2a_url, self.config.a2a_token
            headers = {"A2A-Version": "1.0", "Accept": "application/json"}
        if method == "__card":
            parsed = urlsplit(endpoint)
            endpoint = f"{parsed.scheme}://{parsed.netloc}/.well-known/agent-card.json"
            verb, body = "GET", None
        else:
            verb = "POST"
            body = json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method,
                               "params": params or {}}, separators=(",", ":"), ensure_ascii=False).encode()
            if len(body) > limits.max_request_bytes:
                raise HostError("ResponseLimit")
            headers["Content-Type"] = "application/json"
        headers["Authorization"] = "Bearer " + token
        end = min(self.clock() + limits.request_seconds, cleanup_deadline if cleanup else self.deadline)
        remaining = min(limits.max_response_bytes, limits.max_inbound_bytes - self.inbound)
        if remaining <= 0:
            raise HostError("ResponseLimit")
        self._reserve(cleanup)
        self._event("admitted", protocol=protocol, method=method, cleanup=cleanup, request=self.requests,
                    normalRequests=self.normal_requests, totalRequests=self.requests, cleanupCount=self.cleanup_count,
                    remainingNormal=limits.max_requests-limits.cleanup_requests-self.normal_requests,
                    remainingInbound=limits.max_inbound_bytes-self.inbound,
                    rootRemainingSeconds=max(0, self.deadline-self.clock()))
        def on_dispatch():
            with self._lock:
                if not cleanup:
                    self._live()
                self.remote_started = True
                self._pending_deliveries.add(self.requests)
                self._event("dispatch", protocol=protocol, method=method, cleanup=cleanup, request=self.requests)
        try:
            response = self.transport.request(verb, endpoint, headers, body, deadline=end,
                max_bytes=remaining, max_depth=limits.max_depth,
                max_events=limits.max_events, max_event_bytes=limits.max_event_bytes,
                request_id=None if verb == "GET" else request_id, progress_token=progress,
                check_live=None if cleanup else self._live, on_dispatch=on_dispatch)
            self.inbound += response.received
            self.remote_started = True
            self._event("received", protocol=protocol, method=method, bytes=response.received,
                        notifications=response.notifications, cleanup=cleanup, request=self.requests, inboundBytes=self.inbound)
            if not cleanup:
                self._live()
        except TransportError as exc:
            self.inbound += exc.received
            remote = "Unknown" if exc.dispatched else "NotStarted"
            self.remote_started = self.remote_started or exc.dispatched
            self.remote_unknown = self.remote_unknown or exc.dispatched
            fatal = not cleanup and (self.closed or self.clock() >= self.deadline)
            if fatal:
                if self.fatal is None:
                    self.fatal = {"outcome": "Timeout" if not self.closed else "RootTerminated", "remoteOutcome": remote, "fatal": True}
                elif remote == "Unknown":
                    self.fatal["remoteOutcome"] = remote
            self._event("transport_error", code=exc.code, remoteOutcome=remote, cleanup=cleanup,
                        request=self.requests, bytes=exc.received, inboundBytes=self.inbound)
            raise HostError(self.fatal["outcome"] if fatal else exc.code, remote, fatal) from exc
        except HostError as exc:
            # check_live may terminate the root after bytes were transmitted.
            # No validated reply exists, even if preceding discovery completed.
            if self._pending_deliveries:
                exc.remote = "Unknown"
                self.remote_unknown = True
                if self.fatal is not None:
                    self.fatal["remoteOutcome"] = "Unknown"
            self._event("transport_error", code=exc.code, remoteOutcome=exc.remote, cleanup=cleanup,
                        request=self.requests, bytes=0, inboundBytes=self.inbound)
            raise
        if response.status in (401, 403):
            raise HostError("AuthorityDenied", "Completed")
        if response.status != 200:
            raise HostError("TransportFailure", "Completed")
        value = response.value
        if verb == "GET":
            if not isinstance(value, dict):
                raise HostError("ProtocolRejected", "Unknown")
            return value
        if not isinstance(value, dict) or value.get("jsonrpc") != "2.0" or type(value.get("id")) is not str or value["id"] != request_id:
            raise HostError("ProtocolRejected", "Unknown")
        if ("result" in value) == ("error" in value):
            raise HostError("ProtocolRejected", "Unknown")
        if "error" in value:
            error = value["error"]
            if not isinstance(error, dict) or type(error.get("code")) is not int or not isinstance(error.get("message"), str):
                raise HostError("ProtocolRejected", "Unknown")
            if protocol == "a2a" and error["code"] == -32002:
                raise HostError("TaskNotCancelable", "Completed")
            if protocol == "a2a" and error["code"] == -32001:
                raise HostError("InvalidReference", "Completed")
            raise HostError("TransportFailure", "Completed")
        result = value["result"]
        if not isinstance(result, dict):
            raise HostError("ProtocolRejected", "Unknown")
        if protocol == "mcp" and result.get("resultType", "complete") != "complete":
            raise HostError("ProtocolRejected", "Completed")
        return result

    @staticmethod
    def _parameter_headers(descriptor, args):
        schema = descriptor.get("inputSchema", {})
        mapping = []
        names = set()

        def walk(value, path, allowed=True):
            if not isinstance(value, dict):
                return
            if "x-mcp-header" in value:
                name = value["x-mcp-header"]
                if (not allowed or not path or not isinstance(name, str)
                        or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", name)
                        or name.lower() in names or value.get("type") not in ("string", "integer", "boolean")):
                    raise HostError("BindingChanged")
                names.add(name.lower())
                mapping.append((path, name, value["type"]))
            for key, child in value.items():
                if key == "properties" and isinstance(child, dict):
                    for label, prop in child.items():
                        walk(prop, path + [label], allowed)
                elif isinstance(child, dict):
                    walk(child, path, False)
                elif isinstance(child, list):
                    for sub in child:
                        walk(sub, path, False)
        walk(schema, [])
        headers = {}
        for path, name, kind in mapping:
            value = args
            for key in path:
                if not isinstance(value, dict) or key not in value:
                    value = None
                    break
                value = value[key]
            if value is None:
                continue
            valid = (kind == "string" and isinstance(value, str)
                     or kind == "boolean" and type(value) is bool
                     or kind == "integer" and type(value) is int and abs(value) <= 2**53 - 1)
            if not valid:
                raise HostError("ProtocolRejected")
            scalar = str(value).lower() if type(value) is bool else str(value)
            headers["Mcp-Param-" + name] = encode_header(scalar)
        return headers

    def _check_tool(self):
        cursor = None
        seen = set()
        found = []
        for _ in range(self.limits.max_pages):
            result = self._request("mcp", "tools/list", {"cursor": cursor} if cursor else {})
            tools = result.get("tools")
            if not isinstance(tools, list) or len(tools) > 128:
                raise HostError("ProtocolRejected", "Completed")
            for tool in tools:
                if not isinstance(tool, dict):
                    raise HostError("ProtocolRejected", "Completed")
                try:
                    validate_tool_descriptor(tool)
                except HostError:
                    continue  # Invalid headers exclude the tool, as MCP requires.
                if tool.get("name") == "evidence.read":
                    found.append(tool)
            cursor = result.get("nextCursor")
            if not cursor:
                break
            if not text(cursor, 1024) or cursor in seen:
                raise HostError("ProtocolRejected", "Completed")
            seen.add(cursor)
        else:
            raise HostError("ResponseLimit", "Completed")
        if len(found) != 1 or digest(found[0]) != self.tool_digest:
            raise HostError("BindingChanged", "Completed")

    def _check_card(self, *, cleanup=False, cleanup_deadline=None):
        card = self._request("a2a", "__card", cleanup=cleanup, cleanup_deadline=cleanup_deadline)
        if digest(card) != self.card_digest:
            raise HostError("BindingChanged", "Completed")
        interfaces = card.get("supportedInterfaces")
        if not isinstance(interfaces, list) or not any(
            isinstance(i, dict) and i.get("url") == self.config.a2a_url
            and i.get("protocolBinding") == "JSONRPC" and i.get("protocolVersion") == "1.0"
            for i in interfaces):
            raise HostError("BindingChanged", "Completed")
        caps = card.get("capabilities", {})
        if not isinstance(caps, dict) or any(isinstance(e, dict) and e.get("required") for e in caps.get("extensions", [])):
            raise HostError("BindingChanged", "Completed")

    def _reference(self, token):
        if not isinstance(token, str) or token not in self.refs:
            raise HostError("InvalidReference")
        item = self.refs[token]
        if (item["root"] != self.root_id or item["principal"] != self.config.principal
                or item["tenant"] != self.config.tenant or item["peer"] != self.config.a2a_url
                or item["binding"] != self.card_digest):
            raise HostError("InvalidReference")
        return item

    def _task(self, value, old=None, *, send=False):
        if send:
            _protocol(isinstance(value, dict) and not set(value) - {"task", "message"})
            if set(value).intersection({"task", "message"}) == {"message"}:
                message = value["message"]
                _a2a_message(message, agent=True)
                return {"kind": "DirectReply"}
            if set(value).intersection({"task", "message"}) != {"task"}:
                raise HostError("ProtocolRejected", "Unknown")
            value = value["task"]
        _a2a_task_envelope(value)
        if old and (value["id"] != old["task_id"] or value["contextId"] != old["context_id"]):
            raise HostError("ProtocolRejected", "Unknown")
        status = value.get("status")
        if not isinstance(status, dict) or not isinstance(status.get("state"), str):
            raise HostError("ProtocolRejected", "Unknown")
        if status["state"] not in STATES:
            raise HostError("UnsupportedRemoteState", "Completed")
        state = normalize_task_state(status["state"])
        if old is None:
            token = secrets.token_urlsafe(32)
            old = {"root": self.root_id, "principal": self.config.principal,
                   "tenant": self.config.tenant, "peer": self.config.a2a_url, "binding": self.card_digest, "task_id": value["id"],
                   "context_id": value["contextId"], "token": token, "state": state}
            self.refs[token] = old
        else:
            old["state"] = state
        result = {"kind": "Task", "ref": old["token"], "state": state}
        if "artifacts" in value:
            artifacts = value["artifacts"]
            if not isinstance(artifacts, list):
                raise HostError("ProtocolRejected", "Unknown")
            # Shape is protocol validation; exact membership/order/value is the
            # separate application validator's obligation.
            if len(artifacts) == 1 and isinstance(artifacts[0], dict):
                parts = artifacts[0].get("parts")
                if isinstance(parts, list) and len(parts) == 1 and isinstance(parts[0], dict) and isinstance(parts[0].get("data"), dict):
                    result["artifact"] = copy.deepcopy(parts[0]["data"])
        # Only a fully validated new observation can supersede a prior explicit
        # cancellation refusal. The refusal itself says nothing about task state.
        if state not in TERMINAL and "cancel_refusal_sequence" in old:
            refusal_sequence = old.pop("cancel_refusal_sequence")
            self._event("cleanup_eligibility_restored", refusalSequence=refusal_sequence,
                        state=state)
        self._event("task_observed", state=state, reference=len(self.refs))
        return result

    def call(self, operation, arguments):
        owns_call = False
        try:
            with self._lock:
                self._live()
                if self._active:
                    raise HostError("BudgetDenied")
                if not isinstance(operation, str) or operation not in OPERATIONS or operation not in self.config.grants:
                    raise HostError("AuthorityDenied")
                if not isinstance(arguments, dict):
                    raise HostError("ProtocolRejected")
                self._active = True
                owns_call = True
            result = self._call(operation, arguments)
            self._resolve_delivery()
            return result
        except HostError as exc:
            if owns_call:
                self._resolve_delivery(exc.remote)
            if exc.fatal and self.fatal is None:
                self.fatal = {"outcome": exc.code, "remoteOutcome": exc.remote, "fatal": True}
            self._event("call_rejected", operation=operation if isinstance(operation, str) and operation in OPERATIONS else "unknown", code=exc.code)
            return self._error(exc)
        except (TypeError, ValueError, UnicodeError, RecursionError):
            remote = "Unknown" if self._pending_deliveries else "NotStarted"
            if owns_call:
                self._resolve_delivery(remote)
            self._event("call_rejected", operation="unknown", code="ProtocolRejected")
            return self._error(HostError("ProtocolRejected", remote))
        finally:
            if owns_call:
                with self._activity:
                    self._active = False
                    self._activity.notify_all()

    def _call(self, operation, args):
        expected = {"readEvidence": {"documentId"}, "submit": {"evidence", "includeIds"},
                    "observe": {"ref"}, "cancel": {"ref"}, "provideInput": {"ref", "includeIds"}}[operation]
        if set(args) - expected or (operation != "submit" and set(args) != expected):
            raise HostError("ProtocolRejected")
        if operation == "readEvidence":
            doc = args.get("documentId")
            if not text(doc) or doc not in self.config.allowed_documents:
                raise HostError("AuthorityDenied")
            self._check_tool()
            result = self._request("mcp", "tools/call", {"name": "evidence.read", "arguments": {"documentId": doc}})
            _mcp_result_envelope(result)
            if result.get("isError", False) is not False:
                raise HostError("TransportFailure", "Completed")
            value = result.get("structuredContent")
            if not evidence_valid(value, doc) or value["revision"] != self.config.expected_revision or not isinstance(result.get("content"), list):
                raise HostError("ProtocolRejected", "Completed")
            self.evidence = copy.deepcopy(value)
            return {"kind": "Evidence", "value": copy.deepcopy(value)}
        ref = None
        if operation == "submit":
            if not evidence_valid(args.get("evidence")) or args["evidence"] != self.evidence:
                raise HostError("ProtocolRejected")
            if "includeIds" in args and not ids_valid(args["includeIds"]):
                raise HostError("ProtocolRejected")
            if self.submitted:
                raise HostError("BudgetDenied")
        else:
            ref = self._reference(args.get("ref"))
            if operation == "provideInput":
                if not ids_valid(args.get("includeIds")) or ref["state"] != "InputRequired":
                    raise HostError("ProtocolRejected")
                if self.continued:
                    raise HostError("BudgetDenied")
            if operation == "observe":
                if self.polls >= self.limits.max_polls:
                    raise HostError("BudgetDenied")
                if self.last_poll is not None:
                    self.sleep(max(0, self.last_poll + self.limits.poll_interval - self.clock()))
                    self._live()
        self._check_card()
        if operation in ("submit", "provideInput"):
            message = {"messageId": secrets.token_hex(16), "role": "ROLE_USER"}
            if operation == "submit":
                data = {"kind": "evidence-report", "evidence": args["evidence"]}
                if "includeIds" in args:
                    data["includeIds"] = args["includeIds"]
                self.submitted += 1
            else:
                data = {"includeIds": args["includeIds"]}
                message.update(taskId=ref["task_id"], contextId=ref["context_id"])
                self.continued += 1
            message["parts"] = [{"data": data}]
            value = self._request("a2a", "SendMessage", {"message": message, "configuration": {"returnImmediately": True}})
            return self._task(value, ref, send=True)
        if operation == "observe":
            self.polls += 1
            self.last_poll = self.clock()
        method = "GetTask" if operation == "observe" else "CancelTask"
        try:
            value = self._request("a2a", method, {"id": ref["task_id"]})
        except HostError as exc:
            if operation == "cancel" and exc.code == "TaskNotCancelable" and exc.remote == "Completed":
                # _request has validated the response envelope and request ID.
                # Completed describes the request's delivery, not a terminal task.
                ref["cancel_refusal_sequence"] = len(self.trace)
                self._event("explicit_cancel_refused", code=exc.code, state=ref["state"])
            raise
        return self._task(value, ref)

    def finish(self, application_result):
        # One finisher owns cleanup and publication. Other finishers wait for
        # its receipt; abort may still establish a fatal result before publish.
        with self._finish_lock:
            return self._finish(application_result)

    def _finish(self, application_result):
        with self._lock:
            if self.finished is not None:
                return copy.deepcopy(self.finished)
            if not self.closed:
                try:
                    self._live()
                except HostError:
                    pass
            self.closed = True
            self._event("root_close")
        self._cancel_active()
        cleanup = []
        end = self.clock() + self.limits.cleanup_seconds
        with self._activity:
            joined = self._activity.wait_for(lambda: not self._active,
                timeout=max(0, end - self.clock()))
            if not joined:
                self.fatal = {"outcome": "CleanupFailure", "remoteOutcome": self._remote_outcome(), "fatal": True}
        if not joined:
            cleanup.append({"outcome": "CleanupFailure", "remoteOutcome": self._remote_outcome()})
        for ref in self.refs.values():
            if not joined:
                break
            if ref["state"] in TERMINAL:
                continue
            if "cancel_refusal_sequence" in ref:
                skipped = {"outcome": "Skipped", "reason": "PriorExplicitRefusal",
                           "refusalSequence": ref["cancel_refusal_sequence"],
                           "lastObservedState": ref["state"], "remoteOutcome": "Unknown"}
                cleanup.append(skipped)
                self._event("cleanup_skipped", **skipped)
                continue
            if "cancel" not in self.config.grants:
                cleanup.append({"outcome": "AuthorityDenied", "remoteOutcome": "Unknown"})
                continue
            try:
                self._check_card(cleanup=True, cleanup_deadline=end)
                value = self._request("a2a", "CancelTask", {"id": ref["task_id"]}, cleanup=True, cleanup_deadline=end)
                observed = self._task(value, ref)
                self._resolve_delivery()
                cleanup.append({"outcome": observed["state"], "remoteOutcome": "Completed"})
            except HostError as exc:
                self._resolve_delivery(exc.remote)
                cleanup.append({"outcome": exc.code, "remoteOutcome": exc.remote})
        if not isinstance(application_result, dict) or not text(application_result.get("outcome")):
            application_result = {"outcome": "ProtocolRejected", "remoteOutcome": "NotStarted", "fatal": False}
        with self._lock:
            result = copy.deepcopy(self.fatal or application_result)
            self.refs.clear()
            self._event("publication", outcome=result["outcome"], success=result["outcome"] == "Success")
            self.finished = {"result": result, "cleanup": cleanup, "trace": copy.deepcopy(self.trace)}
            return copy.deepcopy(self.finished)
