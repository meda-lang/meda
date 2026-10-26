"""Executable adapter probes with raw observations for the independent oracle.

Pure codec/schema/state probes use the production helpers with a transport that
records and refuses network attempts. Reference probes run the compiled private
TypeScript binding against a real SDK task, delimit setup, then try the JSON
round trip. This module does not read expected outcomes or award acceptance.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import selectors
import subprocess
import tempfile
import time

try:
    from .host import Host, HostConfig, HostError, normalize_task_state, validate_tool_descriptor
    from . import runner, support
except ImportError:
    from host import Host, HostConfig, HostError, normalize_task_state, validate_tool_descriptor
    import runner
    import support

HERE = Path(__file__).resolve().parent
UnsupportedScenario = runner.UnsupportedScenario


class _NoNetworkTransport:
    def __init__(self):
        self.attempts = []

    def request(self, method, url, headers, body, **limits):
        self.attempts.append({"event": "network_attempt", "method": method,
                              "requestBytes": len(body or b"")})
        raise RuntimeError("A local adapter probe attempted network access")


def _error(error):
    return {"code": error.code, "remoteOutcome": error.remote, "fatal": error.fatal}


def _local_probe(scenario):
    from a2a.types import a2a_pb2
    from mcp.shared.inbound import decode_header_value
    try:
        from .sdk_peers import build_agent_card, build_tool_descriptor
    except ImportError:
        from sdk_peers import build_agent_card, build_tool_descriptor

    transport = _NoNetworkTransport()
    descriptor = build_tool_descriptor()
    host = Host(HostConfig(mcp_url="https://127.0.0.1:1/mcp", a2a_url="https://127.0.0.1:1/a2a",
                mcp_token="unused-local-mcp", a2a_token="unused-local-a2a", ca_file="unused",
                tool_descriptor=descriptor, agent_card=build_agent_card("https://127.0.0.1:1/a2a")),
                transport=transport)
    probe = {}
    if scenario.get("codec") == "mcp_parameter_header":
        if set(scenario) - {"codec", "value", "descriptorType"} or scenario.get("descriptorType") != "string":
            raise UnsupportedScenario("Unsupported parameter-header codec probe")
        value = scenario.get("value")
        if not isinstance(value, str):
            raise UnsupportedScenario("Header corpus values must be strings")
        probe = {"kind": "header_codec", "input": value, "encoded": None, "decoded": None,
                 "decoder": {"module": "mcp.shared.inbound.decode_header_value",
                             "package": "mcp", "version": importlib.metadata.version("mcp")}}
        try:
            encoded = host._parameter_headers(descriptor, {"documentId": value})["Mcp-Param-DocumentId"]
            probe.update(encoded=encoded, decoded=decode_header_value(encoded))
        except HostError as exc:
            probe["error"] = _error(exc)
        control = host._parameter_headers(descriptor, {"documentId": "evidence-42"})["Mcp-Param-DocumentId"]
        probe["control"] = {"input": "evidence-42", "encoded": control, "decoded": decode_header_value(control)}
    elif "descriptorMutation" in scenario:
        if set(scenario) != {"descriptorMutation"}:
            raise UnsupportedScenario("Unsupported descriptor-validation probe")
        control = {"descriptor": copy.deepcopy(descriptor), "returned": validate_tool_descriptor(descriptor)}
        changed = copy.deepcopy(descriptor)
        schema = changed["inputSchema"]
        field = schema["properties"]["documentId"]
        mutation = scenario["descriptorMutation"]
        if mutation == "duplicate_header_name":
            schema["properties"]["other"] = {"type": "string", "x-mcp-header": "documentid"}
        elif mutation == "invalid_header_token":
            field["x-mcp-header"] = "Invalid Header"
        elif mutation == "non_primitive_path":
            field.update(type="object", properties={"nested": {"type": "string"}})
        elif mutation == "number_annotation":
            field["type"] = "number"
        elif mutation == "schema_ref_path":
            schema["properties"]["documentId"] = {"$ref": "#/$defs/HeaderValue"}
            schema.setdefault("$defs", {})["HeaderValue"] = {"type": "string", "x-mcp-header": "DocumentId"}
        else:
            raise UnsupportedScenario("Unsupported descriptor mutation")
        probe = {"kind": "descriptor_validation", "descriptor": changed, "control": control}
        try:
            probe["returned"] = validate_tool_descriptor(changed)
        except HostError as exc:
            probe["error"] = _error(exc)
    elif "decodeTaskState" in scenario:
        state = scenario["decodeTaskState"]
        if set(scenario) != {"decodeTaskState"} or state not in {
                "SUBMITTED", "WORKING", "INPUT_REQUIRED", "AUTH_REQUIRED", "COMPLETED",
                "FAILED", "CANCELED", "REJECTED", "UNSPECIFIED", "FUTURE_STATE"}:
            raise UnsupportedScenario("Unsupported task-state probe")
        wire = "TASK_STATE_" + state
        probe = {"kind": "task_state_decode", "wireState": wire, "normalizedState": None,
                 "sdkEnumName": None, "sdkEnumNumber": None,
                 "sdkEnumMembers": [{"name": name, "number": value}
                                    for name, value in a2a_pb2.TaskState.items()],
                 "schema": {"package": "a2a-sdk", "version": importlib.metadata.version("a2a-sdk"),
                            "descriptorSha256": hashlib.sha256(a2a_pb2.DESCRIPTOR.serialized_pb).hexdigest()}}
        try:
            number = a2a_pb2.TaskState.Value(wire)
            probe.update(sdkEnumNumber=number, sdkEnumName=a2a_pb2.TaskState.Name(number))
        except ValueError:
            probe["sdkEnumError"] = {"type": "ValueError"}
        try:
            probe["normalizedState"] = normalize_task_state(wire)
        except HostError as exc:
            probe["error"] = _error(exc)
    else:
        raise UnsupportedScenario("No executable local adapter probe for this scenario")
    # No task, worker, or I/O was created. Close root admission without publishing
    # an application result. The raw helper output remains the probe result.
    host.abort()
    return {"executionScope": "local_adapter_no_network", "probe": probe,
            "trace": copy.deepcopy(host.trace), "networkAttempts": copy.deepcopy(transport.attempts),
            "peers": {"mcp": [], "a2a": []}, "proxy": {"mcp": [], "a2a": []},
            "cleanup": [], "worker": {"calls": []}}


_REFERENCE_SOURCE = r"""
const readline = require('node:readline');
const {createBindings} = require(process.argv[1]);
const operation = process.argv[2];
const lines = readline.createInterface({input:process.stdin});
const pending = new Map(); let next = 0;
function emit(value) { process.stdout.write(JSON.stringify(value)+'\n'); }
lines.on('line', line => {
  const frame = JSON.parse(line); const resolve = pending.get(frame.id);
  if (!resolve) throw Error('UnexpectedControllerFrame');
  pending.delete(frame.id); resolve(frame.value);
});
function exchange(operation, args) {
  const id = ++next;
  return new Promise(resolve => { pending.set(id, resolve);
    emit({kind:'call',id,operation,arguments:args}); });
}
(async()=>{
  const binding = createBindings(exchange);
  const evidence = await binding.host.readEvidence('evidence-42');
  if (evidence.kind !== 'Evidence') throw Error('EvidenceSetupFailed');
  const task = await binding.host.submit(evidence.value,['f1','f2']);
  if (task.kind !== 'Task') throw Error('ReferenceSetupFailed');
  const valid = await binding.host.observe(task.ref);
  if (valid.kind !== 'Task') throw Error('PositiveControlFailed');
  const control = {kind:valid.kind,state:valid.state};
  await new Promise(resolve => {pending.set('begin',resolve);
    emit({kind:'case_begin',positiveControlResult:control});});
  const before = next;
  const serializedWrapper = JSON.stringify(task.ref);
  const keys = Object.keys(task.ref);
  const roundtripResult = await binding.host.observe(JSON.parse(serializedWrapper));
  const after = next;
  binding.close();
  emit({kind:'probe_result',probe:{kind:'reference_serialization',operation,
    serializedWrapper,wrapperKeys:keys,roundtripResult,positiveControlResult:control,
    bridgeCallsBefore:before,bridgeCallsAfter:after}});
  lines.close();
})().catch(()=>{emit({kind:'probe_error',code:'ProbeExecutionError'});lines.close();process.exitCode=1;});
"""


def _snapshot(env, calls):
    return {"trace": len(env["host"].trace), "bridgeCalls": len(calls),
            "peers": {protocol: len(support.read_witness(path)) for protocol, path in env["witness_paths"].items()},
            "proxy": {protocol: len(proxy.events) for protocol, proxy in env["proxies"].items()}}


def _window(start, end):
    return {"trace": {"start": start["trace"], "end": end["trace"]},
            "bridgeCalls": {"start": start["bridgeCalls"], "end": end["bridgeCalls"]},
            **{name: {protocol: {"start": start[name][protocol], "end": end[name][protocol]}
                      for protocol in ("mcp", "a2a")} for name in ("peers", "proxy")}}


def _reference_probe(scenario, *, compiled):
    allowed = {"setup", "operation", "referenceMutation", "trustedRpcTokenExcluded",
               "referenceSurface", "setupNote"}
    operation = "deserialize_roundtrip" if scenario.get("referenceMutation") == "deserialize_roundtrip" else scenario.get("operation")
    if (set(scenario) - allowed or operation not in {"serialize_wrapper", "deserialize_roundtrip"}
            or scenario.get("setup") not in {"owned_reference", "owned_reference_if_needed"}
            or scenario.get("referenceSurface") not in {None, "application_TaskRef_wrapper"}
            or scenario.get("trustedRpcTokenExcluded", True) is not True
            or not isinstance(scenario.get("setupNote", ""), str)):
        raise UnsupportedScenario("Unsupported private-reference adapter probe")
    compiler = None if compiled else runner.compile_client()
    binding = HERE / "dist/bindings.js"
    if not binding.is_file():
        raise RuntimeError("Compile the pinned TypeScript binding before running adapter probes")
    with runner.environment({}) as env:
        calls, references, application_output = [], [], []
        begin = end = probe = None
        with tempfile.TemporaryFile() as stderr:
            process = subprocess.Popen([runner._node(), "--max-old-space-size=128", "-e", _REFERENCE_SOURCE,
                                        str(binding), operation], cwd=HERE, env=runner._safe_environment(),
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr,
                                       start_new_session=True, bufsize=0)
            selector = selectors.DefaultSelector()
            selector.register(process.stdout, selectors.EVENT_READ)
            deadline, buffer, peak = time.monotonic() + 10, bytearray(), 0
            try:
                while probe is None:
                    peak = max(peak, runner._rss(process.pid))
                    if time.monotonic() >= deadline or peak > runner.MAX_RSS:
                        raise RuntimeError("Reference probe exceeded its supervised limit")
                    for key, _ in selector.select(.05):
                        chunk = os.read(key.fileobj.fileno(), 4096)
                        if not chunk:
                            raise RuntimeError("Reference worker exited before reporting observations")
                        buffer.extend(chunk)
                        if len(buffer) > runner.MAX_LINE:
                            raise RuntimeError("Reference worker exceeded its frame limit")
                        while b"\n" in buffer:
                            line, _, remaining = buffer.partition(b"\n")
                            buffer = bytearray(remaining)
                            frame = json.loads(line)
                            kind = frame.get("kind")
                            if kind == "call":
                                value = env["host"].call(frame["operation"], frame["arguments"])
                                record = {"operation": frame["operation"], "kind": value.get("kind")}
                                record.update({k: value[k] for k in ("state", "code", "remoteOutcome", "fatal") if k in value})
                                calls.append(record)
                                if value.get("kind") == "Task":
                                    references.append(value["ref"])
                                response = {"id": frame["id"], "value": value}
                            elif kind == "case_begin":
                                if begin is not None:
                                    raise RuntimeError("Duplicate reference measurement boundary")
                                begin = _snapshot(env, calls)
                                application_output.append(json.dumps(frame, ensure_ascii=False))
                                response = {"id": "begin", "value": None}
                            elif kind == "probe_result":
                                if begin is None:
                                    raise RuntimeError("Reference measurement did not begin")
                                probe = frame["probe"]
                                end = _snapshot(env, calls)
                                application_output.append(json.dumps(frame, ensure_ascii=False))
                                break
                            else:
                                raise RuntimeError("Reference probe failed without a usable observation")
                            process.stdin.write((json.dumps(response) + "\n").encode())
                            process.stdin.flush()
                process.wait(timeout=2)
                if process.returncode:
                    raise RuntimeError("Reference worker failed")
            finally:
                selector.close()
                if process.poll() is None:
                    runner._kill(process)
                process.stdin.close()
                process.stdout.close()
            stderr.seek(0)
            diagnostic = stderr.read(runner.MAX_LINE + 1)
        # Measurement ended before local root shutdown; preserve full ledgers and
        # half-open offsets instead of erasing setup effects or asserting zero.
        env["host"].abort()
        observed = {"executionScope": "compiled_typescript_sdk_reference_probe", "probe": probe,
                    "trace": copy.deepcopy(env["host"].trace), "cleanup": [],
                    "worker": {"calls": calls, "retired": process.poll() is not None,
                               "returncode": process.returncode, "peakRssBytesObserved": peak,
                               "stderrBytes": len(diagnostic)},
                    "measuredWindow": _window(begin, end),
                    "measurementEvents": [{"event": "case_begin", "offsets": begin},
                                          {"event": "case_end", "offsets": end}],
                    "peers": {protocol: support.read_witness(path) for protocol, path in env["witness_paths"].items()},
                    "proxy": {protocol: copy.deepcopy(proxy.events) for protocol, proxy in env["proxies"].items()},
                    "binding": {"path": "dist/bindings.js", "sha256": hashlib.sha256(binding.read_bytes()).hexdigest()},
                    "witnessesCapturedBeforePeerShutdown": True}
        if compiler is not None:
            observed["compiler"] = compiler
        channels = {"applicationProbeOutput": application_output,
                    "ordinaryHostTrace": [json.dumps(row) for row in observed["trace"]],
                    "peerWitnesses": [json.dumps(row) for rows in observed["peers"].values() for row in rows],
                    "proxyWitnesses": [json.dumps(row) for rows in observed["proxy"].values() for row in rows],
                    "workerStderr": [diagnostic.decode(errors="replace")]}
        observed["applicationChannelScan"] = runner._channel_scan(channels, env["secrets"], list(set(references)),
                                                                  len(diagnostic) <= runner.MAX_LINE)
        raw = json.dumps(observed)
        observed["credentialLeakDetected"] = any(token in raw for token in env["secrets"])
        observed = runner._scrub(observed, [*env["secrets"], *references])
    observed["peerProcessesRetired"] = all(process.poll() is not None for process in env["peer_processes"].values())
    return observed


def execute_adapter_probe(scenario, *, compiled=True):
    """Return raw probe evidence; raise UnsupportedScenario for unknown inputs."""
    if not isinstance(scenario, dict):
        raise UnsupportedScenario("An adapter scenario must be an object")
    if scenario.get("operation") == "serialize_wrapper" or scenario.get("referenceMutation") == "deserialize_roundtrip":
        return _reference_probe(scenario, compiled=compiled)
    return _local_probe(scenario)


def run_adapter_case(case, arm="typescript", *, compiled=False):
    if case.get("surface") != "adapter_probe" or arm not in case.get("arms", []):
        raise UnsupportedScenario("The requested adapter case/arm is unavailable")
    return execute_adapter_probe(case["scenario"], compiled=compiled)
