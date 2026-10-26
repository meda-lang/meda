"""Actual SDK-backed host probes with explicit setup/measurement boundaries."""
from __future__ import annotations

import copy
from dataclasses import replace
import json

from .host import Host
from . import runner, support


def _safe_call(operation, result):
    # This is a trusted binding receipt, never disclose the bearer reference.
    return {"operation": operation, "result": {key: value for key, value in result.items() if key != "ref"}}


def _offsets(env, host):
    return {"trace": len(host.trace),
            "peers": {key: len(support.read_witness(path)) for key, path in env["witness_paths"].items()},
            "proxy": {key: len(proxy.events) for key, proxy in env["proxies"].items()}}


def execute_host_probe(scenario):
    mutation = scenario.get("referenceMutation")
    if mutation == "deserialize_roundtrip":
        raise runner.UnsupportedScenario("Application-wrapper roundtrip must execute through the real binding probe; privileged host token serialization is not an authority test")
    operation = scenario["operation"]
    setup_scenario = {}
    repeated = scenario.get("firstResponseLostAfterPeerCommit", False)
    if repeated:
        setup_scenario["dropResponseAfterPeerCommit"] = operation
    with runner.environment(setup_scenario) as env:
        host = env["host"]
        setup_calls, calls = [], []
        begin = None
        evidence = ref = None
        # A valid task must exist before reference/grant tests. All setup
        # uses the same real SDK path and remains visible outside the window.
        if operation != "readEvidence" and (scenario.get("grant") is not False or operation in {"provideInput", "cancel"}):
            read = host.call("readEvidence", {"documentId": "evidence-42"})
            setup_calls.append(_safe_call("readEvidence", read))
            if read.get("kind") != "Evidence":
                raise RuntimeError("Evidence setup failed")
            evidence = read["value"]
        need_ref = operation in {"provideInput", "observe", "cancel"}
        if need_ref:
            if repeated and operation == "provideInput":
                # This quota probe includes creation of the task it continues;
                # evidence retrieval alone is outside its measured window.
                begin = _offsets(env, host)
            arguments = {"evidence": evidence}
            if operation != "provideInput":
                arguments["includeIds"] = ["f1", "f2"]
            submitted = host.call("submit", arguments)
            setup_calls.append(_safe_call("submit", submitted))
            if submitted.get("kind") != "Task":
                raise RuntimeError("Task setup failed")
            ref = submitted["ref"]
        secrets = env["secrets"] + ([ref] if isinstance(ref, str) else [])
        if scenario.get("grant") is False:
            host.config = replace(host.config, grants=host.config.grants - {operation})
        if mutation == "forged_token":
            ref = "unissued-task-reference"
        elif mutation == "foreign_root":
            original = host
            host = Host(original.config)
        elif mutation == "foreign_peer":
            # Host references record their peer identity. A trusted fixture
            # changes the configured peer after issue; no request may escape.
            host.config = replace(host.config, a2a_url=host.config.a2a_url + "/other")
        elif mutation == "closed_root":
            host.abort()
        if operation == "readEvidence":
            args = {"documentId": "evidence-42"}
        elif operation == "submit":
            # For denied admission this deliberately has no accepted evidence;
            # the authority check must run before argument/dispatch handling.
            args = {"evidence": evidence, "includeIds": ["f1", "f2"]}
        elif operation == "provideInput":
            args = {"ref": ref, "includeIds": ["f1", "f2"]}
        else:
            args = {"ref": ref}
        if begin is None:
            begin = _offsets(env, host)
        for _ in range(scenario.get("attempts", 1)):
            calls.append(_safe_call(operation, host.call(operation, args)))
        end = _offsets(env, host)
        last = calls[-1]["result"]
        proposed = {"outcome": last.get("code", "ProbeComplete")}
        receipt = host.finish(proposed)
        receipt.update(probeCalls=calls, setupCalls=setup_calls,
                       peers={key: support.read_witness(path) for key, path in env["witness_paths"].items()},
                       proxy={key: copy.deepcopy(proxy.events) for key, proxy in env["proxies"].items()},
                       measuredWindow={"trace": {"start": begin["trace"], "end": end["trace"]},
                           **{name: {key: {"start": begin[name][key], "end": end[name][key]}
                                      for key in ("mcp", "a2a")} for name in ("peers", "proxy")}},
                       witnessesCapturedBeforePeerShutdown=True)
        serialized = json.dumps(receipt, ensure_ascii=False)
        receipt["credentialLeakDetected"] = any(secret in serialized for secret in secrets)
        return runner._scrub(receipt, secrets)
