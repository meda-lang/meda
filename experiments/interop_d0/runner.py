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
import selectors
import shutil
import signal
import subprocess
import tempfile
import threading
import time

try:
    from .host import Host, HostConfig, Limits, OPERATIONS
    from . import support
except ImportError:
    from host import Host, HostConfig, Limits, OPERATIONS
    import support

HERE = Path(__file__).resolve().parent
MAX_LINE = 65_536
MAX_RSS = 256 * 1024 * 1024
_PROCESS_STATUS_PATHS = {}


class UnsupportedScenario(ValueError):
    """A planned case lacks its actual implementation; never count it as passed."""


def _node():
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("Node.js is required")
    return node


def _safe_environment():
    # Deliberately excludes credentials, NODE_OPTIONS and other inherited hooks.
    return {"PATH": os.defpath, "LANG": "C.UTF-8"}


def _rss(pid):
    # Some executors expose an outer /proc inside an inner PID namespace.
    # Popen.pid then does not name that process in /proc. Resolve only among
    # this controller's direct children and match its namespace-visible PID.
    own = Path("/proc/self/status").read_text().splitlines()
    outer_pid = next(line.split()[1] for line in own if line.startswith("Tgid:"))
    key = (outer_pid, pid)
    cached = _PROCESS_STATUS_PATHS.get(key)
    paths = [cached] if cached is not None else []
    # The children pseudo-file is unavailable on some kernel builds. Enumerate
    # status metadata only, requiring both parent and namespace PID to match.
    paths.extend(path / "status" for path in Path("/proc").iterdir() if path.name.isdigit())
    for path in paths:
        try:
            fields = {line.split(":", 1)[0]: line.split(":", 1)[1].split()
                      for line in path.read_text().splitlines()}
            namespace_pids = fields.get("NSpid", fields["Pid"])
            if fields["PPid"] == [outer_pid] and int(namespace_pids[-1]) == pid:
                _PROCESS_STATUS_PATHS[key] = path
                return int(fields.get("VmRSS", ["0"])[0]) * 1024
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    return 0


def _kill(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=2)


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


