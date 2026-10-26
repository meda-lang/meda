"""Deterministic application peers served by the pinned upstream MCP/A2A SDKs.

The authentication registry is a local test profile, not an OAuth implementation.
Wire decoding, transport metadata, dispatch and serialization belong to the SDKs.
"""
from __future__ import annotations

import argparse
import asyncio
import contextvars
import copy
import json
import time
from pathlib import Path
from typing import Annotated, Any

from google.protobuf.json_format import MessageToDict, ParseDict
from pydantic import BaseModel, ConfigDict, Field
from starlette.applications import Starlette
from starlette.responses import JSONResponse

from mcp.server.mcpserver import MCPServer, Context
from mcp.server.transport_security import TransportSecuritySettings
from a2a.server.context import ServerCallContext
from a2a.server.request_handlers.request_handler import RequestHandler
from a2a.server.request_handlers.response_helpers import agent_card_to_dict
from a2a.server.routes.agent_card_routes import create_agent_card_routes
from a2a.server.routes.common import DefaultServerCallContextBuilder
from a2a.server.routes.jsonrpc_routes import create_jsonrpc_routes
from a2a.types import a2a_pb2 as proto
from a2a.utils.errors import (
    InvalidParamsError, TaskNotCancelableError, TaskNotFoundError,
    UnsupportedOperationError,
)

EVIDENCE = {"documentId": "evidence-42", "revision": 1,
            "facts": [{"id": "f1", "value": "blue"}, {"id": "f2", "value": "square"}]}
IDENTITY: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar("d0_peer_identity")


class Fact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    value: str


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    documentId: str
    revision: int
    facts: list[Fact]


def witness(config: dict[str, Any], event: str, **fields: Any) -> None:
    """Write explicitly selected synthetic observations, never headers/tokens."""
    path = config.get("witness_path")
    if path:
        with Path(path).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"event": event, **fields}, sort_keys=True) + "\n")


class AuthBoundary:
    """Authenticate the transport and authorize the requested fixture operation.

    The small JSON inspection chooses a grant only. The upstream SDK still parses,
    validates and dispatches the original bytes. Malformed input reaches its parser.
    """
    def __init__(self, app: Any, config: dict[str, Any]):
        self.app, self.config = app, config

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin1").lower(): v.decode("latin1")
                   for k, v in scope["headers"]}
        token = headers.get("authorization", "")
        token = token[7:] if token.startswith("Bearer ") else ""
        identity = next((r for r in self.config["credentials"] if r["token"] == token), None)
        if (not identity or identity.get("audience") != self.config["protocol"]
                or identity.get("expires_at", 0) <= time.time()):
            witness(self.config, "denied", reason="credential")
            await JSONResponse({"error": "Unauthorized"}, status_code=401,
                               headers={"WWW-Authenticate": "Bearer"})(scope, receive, send)
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > 65536:
                await JSONResponse({"error": "RequestLimit"}, status_code=413)(scope, receive, send)
                return
            if not message.get("more_body", False):
                break
        method, operation = "GET", "discover"
        if scope["method"] == "POST":
            try:
                payload = json.loads(body)
                method = payload.get("method", "invalid")
                params = payload.get("params") or {}
                operation = {"server/discover": "discover", "tools/list": "discover",
                             "tools/call": "readEvidence", "GetTask": "observe",
                             "CancelTask": "cancel"}.get(method, "unsupported")
                if method == "SendMessage":
                    msg = params.get("message") or {}
                    operation = "provideInput" if msg.get("taskId") else "submit"
            except (ValueError, AttributeError, TypeError):
                operation = "invalid"
        # Unknown methods get a normal SDK method error; they cannot execute work.
        if operation not in {"invalid", "unsupported"} and operation not in identity["operations"]:
            witness(self.config, "denied", reason="grant", operation=operation)
            await JSONResponse({"error": "Forbidden"}, status_code=403)(scope, receive, send)
            return
        scope["d0_identity"] = {k: identity[k] for k in ("principal", "tenant")}
        reset = IDENTITY.set(scope["d0_identity"])
        delivered = False

        async def replay() -> dict:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        witness(self.config, "request", method=method, operation=operation,
                principal=identity["principal"], tenant=identity["tenant"])
        try:
            await self.app(scope, replay, send)
        finally:
            IDENTITY.reset(reset)


