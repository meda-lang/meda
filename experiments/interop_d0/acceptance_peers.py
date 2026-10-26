"""Raw, outside-in peer probes for the independent D0 acceptance oracle.

No case expectations or verdicts enter this module. Requests go through verified
local TLS to the actual SDK peers. The receipt retains setup observations and
marks the measured interval with half-open offsets; it does not pretend these
direct probes passed through the shared host.
"""
from __future__ import annotations

import copy
import http.client
import importlib.metadata
import json
import secrets
import ssl
import time
from urllib.parse import urlsplit

from mcp.types import DiscoverResult, JSONRPCError, JSONRPCResponse

try:
    from . import runner, support
    from .sdk_peers import EVIDENCE
except ImportError:
    import runner
    import support
    from sdk_peers import EVIDENCE


VERSION = "2026-07-28"
MAX_RESPONSE = 65_536
WIRE_MUTATIONS = {"version_header_body", "method_header_body", "name_header_body"}
CREDENTIAL_VARIANTS = {"missing", "expired", "wrong_audience", "invalid"}


def _schema(method, body):
    """Record a real SDK schema check, separately from the oracle's verdict."""
    if not isinstance(body, dict):
        return {"schemaName": None, "accepted": None}
    if "error" in body and body.get("jsonrpc") == "2.0":
        model, value = JSONRPCError, body
    elif method == "server/discover" and "result" in body:
        model, value = DiscoverResult, body["result"]
    elif body.get("jsonrpc") == "2.0" and "result" in body:
        model, value = JSONRPCResponse, body
    else:
        return {"schemaName": None, "accepted": None}
    result = {"schemaName": "mcp.types." + model.__name__}
    try:
        model.model_validate(value)
        result["accepted"] = True
    except (ValueError, TypeError) as error:
        result.update(accepted=False, error=type(error).__name__)
    return result


def _request(env, requests, protocol, method, params, *, credential="valid", headers=None, stage="case"):
    endpoint = env["host"].config.mcp_url if protocol == "mcp" else env["host"].config.a2a_url
    target = urlsplit(endpoint)
    request_id = "peer-probe-" + str(len(requests) + 1)
    params = copy.deepcopy(params)
    routing = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if protocol == "mcp":
        params["_meta"] = {"io.modelcontextprotocol/protocolVersion": VERSION,
                           "io.modelcontextprotocol/clientInfo": {"name": "meda-d0-peer-probe", "version": "1"},
                           "io.modelcontextprotocol/clientCapabilities": {}, "progressToken": request_id}
        routing.update({"MCP-Protocol-Version": VERSION, "Mcp-Method": method})
        if method == "tools/call":
            routing.update({"Mcp-Name": params["name"], "Mcp-Param-DocumentId": params["arguments"]["documentId"]})
    else:
        routing["A2A-Version"] = "1.0"
    routing.update(headers or {})
    outgoing = dict(routing)
    if credential != "missing":
        if credential == "invalid":
            token = secrets.token_urlsafe(32)
            env["secrets"].append(token)
        else:
            token = next(row["token"] for row in env["credentials"][protocol] if row["label"] == credential)
        outgoing["Authorization"] = "Bearer " + token
    envelope = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
    encoded = json.dumps(envelope, separators=(",", ":")).encode()
    connection = http.client.HTTPSConnection(target.hostname, target.port, timeout=4,
        context=ssl.create_default_context(cafile=env["certificates"]["ca_file"]))
    started = time.monotonic()
    operation = {"server/discover": "discover", "tools/call": "readEvidence",
                 "SendMessage": "submit", "GetTask": "observe"}[method]
    record = {"protocol": protocol, "method": method, "operation": operation,
              "stage": stage, "credentialLabel": credential, "requestId": request_id,
              "request": envelope, "routingHeaders": routing, "requestBytes": len(encoded)}
    requests.append(record)
    response = None
    try:
        connection.request("POST", target.path, encoded, outgoing)
        record["dispatched"] = True
        response = connection.getresponse()
        raw = response.read(MAX_RESPONSE + 1)
        record.update(status=response.status, mediaType=response.getheader("Content-Type", ""),
                      responseBytes=len(raw), responseTruncated=len(raw) > MAX_RESPONSE,
                      authenticateHeader=response.getheader("WWW-Authenticate"))
        text = raw[:MAX_RESPONSE].decode("utf-8", errors="replace")
        record["rawBody"] = text
        try:
            record["body"] = json.loads(text)
        except ValueError:
            record["body"] = None
        record["schemaValidation"] = _schema(method, record["body"])
    except (OSError, http.client.HTTPException) as error:
        record["transportError"] = type(error).__name__
    finally:
        if response is not None:
            response.close()
        connection.close()
        record["elapsedSeconds"] = time.monotonic() - started
    return record


