"""Isolated host mutants paired with canonical controls over real SDK peers.

Only the selected method on one fixture instance is replaced. The replacement
is derived from the canonical method and refuses to run if the expected guard
has changed. Runtime source files, the Host class, policies, and peer grants are
never weakened. Independent oracle code decides whether the observed behavior
demonstrates the injected defect.
"""
from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import inspect
import json
import textwrap
from types import MethodType

from . import host as host_module, runner, support
from .acceptance_host import _offsets, _safe_call


_MUTATIONS = {
    "remove_operation_grant": (
        "call",
        ((" or operation not in self.config.grants", ""),),
    ),
    "remove_request_quota": (
        "_reserve",
        (("if self.requests >= self.limits.max_requests:",
          "if False and self.requests >= self.limits.max_requests:"),
         ("if self.normal_requests >= self.limits.max_requests - self.limits.cleanup_requests:",
          "if False and self.normal_requests >= self.limits.max_requests - self.limits.cleanup_requests:")),
    ),
}


def _method_mutation(host, mutation):
    """Apply a precise source mutation only to this instance; record its bytes."""
    method, replacements = _MUTATIONS[mutation]
    original = textwrap.dedent(inspect.getsource(getattr(host_module.Host, method)))
    changed = original
    for before, after in replacements:
        if changed.count(before) != 1:
            raise runner.UnsupportedScenario("Canonical host guard changed; mutation needs review")
        changed = changed.replace(before, after, 1)
    namespace = dict(vars(host_module))
    exec(compile(changed, "<meda-host-mutation:" + mutation + ">", "exec"), namespace)
    setattr(host, method, MethodType(namespace[method], host))
    return {
        "kind": "host_mutant", "mutation": mutation, "arm": "shared",
        "method": method,
        "canonicalMethodSha256": hashlib.sha256(original.encode()).hexdigest(),
        "mutatedMethodSha256": hashlib.sha256(changed.encode()).hexdigest(),
        "replacements": [{"before": before, "after": after} for before, after in replacements],
        "scope": "fixture_instance",
    }


def _policy(host, operation):
    return {
        "operation": operation,
        "grants": sorted(host.config.grants),
        "limits": {
            "max_requests": host.limits.max_requests,
            "cleanup_requests": host.limits.cleanup_requests,
            "normalRequests": host.limits.max_requests - host.limits.cleanup_requests,
        },
    }


def _run(scenario, *, mutated):
    mutation = scenario["hostMutation"]
    operation = scenario["operation"]
    # A completed task needs no cancellation. This keeps the grant probe's
    # measured submit separate from cleanup without removing any ledger rows.
    peer_scenario = {"a2aStates": ["COMPLETED"]} if mutation == "remove_operation_grant" else {
        "limits": {"normalRequests": scenario["normalRequests"]}}
    with runner.environment(peer_scenario) as env:
        host = env["host"]
        if mutation == "remove_operation_grant":
            host.config = replace(host.config, grants=host.config.grants - {operation})
        policy = _policy(host, operation)
        setup_calls = []
        if operation == "submit":
            evidence = host.call("readEvidence", {"documentId": "evidence-42"})
            setup_calls.append(_safe_call("readEvidence", evidence))
            if evidence.get("kind") != "Evidence":
                raise RuntimeError("Evidence setup failed")
            arguments = {"evidence": evidence["value"], "includeIds": ["f1", "f2"]}
        else:
            arguments = {"documentId": "evidence-42"}
        provenance = _method_mutation(host, mutation) if mutated else None
        begin = _offsets(env, host)
        value = host.call(operation, arguments)
        end = _offsets(env, host)
        secrets = [*env["secrets"], *host.refs]
        proposed = {"outcome": value.get("code", "ProbeComplete")}
        receipt = host.finish(proposed)
        if policy != _policy(host, operation):
            raise RuntimeError("Mutation changed the declared host policy")
        receipt.update(
            probeCalls=[_safe_call(operation, value)], setupCalls=setup_calls,
            mutationPolicy=policy,
            peers={key: support.read_witness(path) for key, path in env["witness_paths"].items()},
            proxy={key: copy.deepcopy(proxy.events) for key, proxy in env["proxies"].items()},
            measuredWindow={
                "trace": {"start": begin["trace"], "end": end["trace"]},
                **{name: {key: {"start": begin[name][key], "end": end[name][key]}
                          for key in ("mcp", "a2a")} for name in ("peers", "proxy")},
            },
            witnessesCapturedBeforePeerShutdown=True,
        )
        # Publication is recorded after the operation window. The actual
        # unsuccessful terminal belongs in the measured trace as well.
        receipt["measuredWindow"]["trace"]["end"] = len(receipt["trace"])
        serialized = json.dumps(receipt, ensure_ascii=False)
        receipt["credentialLeakDetected"] = any(secret in serialized for secret in secrets)
        receipt = runner._scrub(receipt, secrets)
    receipt["peerProcessesRetired"] = all(process.poll() is not None for process in env["peer_processes"].values())
    return receipt, provenance


def execute_host_mutant(scenario):
    """Execute the canonical denial and the same operation with one guard gone."""
    mutation = scenario.get("hostMutation")
    valid_grant = (mutation == "remove_operation_grant" and scenario.get("operation") == "submit"
                   and scenario.get("hostGrant") is False
                   and scenario.get("peerCredentialAllowsOperation") is True)
    valid_quota = (mutation == "remove_request_quota" and scenario.get("operation") == "readEvidence"
                   and type(scenario.get("normalRequests")) is int and scenario["normalRequests"] == 0)
    if not (valid_grant or valid_quota):
        raise runner.UnsupportedScenario("Unsupported host mutation scenario")
    control, _ = _run(scenario, mutated=False)
    receipt, provenance = _run(scenario, mutated=True)
    receipt["mutationControl"] = control
    receipt["mutationExecution"] = provenance
    return receipt