def create_mcp_server(config: dict[str, Any]) -> MCPServer:
    server = MCPServer("meda-d0-evidence", version="1.0.0", subscriptions=False)

    async def evidence_read(documentId: Annotated[str, Field(json_schema_extra={"x-mcp-header": "DocumentId"})], ctx: Context) -> Evidence:
        if documentId != "evidence-42":
            raise ValueError("DocumentUnavailable")
        witness(config, "evidence_read", documentId=documentId)
        scenario = config.get("scenario", "happy")
        if scenario == "live_progress":
            # Exercise the SDK's real request-scoped SSE and disconnect watcher.
            # A completed or server-shutdown run must not be mistaken for the
            # independent test's before-shutdown cancellation observation.
            completed = False
            witness(config, "stream_started")
            try:
                for index in range(400):
                    await ctx.report_progress(index, 400)
                    await asyncio.sleep(.05)
                completed = True
            except asyncio.CancelledError:
                witness(config, "stream_cancelled")
                raise
            finally:
                witness(config, "stream_terminated", completed=completed)
        elif not config.get("json_response", True):
            await ctx.report_progress(1, 1)
        if scenario == "tool_error":
            raise ValueError("SyntheticToolError")
        result = copy.deepcopy(EVIDENCE)
        if scenario == "wrong_document":
            result["documentId"] = "other-document"
        elif scenario == "duplicate_fact":
            result["facts"][1]["id"] = "f1"
        elif scenario == "oversized_evidence":
            result["facts"][0]["value"] = "x" * 70000
        elif scenario == "slow_evidence":
            await asyncio.sleep(3)
        return Evidence.model_validate(result)

    server.add_tool(evidence_read, name="evidence.read",
                    description="Read the fixed synthetic evidence document.", structured_output=True)
    return server


def build_tool_descriptor() -> dict[str, Any]:
    """Freeze the actual public SDK-generated descriptor, not a lookalike schema."""
    server = create_mcp_server({})
    tools = asyncio.run(server.list_tools())
    return tools[0].model_dump(by_alias=True, exclude_none=True)


def _agent_card(endpoint: str) -> proto.AgentCard:
    return ParseDict({
        "name": "Meda D0 deterministic report agent",
        "description": "Select supplied evidence facts without a model.",
        "version": "1.0.0",
        "supportedInterfaces": [{"url": endpoint, "protocolBinding": "JSONRPC", "protocolVersion": "1.0"}],
        "capabilities": {"streaming": False, "pushNotifications": False},
        "defaultInputModes": ["application/json"], "defaultOutputModes": ["application/json"],
        "securitySchemes": {"fixtureBearer": {"httpAuthSecurityScheme": {"scheme": "bearer"}}},
        "securityRequirements": [{"schemes": {"fixtureBearer": {"list": []}}}],
        "skills": [{"id": "evidence-report", "name": "Evidence report",
                    "description": "Return the selected evidence in request order.", "tags": ["fixture"]}],
    }, proto.AgentCard())


def build_agent_card(endpoint: str) -> dict[str, Any]:
    return agent_card_to_dict(_agent_card(endpoint))


class FixtureContextBuilder(DefaultServerCallContextBuilder):
    def build(self, request: Any) -> ServerCallContext:
        context = super().build(request)
        context.state["identity"] = request.scope["d0_identity"]
        context.tenant = request.scope["d0_identity"]["tenant"]
        return context


