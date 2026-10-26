"""Shared guarded host for both language arms; no Meda-specific enforcement.

This small loopback experiment is not a production security boundary, real
OAuth, MCP/A2A conformance, or the proposed Meda effect/resource runtime.
"""
from __future__ import annotations

from dataclasses import dataclass
import http.client
import json
import pathlib
import select
import subprocess
import sys
from urllib.parse import urlsplit


ACTIONS = frozenset(("read", "submit", "poll", "continue", "cancel"))
FIELDS = frozenset(("kind", "tenant", "taskId", "input"))
METHODS = {"read": "tools/call", "submit": "message/send", "poll": "tasks/get",
           "continue": "tasks/continue", "cancel": "tasks/cancel"}


def observation(kind: str, code: str = "", task_id: str = "", value: str = "") -> dict:
    return {"kind": kind, "taskId": task_id, "value": value, "code": code}


class FixturePeer:
    """Separate Python process, actual HTTP socket, independently stored tasks."""
    def __init__(self, mode: str = "normal"):
        self.mode = mode
        self.process = None
        self.url = ""

    def __enter__(self):
        self.process = subprocess.Popen(
            [sys.executable, str(pathlib.Path(__file__).with_name("peer.py")),
             "--mode", self.mode], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True,
        )
        ready, _, _ = select.select([self.process.stdout], [], [], 5)
        if not ready:
            self.__exit__(None, None, None)
            raise RuntimeError("Fixture peer startup timed out")
        self.url = self.process.stdout.readline().strip()
        if not self.url.startswith("http://127.0.0.1:"):
            self.__exit__(None, None, None)
            raise RuntimeError("Fixture peer did not start")
        return self

    def stats(self) -> dict:
        target = urlsplit(self.url)
        connection = http.client.HTTPConnection(target.hostname, target.port, timeout=2)
        try:
            connection.request("GET", "/__stats")
            response = connection.getresponse()
            if response.status != 200:
                raise RuntimeError("Fixture stats failed")
            return json.loads(response.read(262144))
        finally:
            connection.close()

    def __exit__(self, *_args):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
            self.process.stdout.close()
            self.process.stderr.close()


@dataclass(frozen=True)
class Grant:
    principal: str
    tenant: str
    allowed_ops: frozenset[str]


