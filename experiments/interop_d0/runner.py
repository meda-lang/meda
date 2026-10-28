"""Outside-in local SDK/TypeScript development runner, not an acceptance oracle.

The trusted controller owns credentials and the Host. Node receives only workflow
inputs and typed operation results. RSS/deadline supervision is exercised here;
this is not a hardened filesystem/network sandbox for adversarial JavaScript.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

try:
    from .host import Host, HostConfig, Limits, OPERATIONS
    from . import support
except ImportError:
    from host import Host, HostConfig, Limits, OPERATIONS
    import support

HERE = Path(__file__).resolve().parent

from meda_runtime.supervisor import (
    MAX_LINE, MAX_RSS, _safe_environment, _rss, _kill, _run_process,
    _finish_count, _channel_scan, _scrub,
)



class UnsupportedScenario(ValueError):
    """A planned case lacks its actual implementation; never count it as passed."""


def _node():
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("Node.js is required")
    return node


def compile_client():
    """Compile pinned TypeScript under the documented local supervisor limits."""
    if not Path("/proc/self/status").is_file():
        raise RuntimeError("RSS supervision requires Linux /proc in this profile")
    compiler = HERE / "node_modules/typescript/bin/tsc"
    package = HERE / "node_modules/typescript/package.json"
    if not compiler.is_file() or json.loads(package.read_text())["version"] != "5.9.3":
        raise RuntimeError("Install the pinned TypeScript dependency with npm ci")
    with tempfile.TemporaryFile() as output:
        process = subprocess.Popen([_node(), "--max-old-space-size=96", str(compiler),
                                    "-p", str(HERE / "tsconfig.json")], cwd=HERE,
                                   stdout=output, stderr=subprocess.STDOUT,
                                   env=_safe_environment(), start_new_session=True)
        start, peak = time.monotonic(), 0
        try:
            while process.poll() is None:
                peak = max(peak, _rss(process.pid))
                if peak > MAX_RSS or time.monotonic() - start >= 10:
                    _kill(process)
                    raise RuntimeError("TypeScript compilation exceeded its supervised limit: " +
                                       json.dumps({"peakRssBytesObserved": peak,
                                                   "elapsedSeconds": time.monotonic() - start}))
                time.sleep(.02)
            if process.returncode:
                output.seek(0)
                raise RuntimeError("TypeScript compilation failed: " + output.read(2048).decode(errors="replace"))
        finally:
            if process.poll() is None:
                _kill(process)
        return {"compiler": "TypeScript", "version": "5.9.3", "passed": True,
                "peakRssBytesObserved": peak, "elapsedSeconds": time.monotonic() - start,
                "sourceStrict": True, "dependencyDeclarationChecks": "skipped",
                "lib": ["ES2022"], "v8OldSpaceMiB": 96,
                "rssLimitBytes": MAX_RSS, "wallLimitSeconds": 10}


def _limits(scenario):
    values = {}
    aliases = {"maxInboundBytes": "max_inbound_bytes", "sseEvents": "max_events",
               "maxResponseBytes": "max_response_bytes", "maxRequests": "max_requests"}
    for key, value in scenario.get("limits", {}).items():
        if key == "normalRequests":
            values["max_requests"] = value + Limits().cleanup_requests
        elif key == "rootWorkMs":
            values["root_seconds"] = value / 1000
        elif key == "requestMs":
            values["request_seconds"] = value / 1000
        elif key in aliases:
            values[aliases[key]] = value
        elif key in Limits.__dataclass_fields__:
            values[key] = value
        else:
            raise UnsupportedScenario("Unsupported resource override: " + key)
    if scenario.get("barrier") == "zero_normal_allowance_after_final_receive":
        values["max_requests"] = 8  # Six normal requests plus the two cleanup reservations.
    if scenario.get("barrier") == "abort_with_zero_normal_allowance":
        values["max_requests"] = 6  # Read and submit each require discovery plus business RPC.
    return Limits(**values)


def _peer_scenario(scenario, protocol):
    if protocol == "mcp":
        if scenario.get("resourceFault") == "periodic_progress" or scenario.get("barrier") == "abort_during_evidence_stream":
            return "live_progress"
        return "happy"  # Wire/data faults belong to the external proxy.
    if scenario.get("a2aResponse") == "Message":
        return "direct_reply"
    if scenario.get("cancelResponse") == "TaskNotCancelableError":
        return "completion_before_cancel"
    states = scenario.get("a2aStates", ["WORKING", "COMPLETED"])
    if states and len(states) > 1 and all(state == "WORKING" for state in states):
        return "pending"
    return {"SUBMITTED": "submitted", "AUTH_REQUIRED": "auth_required",
            "COMPLETED": "immediate_complete", "FAILED": "remote_failed",
            "CANCELED": "remote_canceled", "REJECTED": "remote_rejected",
            "UNKNOWN": "unknown_state", "UNSPECIFIED": "unknown_state"}.get(states[0], "happy")


def workflow_input(scenario):
    result = {}
    if "documentId" in scenario:
        result["documentId"] = scenario["documentId"]
    if "initialIncludeIds" in scenario:
        if scenario["initialIncludeIds"] is None:
            result["requestClarification"] = True
        else:
            result["includeIds"] = scenario["initialIncludeIds"]
    if scenario.get("suppliedIncludeIds") is not None:
        result["suppliedInput"] = scenario["suppliedIncludeIds"]
    if scenario.get("applicationAction") == "cancel":
        result["cancelAfterSubmit"] = True
    return result


@contextlib.contextmanager
def environment(scenario):
    """Yield trusted fixture controls; none of this dictionary reaches Node."""
    try:
        from .fault_proxy import FaultProxy
        from .sdk_peers import build_agent_card, build_tool_descriptor
    except ImportError:
        from fault_proxy import FaultProxy
        from sdk_peers import build_agent_card, build_tool_descriptor
    with tempfile.TemporaryDirectory(prefix="meda-d0-run-") as directory:
        directory = Path(directory)
        certs = support.certificates(directory)
        ports = []
        while len(ports) < 4:
            candidate = support.free_port()
            if candidate not in ports:
                ports.append(candidate)
        credentials = {protocol: support.credentials(protocol) for protocol in ("mcp", "a2a")}
        secrets = [entry["token"] for rows in credentials.values() for entry in rows]
        endpoints = {"mcp": f"https://127.0.0.1:{ports[2]}/mcp",
                     "a2a": f"https://127.0.0.1:{ports[3]}/a2a"}
        configs, witnesses = {}, {}
        for index, protocol in enumerate(("mcp", "a2a")):
            witnesses[protocol] = directory / (protocol + "-witness.jsonl")
            configs[protocol] = {"protocol": protocol, "port": ports[index], **certs,
                "credentials": credentials[protocol], "witness_path": str(witnesses[protocol]),
                "public_url": endpoints[protocol], "scenario": _peer_scenario(scenario, protocol),
                "json_response": scenario.get("mcpResponse", "json") != "sse" and
                    _peer_scenario(scenario, protocol) != "live_progress"}
        proxies = {protocol: FaultProxy(protocol, ports[index + 2], ports[index], certs, scenario)
                   for index, protocol in enumerate(("mcp", "a2a"))}
        with contextlib.ExitStack() as stack:
            processes = {protocol: stack.enter_context(support.peer(configs[protocol], directory))
                         for protocol in ("mcp", "a2a")}
            for proxy in proxies.values():
                stack.enter_context(proxy.serve())
            host = Host(HostConfig(mcp_url=endpoints["mcp"], a2a_url=endpoints["a2a"],
                mcp_token=credentials["mcp"][0]["token"], a2a_token=credentials["a2a"][0]["token"],
                ca_file=certs["ca_file"], tool_descriptor=build_tool_descriptor(),
                agent_card=build_agent_card(endpoints["a2a"]), limits=_limits(scenario)))
            env = {"host": host, "proxies": proxies, "credentials": credentials,
                   "secrets": secrets, "peer_configs": configs, "witness_paths": witnesses,
                   "peer_processes": processes, "certificates": certs, "directory": directory}
            try:
                yield env
            finally:
                if host.finished is None:
                    host.abort("RootTerminated")
                    host.finish({"outcome": "RootTerminated", "fatal": True})


class _ScenarioHooks:
    """Research-only ordering barriers; never packaged with the runtime."""
    def __init__(self, proxies, scenario):
        self.proxies, self.scenario = proxies, scenario

    def monitor(self, terminate, barriers):
        barrier = self.scenario.get("barrier")
        if barrier == "close_before_observation_response" and "a2a" in self.proxies:
            proxy = self.proxies["a2a"]
            if proxy.response_ready.is_set():
                barriers.append("root_closed_before_observation_release")
                terminate("root_abort")
                proxy.release_response.set()
                return True
        if barrier == "abort_during_evidence_stream" and "mcp" in self.proxies:
            if self.proxies["mcp"].stream_started.is_set():
                barriers.append("root_closed_after_stream_started")
                terminate("root_abort")
                return True
        return False

    def after_call(self, operation, value, terminate, barriers):
        if operation == "submit" and value.get("kind") == "Task" and self.scenario.get("barrier") in {
                "abort_after_submit_before_poll", "abort_with_zero_normal_allowance"}:
            barriers.append("root_closed_after_submit_before_source_response")
            terminate("root_abort")

    def after_publication(self, host, barriers):
        if self.scenario.get("barrier") == "publication_before_abort":
            host.abort("RootTerminated")
            barriers.append("publication_committed_before_late_abort")


def run_client(host, input_value, *, proxies=None, scenario=None, worker_path=None,
               credential_sentinels=(), private_receipts=None, worker_command=None):
    """Compatibility adapter for research fixture configuration."""
    worker_path = Path(worker_path or HERE / "dist/main.js")
    if worker_command is None and not worker_path.is_file():
        raise RuntimeError("Compile the TypeScript client before running")
    proxies, scenario = proxies or {}, scenario or {}
    if scenario.get("onMissingInput") == "wait":
        raise UnsupportedScenario("Live input waiting is not implemented in the current client")
    if scenario.get("localCleanup") == "worker_refuses_join":
        raise UnsupportedScenario("A refusal-to-join fault fixture is not implemented")
    supported_barriers = {None, "abort_after_submit_before_poll", "publication_before_abort",
                          "close_before_observation_response", "abort_during_evidence_stream",
                          "zero_normal_allowance_after_final_receive", "root_deadline_before_request_deadline",
                          "abort_with_zero_normal_allowance"}
    if scenario.get("barrier") not in supported_barriers:
        raise UnsupportedScenario("Unsupported ordering barrier")
    command = worker_command or [_node(), "--max-old-space-size=128", str(worker_path)]
    return _run_process(host, input_value, command, cwd=HERE,
                        credential_sentinels=credential_sentinels, private_receipts=private_receipts,
                        _hooks=_ScenarioHooks(proxies, scenario))


def execute_workflow(scenario, *, worker_command=None, worker_path=None):
    with environment(scenario) as env:
        private_receipts = {}
        result = run_client(env["host"], workflow_input(scenario), proxies=env["proxies"], scenario=scenario,
                            credential_sentinels=env["secrets"], private_receipts=private_receipts,
                            worker_command=worker_command, worker_path=worker_path)
        # Observe stream cancellation while the SDK process is still running;
        # its later process shutdown must not manufacture that evidence.
        if env["proxies"]["mcp"].stream_started.is_set():
            end = time.monotonic() + env["host"].limits.cleanup_seconds
            while time.monotonic() < end:
                rows = support.read_witness(env["witness_paths"]["mcp"])
                if any(row.get("event") == "stream_terminated" for row in rows):
                    break
                time.sleep(.01)
        result["peers"] = {protocol: support.read_witness(path)
                           for protocol, path in env["witness_paths"].items()}
        result["proxy"] = {protocol: copy.deepcopy(proxy.events) for protocol, proxy in env["proxies"].items()}
        result["bindingManifest"] = {"mcpUrl": env["host"].config.mcp_url,
            "a2aUrl": env["host"].config.a2a_url,
            "toolDescriptorSha256": env["host"].tool_digest, "agentCardSha256": env["host"].card_digest,
            "limits": asdict(env["host"].limits),
            "protocolPins": {"MCP": "2026-07-28", "A2A": "1.0"}}
        channels = private_receipts["channels"]
        for name, records in (("ordinaryHostTrace", env["host"].trace),
                              ("peerWitnesses", [r for rows in result["peers"].values() for r in rows]),
                              ("proxyWitnesses", [r for rows in result["proxy"].values() for r in rows])):
            channels[name] = [json.dumps(row, ensure_ascii=False) for row in records]
        result["applicationChannelScan"] = _channel_scan(channels, env["secrets"],
            private_receipts["references"], private_receipts["complete"])
        serialized = json.dumps(result, ensure_ascii=False)
        result["credentialLeakDetected"] = (any(secret in serialized for secret in env["secrets"]) or
            any(row["credentialMatches"] for row in result["applicationChannelScan"]["channels"]))
        result["witnessesCapturedBeforePeerShutdown"] = True
        if scenario.get("probeAfterClose"):
            before = sum(row["event"] == "dispatch" for row in env["host"].trace)
            result["postCloseAdmission"] = env["host"].call("readEvidence", {"documentId": "evidence-42"})
            after = sum(row["event"] == "dispatch" for row in env["host"].trace)
            result["postCloseDispatches"] = after - before
        result = _scrub(result, [*env["secrets"], *private_receipts["references"]])
    result["peerProcessesRetired"] = all(process.poll() is not None for process in env["peer_processes"].values())
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    compiler = compile_client()
    scenarios = [("json", {}), ("sse", {"mcpResponse": "sse"}),
        ("continuation", {"initialIncludeIds": None, "suppliedIncludeIds": ["f1", "f2"]}),
        ("no_answer", {"initialIncludeIds": None}),
        ("lost_submit", {"dropResponseAfterPeerCommit": "submit"}),
        ("cancel", {"applicationAction": "cancel"})]
    rows = [{"name": name, "scenario": scenario, **execute_workflow(scenario)} for name, scenario in scenarios]
    output = {"kind": "development_smoke_not_acceptance", "profile": "meda-interop-d0/1",
              "arm": "typescript", "compiler": compiler, "runs": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"kind": output["kind"], "runs": len(rows),
                      "outcomes": {row["name"]: row["result"]["outcome"] for row in rows}}))


if __name__ == "__main__":
    main()