class ReportHandler(RequestHandler):
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.tasks: dict[str, dict[str, Any]] = {}

    @staticmethod
    def owner(context: ServerCallContext) -> tuple[str, str]:
        identity = context.state["identity"]
        return identity["principal"], identity["tenant"]

    def owned(self, task_id: str, context: ServerCallContext) -> dict[str, Any]:
        task = self.tasks.get(task_id)
        if not task or task["owner"] != self.owner(context):
            witness(self.config, "task_access_denied", taskId=task_id)
            raise TaskNotFoundError()
        return task

    def response(self, task: dict[str, Any]) -> proto.Task:
        result = {"id": task["id"], "contextId": task["contextId"],
                  "status": {"state": task["state"]}}
        if task["state"] == "TASK_STATE_COMPLETED":
            evidence = task["evidence"]
            facts = {v["id"]: v["value"] for v in evidence["facts"]}
            report = {"documentId": evidence["documentId"], "revision": evidence["revision"],
                      "selected": [{"id": i, "value": facts[i]} for i in task["includeIds"]]}
            if self.config.get("scenario") == "domain_wrong":
                report["selected"][0]["value"] = "invented"
            result["artifacts"] = [{"artifactId": "report-1", "parts": [{"data": report}]}]
        return ParseDict(result, proto.Task())

    async def on_message_send(self, params: proto.SendMessageRequest, context: ServerCallContext) -> proto.Task | proto.Message:
        message = MessageToDict(params.message)
        parts = message.get("parts", [])
        if len(parts) != 1 or not isinstance(parts[0].get("data"), dict):
            raise InvalidParamsError()
        data = parts[0]["data"]
        scenario = self.config.get("scenario", "happy")
        if message.get("taskId"):
            task = self.owned(message["taskId"], context)
            if message.get("contextId") not in (None, task["contextId"]):
                raise InvalidParamsError()
            if task["state"] != "TASK_STATE_INPUT_REQUIRED":
                raise UnsupportedOperationError()
            ids = data.get("includeIds")
            if not isinstance(ids, list) or any(i not in {"f1", "f2"} for i in ids):
                raise InvalidParamsError()
            task["includeIds"] = ids
            task["state"] = "TASK_STATE_COMPLETED"
            witness(self.config, "continued", taskId=task["id"], includeIds=ids)
            return self.response(task)
        if scenario == "direct_reply":
            return ParseDict({"messageId": "reply-1", "role": "ROLE_AGENT",
                              "parts": [{"text": "This is a direct reply."}]}, proto.Message())
        if data.get("kind") != "evidence-report" or data.get("evidence") != EVIDENCE:
            raise InvalidParamsError()
        ids = data.get("includeIds")
        if ids is not None and (not isinstance(ids, list) or any(i not in {"f1", "f2"} for i in ids)):
            raise InvalidParamsError()
        count = len(self.tasks) + 1
        state = "TASK_STATE_INPUT_REQUIRED" if ids is None else "TASK_STATE_WORKING"
        state = {"submitted": "TASK_STATE_SUBMITTED", "auth_required": "TASK_STATE_AUTH_REQUIRED",
                 "remote_failed": "TASK_STATE_FAILED", "remote_rejected": "TASK_STATE_REJECTED",
                 "remote_canceled": "TASK_STATE_CANCELED", "immediate_complete": "TASK_STATE_COMPLETED",
                 "unknown_state": 99}.get(scenario, state)
        task = {"id": f"task-{count}", "contextId": f"context-{count}", "state": state,
                "owner": self.owner(context), "evidence": data["evidence"],
                "includeIds": ids or [], "polls": 0}
        self.tasks[task["id"]] = task
        witness(self.config, "created", taskId=task["id"], contextId=task["contextId"],
                principal=task["owner"][0], tenant=task["owner"][1])
        return self.response(task)

    async def on_get_task(self, params: proto.GetTaskRequest, context: ServerCallContext) -> proto.Task:
        task = self.owned(params.id, context)
        task["polls"] += 1
        if task["state"] in ("TASK_STATE_WORKING", "TASK_STATE_SUBMITTED") and self.config.get("scenario") != "pending":
            task["state"] = "TASK_STATE_COMPLETED"
        witness(self.config, "observed", taskId=params.id, state=task["state"])
        return self.response(task)

    async def on_cancel_task(self, params: proto.CancelTaskRequest, context: ServerCallContext) -> proto.Task:
        task = self.owned(params.id, context)
        if self.config.get("scenario") == "completion_before_cancel" and task["state"] in {"TASK_STATE_WORKING", "TASK_STATE_SUBMITTED"}:
            task["state"] = "TASK_STATE_COMPLETED"
            witness(self.config, "completed_before_cancel", taskId=params.id)
        if task["state"] in {"TASK_STATE_COMPLETED", "TASK_STATE_FAILED", "TASK_STATE_REJECTED", "TASK_STATE_CANCELED"}:
            witness(self.config, "cancel_refused", taskId=params.id)
            raise TaskNotCancelableError()
        task["state"] = "TASK_STATE_CANCELED"
        witness(self.config, "canceled", taskId=params.id)
        return self.response(task)

    async def unsupported(self, params: Any, context: ServerCallContext) -> Any:
        raise UnsupportedOperationError()

    on_list_tasks = unsupported
    on_create_task_push_notification_config = unsupported
    on_get_task_push_notification_config = unsupported
    on_list_task_push_notification_configs = unsupported
    on_delete_task_push_notification_config = unsupported
    on_get_extended_agent_card = unsupported

    async def on_message_send_stream(self, params: Any, context: ServerCallContext):
        raise UnsupportedOperationError()
        yield  # Mark the unsupported interface as an async generator.

    on_subscribe_to_task = on_message_send_stream


def build_app(config: dict[str, Any]) -> Any:
    if config["protocol"] == "mcp":
        server = create_mcp_server(config)
        security = TransportSecuritySettings(enable_dns_rebinding_protection=True,
                    allowed_hosts=["127.0.0.1:*", "localhost:*"],
                    allowed_origins=[f"https://127.0.0.1:{config['port']}"])
        app = server.streamable_http_app(streamable_http_path="/mcp",
                    json_response=config.get("json_response", True),
                    transport_security=security, max_request_body_size=65536)
    elif config["protocol"] == "a2a":
        endpoint = config.get("public_url", config.get("advertised_url", f"https://127.0.0.1:{config['port']}/a2a"))
        handler = ReportHandler(config)
        routes = create_agent_card_routes(_agent_card(endpoint))
        routes += create_jsonrpc_routes(handler, "/a2a", context_builder=FixtureContextBuilder(),
                                        enable_v0_3_compat=False)
        app = Starlette(routes=routes)
    else:
        raise ValueError("Unknown protocol")
    return AuthBoundary(app, config)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    import uvicorn
    uvicorn.run(build_app(config), host="127.0.0.1", port=config["port"],
                ssl_certfile=config["cert_file"], ssl_keyfile=config["key_file"],
                log_level="error", access_log=False, timeout_graceful_shutdown=1)


if __name__ == "__main__":
    main()