class GuardedHost:
    """One local root with fixed authority and endpoint.

    execute action: {kind: read|submit|poll|continue|cancel, tenant, taskId, input}
    result: {kind, taskId, value, code}; result kinds are evidence, pending,
    input_required, completed, cancelled, denied, invalid, unknown, budget.

    Root quota counts every dispatched request, including unknown outcomes.
    max_bytes bounds each wire response; it is not a remote spend guarantee.
    A host close stops future admission, not the separately owned remote tasks.
    """
    def __init__(self, peer: FixturePeer | str, principal: str = "alice",
                 tenant: str = "team-a", max_calls: int = 8,
                 max_bytes: int = 4096, allowed_ops=None, root_id: str = "root-1",
                 timeout: float = 2.0):
        self.url = peer.url if isinstance(peer, FixturePeer) else peer
        target = urlsplit(self.url)
        if target.scheme != "http" or target.hostname != "127.0.0.1" or target.path != "/rpc":
            raise ValueError("Only the explicit loopback fixture endpoint is supported")
        if (isinstance(max_calls, bool) or not isinstance(max_calls, int) or max_calls < 0
                or isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 64):
            raise ValueError("Invalid local limits")
        ops = frozenset(ACTIONS if allowed_ops is None else allowed_ops)
        if not ops <= ACTIONS or not principal or not tenant or timeout <= 0:
            raise ValueError("Invalid local grant")
        self.grant = Grant(principal, tenant, ops)
        self.max_calls, self.max_bytes = max_calls, max_bytes
        self.timeout, self.root_id = timeout, root_id
        self.dispatches = 0
        self.trace: list[dict] = []
        self.closed = False

    def close(self):
        self.closed = True

    def execute(self, action: dict) -> dict:
        if self.closed:
            return self._record(observation("denied", "RootClosed"))
        if (not isinstance(action, dict) or set(action) != FIELDS
                or any(not _valid_text(value) for value in action.values())):
            return self._record(observation("invalid", "InvalidAction"))
        kind = action["kind"]
        if kind not in ACTIONS:
            return self._record(observation("invalid", "UnsupportedAction"))
        if action["tenant"] != self.grant.tenant or kind not in self.grant.allowed_ops:
            return self._record(observation("denied", "AuthorityDenied"))
        if len(action["input"].encode("utf-8")) > 1024 or len(action["taskId"]) > 128:
            return self._record(observation("invalid", "InputLimit"))
        if kind in ("read", "submit") and action["taskId"]:
            return self._record(observation("invalid", "UnexpectedTaskId"))
        if kind in ("poll", "continue", "cancel") and not action["taskId"]:
            return self._record(observation("invalid", "MissingTaskId"))
        if kind == "continue" and not action["input"]:
            return self._record(observation("invalid", "MissingInput"))
        if self.dispatches >= self.max_calls:
            return self._record(observation("budget", "CallLimit"))
        self.dispatches += 1  # Charge before possible transmission. Never retry.
        request_id = self.dispatches
        self.trace.append({"event": "dispatch", "root": self.root_id,
                           "request": request_id, "action": kind})
        request = {"jsonrpc": "2.0", "id": request_id, "method": METHODS[kind],
                   "params": {"taskId": action["taskId"], "input": action["input"]}}
        target = urlsplit(self.url)
        connection = http.client.HTTPConnection(target.hostname, target.port, timeout=self.timeout)
        try:
            connection.request("POST", target.path, json.dumps(request).encode(),
                               {"Content-Type": "application/json",
                                "X-Fixture-Principal": self.grant.principal,
                                "X-Fixture-Tenant": self.grant.tenant})
            response = connection.getresponse()
            raw = response.read(self.max_bytes + 1)
            if len(raw) > self.max_bytes:
                return self._record(observation("invalid", "ResponseLimit"))
            try:
                result = json.loads(raw, object_pairs_hook=_unique_object)
            except (ValueError, UnicodeError):
                return self._record(observation("invalid", "MalformedPeerData"))
            if (not isinstance(result, dict) or result.get("jsonrpc") != "2.0"
                    or type(result.get("id")) is not int or result["id"] != request_id):
                return self._record(observation("invalid", "InvalidEnvelope"))
            if "error" in result:
                if set(result) != {"jsonrpc", "id", "error"} or not isinstance(result["error"], dict):
                    return self._record(observation("invalid", "InvalidEnvelope"))
                code = result["error"].get("code")
                if code == "Denied":
                    return self._record(observation("denied", "PeerDenied"))
                return self._record(observation("invalid", "PeerRejected"))
            if response.status != 200 or set(result) != {"jsonrpc", "id", "result"}:
                return self._record(observation("invalid", "InvalidEnvelope"))
            return self._record(self._decode(kind, action["taskId"], result["result"]))
        except (OSError, http.client.HTTPException):
            # This fixture cannot prove non-dispatch after transport exceptions.
            return self._record(observation("unknown", "DeliveryUnknown"))
        finally:
            connection.close()

    def _decode(self, action: str, expected_task: str, result) -> dict:
        if action == "read":
            if (not isinstance(result, dict) or set(result) != {"resultType", "structuredContent"}
                    or result["resultType"] != "complete"
                    or not isinstance(result["structuredContent"], dict)
                    or set(result["structuredContent"]) != {"value"}
                    or not _valid_text(result["structuredContent"]["value"])):
                return observation("invalid", "InvalidPeerData")
            return observation("evidence", value=result["structuredContent"]["value"])
        if (not isinstance(result, dict) or set(result) != {"id", "status", "artifacts"}
                or not _valid_text(result["id"]) or not result["id"] or len(result["id"]) > 128
                or (expected_task and result["id"] != expected_task)
                or not isinstance(result["status"], dict) or set(result["status"]) != {"state"}
                or not isinstance(result["artifacts"], list)):
            return observation("invalid", "InvalidPeerData")
        mapping = {"working": "pending", "input-required": "input_required",
                   "completed": "completed", "canceled": "cancelled"}
        state = result["status"]["state"]
        if not isinstance(state, str) or state not in mapping:
            return observation("invalid", "InvalidPeerData")
        artifacts = result["artifacts"]
        value = ""
        if state == "completed":
            if (len(artifacts) != 1 or not isinstance(artifacts[0], dict)
                    or set(artifacts[0]) != {"text"} or not _valid_text(artifacts[0]["text"])):
                return observation("invalid", "InvalidPeerData")
            value = artifacts[0]["text"]
        elif artifacts:
            return observation("invalid", "InvalidPeerData")
        return observation(mapping[state], task_id=result["id"], value=value)

    def _record(self, result):
        # Metadata-only: no request payload, returned content, identity headers.
        self.trace.append({"event": "observation", "root": self.root_id,
                           "kind": result["kind"], "code": result["code"]})
        return result


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _valid_text(value):
    if not isinstance(value, str):
        return False
    try:
        value.encode("utf-8")
    except UnicodeError:
        return False
    return True