def _offsets(env, requests):
    return {"requests": len(requests), "trace": 0,
            "peers": {protocol: len(support.read_witness(path)) for protocol, path in env["witness_paths"].items()},
            "proxy": {protocol: len(proxy.events) for protocol, proxy in env["proxies"].items()}}


def _window(start, end):
    return {key: ({protocol: {"start": start[key][protocol], "end": end[key][protocol]}
                   for protocol in ("mcp", "a2a")} if key in {"peers", "proxy"}
                 else {"start": start[key], "end": end[key]}) for key in start}


def probe_in_environment(scenario, env):
    """Execute a supported stimulus and return observations, never expectations."""
    requests = []
    operation = scenario.get("operation")
    mutation, credential = scenario.get("wireMutation"), scenario.get("credentialVariant")
    task_id = None
    if scenario.get("setup") == "foreign_principal_task" and operation == "observe":
        setup = _request(env, requests, "a2a", "SendMessage", {
            "message": {"messageId": "foreign-setup-message", "role": "ROLE_USER",
                        "parts": [{"data": {"kind": "evidence-report", "evidence": EVIDENCE,
                                             "includeIds": ["f1", "f2"]}}]},
            "configuration": {"returnImmediately": True}}, credential="foreign", stage="setup")
        body = setup.get("body") or {}
        task_id = body.get("result", {}).get("task", {}).get("id")
        if not isinstance(task_id, str):
            raise RuntimeError("Actual SDK did not return a task for the peer-probe setup")
    elif operation == "readEvidence" and (mutation in WIRE_MUTATIONS or credential in CREDENTIAL_VARIANTS):
        pass
    elif operation == "server/discover" and scenario.get("requestedVersion") == VERSION:
        pass
    else:
        raise runner.UnsupportedScenario("Unsupported direct SDK peer probe")
    start = _offsets(env, requests)
    if task_id is not None:
        _request(env, requests, "a2a", "GetTask", {"id": task_id})
    elif operation == "server/discover":
        _request(env, requests, "mcp", "server/discover", {})
    else:
        overrides = {"version_header_body": {"MCP-Protocol-Version": "2025-11-25"},
                     "method_header_body": {"Mcp-Method": "tools/list"},
                     "name_header_body": {"Mcp-Name": "different.tool"}}.get(mutation, {})
        _request(env, requests, "mcp", "tools/call", {"name": "evidence.read",
            "arguments": {"documentId": "evidence-42"}}, credential=credential or "valid", headers=overrides)
    end = _offsets(env, requests)
    result = {"probe": {"kind": "peer_request", "transport": "verified_local_tls",
                        "sdkVersions": {"mcp": importlib.metadata.version("mcp"),
                                        "a2a-sdk": importlib.metadata.version("a2a-sdk")}},
              "requests": requests, "trace": [], "measuredWindow": _window(start, end),
              "peers": {protocol: support.read_witness(path) for protocol, path in env["witness_paths"].items()},
              "proxy": {protocol: copy.deepcopy(proxy.events) for protocol, proxy in env["proxies"].items()},
              "witnessesCapturedBeforePeerShutdown": all(process.poll() is None for process in env["peer_processes"].values())}
    serialized = json.dumps(result, ensure_ascii=False)
    result["credentialLeakDetected"] = any(secret in serialized for secret in env["secrets"])
    return runner._scrub(result, env["secrets"])


def execute_peer_probe(scenario):
    """Public entrypoint matching runner.execute_workflow's stimulus-only API."""
    with runner.environment(scenario) as env:
        result = probe_in_environment(scenario, env)
    result["peerProcessesRetired"] = all(process.poll() is not None for process in env["peer_processes"].values())
    return result