def run_client(host, input_value, *, proxies=None, scenario=None, worker_path=None,
               credential_sentinels=(), private_receipts=None):
    """Run one actual Node process; return host publication and worker evidence."""
    if not Path("/proc/self/status").is_file():
        raise RuntimeError("This profile requires Linux RSS supervision")
    worker_path = Path(worker_path or HERE / "dist/main.js")
    if not worker_path.is_file():
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
    process = subprocess.Popen([_node(), "--max-old-space-size=128", str(worker_path)], cwd=HERE,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env=_safe_environment(), start_new_session=True, bufsize=0)
    os.set_blocking(process.stdin.fileno(), False)
    start = time.monotonic()
    stop = threading.Event()
    guard = threading.Lock()
    state = {"termination": None, "peakRssBytesObserved": 0, "barriers": []}
    rpc_calls, finish_frames, post_fatal_responses = [], 0, 0
    stderr = bytearray()
    unexpected_stdout = bytearray()
    internal_refs = set()
    truncated = False

    def terminate(reason):
        with guard:
            if state["termination"] is not None:
                return
            state["termination"] = reason
            host.abort("Timeout" if reason == "deadline" else "RootTerminated")
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def monitor():
        try:
            monitor_loop()
        except Exception:
            terminate("supervisor_failure")

    def monitor_loop():
        while not stop.wait(.01):
            if process.poll() is not None:
                return
            rss = _rss(process.pid)
            state["peakRssBytesObserved"] = max(state["peakRssBytesObserved"], rss)
            if rss > MAX_RSS:
                terminate("memory_limit")
            if time.monotonic() >= host.deadline:
                terminate("deadline")
            barrier = scenario.get("barrier")
            if barrier == "close_before_observation_response" and "a2a" in proxies:
                proxy = proxies["a2a"]
                if proxy.response_ready.is_set():
                    state["barriers"].append("root_closed_before_observation_release")
                    terminate("root_abort")
                    proxy.release_response.set()
                    return
            if barrier == "abort_during_evidence_stream" and "mcp" in proxies:
                if proxies["mcp"].stream_started.is_set():
                    state["barriers"].append("root_closed_after_stream_started")
                    terminate("root_abort")
                    return

    def write_frame(frame):
        # A hostile or wedged worker cannot hold the closure lock by failing to
        # drain stdin. Each write is nonblocking; closure may interrupt a frame.
        view = memoryview(frame)
        while view:
            with guard:
                if host.closed or state["termination"] is not None:
                    return False
                try:
                    written = os.write(process.stdin.fileno(), view[:4096])
                except BlockingIOError:
                    written = 0
            if written:
                view = view[written:]
            else:
                stop.wait(.005)
        return True

    watcher = threading.Thread(target=monitor, name="d0-worker-supervisor", daemon=True)
    watcher.start()
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    buffer = bytearray()
    proposed = None
    expected_id = 1
    try:
        initial = json.dumps({"kind": "start", "input": input_value}, separators=(",", ":")).encode() + b"\n"
        if len(initial) > MAX_LINE:
            terminate("input_limit")
        else:
            write_frame(initial)
        while proposed is None and state["termination"] is None:
            ready = selector.select(.05)
            if not ready and process.poll() is not None:
                terminate("exit_without_finish")
                break
            for key, _ in ready:
                data = os.read(key.fileobj.fileno(), 4096)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                if key.data == "stderr":
                    stderr.extend(data)
                    if len(stderr) > MAX_LINE:
                        truncated = True
                        del stderr[MAX_LINE:]
                        terminate("stderr_limit")
                    continue
                buffer.extend(data)
                if len(buffer) > MAX_LINE:
                    unexpected_stdout.extend(buffer[:MAX_LINE])
                    truncated = True
                    terminate("frame_limit")
                    break
                while b"\n" in buffer and state["termination"] is None:
                    line, _, rest = buffer.partition(b"\n")
                    buffer = bytearray(rest)
                    try:
                        frame = json.loads(line)
                    except (UnicodeDecodeError, ValueError):
                        unexpected_stdout.extend(line)
                        terminate("invalid_frame")
                        break
                    if not isinstance(frame, dict):
                        unexpected_stdout.extend(line)
                        terminate("invalid_frame")
                        break
                    if frame.get("kind") == "finish":
                        finish_frames += 1
                        if finish_frames != 1 or not isinstance(frame.get("result"), dict):
                            unexpected_stdout.extend(line)
                            terminate("invalid_finish")
                            break
                        proposed = frame["result"]
                        if buffer:
                            unexpected_stdout.extend(buffer)
                            finish_frames += _finish_count(buffer)
                            terminate("output_after_finish")
                        break
                    operation = frame.get("operation")
                    if (frame.get("kind") != "call" or type(frame.get("id")) is not int or frame.get("id") != expected_id or
                            not isinstance(operation, str) or operation not in OPERATIONS or not isinstance(frame.get("arguments"), dict)):
                        terminate("invalid_call")
                        break
                    expected_id += 1
                    value = host.call(operation, frame["arguments"])
                    if value.get("kind") == "Task" and isinstance(value.get("ref"), str):
                        internal_refs.add(value["ref"])
                    rpc_calls.append({"id": frame["id"], "operation": operation, "kind": value.get("kind"),
                                      **{name: value[name] for name in ("state", "code", "fatal", "remoteOutcome") if name in value}})
                    barrier = scenario.get("barrier")
                    if operation == "submit" and value.get("kind") == "Task" and barrier in {
                            "abort_after_submit_before_poll", "abort_with_zero_normal_allowance"}:
                        state["barriers"].append("root_closed_after_submit_before_source_response")
                        terminate("root_abort")
                    if value.get("fatal") or host.closed or state["termination"] is not None:
                        if state["termination"] is None:
                            # Retire without replacing the host's specific fatal cause.
                            state["termination"] = "fatal_host_outcome"
                            try:
                                os.killpg(process.pid, signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                        break
                    response = json.dumps({"kind": "response", "id": frame["id"], "value": value},
                                          separators=(",", ":")).encode() + b"\n"
                    if len(response) > MAX_LINE:
                        terminate("response_frame_limit")
                        break
                    if not write_frame(response):
                        break
        if process.stdin and not process.stdin.closed:
            process.stdin.close()
        try:
            process.wait(timeout=min(1, host.limits.cleanup_seconds))
        except subprocess.TimeoutExpired:
            terminate("worker_retirement_limit")
            _kill(process)
        # After one finish, any further stdout is a duplicate/output violation.
        os.set_blocking(process.stdout.fileno(), False)
        trailing = process.stdout.read(MAX_LINE + 1)
        if trailing:
            unexpected_stdout.extend(trailing[:MAX_LINE])
            truncated = truncated or len(trailing) > MAX_LINE
            finish_frames += _finish_count(trailing)
            terminate("output_after_finish")
        os.set_blocking(process.stderr.fileno(), False)
        trailing_stderr = process.stderr.read(MAX_LINE - len(stderr) + 1)
        if trailing_stderr:
            stderr.extend(trailing_stderr)
        if len(stderr) > MAX_LINE or len(unexpected_stdout) > MAX_LINE:
            truncated = True
            del stderr[MAX_LINE:]
            del unexpected_stdout[MAX_LINE:]
        if process.returncode not in (0, None) and state["termination"] is None:
            terminate("worker_failure")
    except (BrokenPipeError, OSError):
        terminate("controller_io_failure")
    finally:
        stop.set()
        _kill(process)
        watcher.join(timeout=1)
        selector.close()
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream and not stream.closed:
                stream.close()
    publication = host.finish(proposed or {"outcome": "RootTerminated", "fatal": True})
    if scenario.get("barrier") == "publication_before_abort":
        host.abort("RootTerminated")
        state["barriers"].append("publication_committed_before_late_abort")
    application_channels = {
        "applicationFinish": [] if proposed is None else [json.dumps(proposed, ensure_ascii=False)],
        "stderr": [] if not stderr else [stderr.decode(errors="replace")],
        "unexpectedStdout": [] if not unexpected_stdout else [unexpected_stdout.decode(errors="replace")],
    }
    if private_receipts is not None:
        private_receipts.update(references=internal_refs, channels=application_channels, complete=not truncated)
    worker = {"retired": process.poll() is not None, "returncode": process.returncode,
              "termination": state["termination"] or "normal", "finishFrames": finish_frames,
              "responsesAfterFatal": post_fatal_responses, "calls": rpc_calls,
              "peakRssBytesObserved": state["peakRssBytesObserved"],
              "elapsedSeconds": time.monotonic() - start, "barriers": state["barriers"],
              "supervisorJoined": not watcher.is_alive(), "stderrBytes": len(stderr),
              "applicationFinish": proposed, "stderr": application_channels["stderr"],
              "unexpectedStdout": application_channels["unexpectedStdout"], "outputTruncated": truncated,
              "containment": "sampled_rss_and_wall_supervision_not_os_sandbox"}
    return _scrub({**publication, "worker": worker}, [*credential_sentinels, *internal_refs])


def _finish_count(raw):
    count = 0
    for line in raw.splitlines():
        try:
            value = json.loads(line)
            count += isinstance(value, dict) and value.get("kind") == "finish"
        except (ValueError, UnicodeError):
            pass
    return count


def _channel_scan(channels, credentials, references, complete):
    rows = []
    for name, records in channels.items():
        rows.append({"name": name, "entries": len(records),
            "bytes": sum(len(item.encode("utf-8")) for item in records),
            "credentialMatches": sum(item.count(token) for item in records for token in credentials),
            "referenceMatches": sum(item.count(token) for item in records for token in references)})
    return {"channels": rows, "credentialSentinelCount": len(credentials),
            "referenceSentinelCount": len(references), "complete": complete}


def _scrub(value, secrets):
    if isinstance(value, str):
        for secret in secrets:
            value = value.replace(secret, "[REDACTED_CREDENTIAL]")
        return value
    if isinstance(value, list):
        return [_scrub(item, secrets) for item in value]
    if isinstance(value, dict):
        return {_scrub(key, secrets): _scrub(item, secrets) for key, item in value.items()}
    return value


def execute_workflow(scenario):
    with environment(scenario) as env:
        private_receipts = {}
        result = run_client(env["host"], workflow_input(scenario), proxies=env["proxies"], scenario=scenario,
                            credential_sentinels=env["secrets"], private_receipts=private_receipts)
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
