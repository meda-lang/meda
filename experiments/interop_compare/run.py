#!/usr/bin/env python3
"""Outside-in matched decision-client experiment. Not protocol conformance."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

from clients import ARMS, ClientError, checker_probes, compile_client, invoke_client, resolve_tsc, source_path
from host import FixturePeer, GuardedHost

ROOT = Path(__file__).resolve().parent


def file_manifest():
    paths = [ROOT / "EXPERIMENT.md", ROOT / "cases.json", ROOT / "host.py", ROOT / "peer.py",
             ROOT / "clients.py", ROOT / "run.py", ROOT / "toolchain.json", ROOT / "package.json",
             ROOT / "maintenance.py"]
    paths += sorted((ROOT / "clients").glob("*"))
    paths += [ROOT.parent / "gates" / "meda.py", ROOT.parent / "gates" / "meda_core.py"]
    return {str(path.relative_to(ROOT.parent)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths if path.is_file()}


def compiler_manifest():
    directory=resolve_tsc().parent.parent
    digest=hashlib.sha256()
    count=0
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            digest.update(str(path.relative_to(directory)).encode()+b"\0")
            digest.update(hashlib.sha256(path.read_bytes()).digest())
            count+=1
    return {"algorithm":"sha256(relative-path NUL file-sha256), sorted paths",
            "packageTreeSha256":digest.hexdigest(),"files":count,"version":"5.9.3"}


def run_case(arm, case):
    with FixturePeer(case["mode"]) as peer:
        host = GuardedHost(peer, max_calls=case.get("max_calls", 8),
                           allowed_ops=case.get("allowed_ops"))
        snapshot = {"stage": "start", "observation": "", "taskId": "",
                    "remaining": host.max_calls, "evidence": "", "input": case.get("input", "")}
        decisions, observations = [], []
        terminal = "HARNESS_STEP_LIMIT"
        for _ in range(20):
            decision = invoke_client(arm, snapshot)
            decisions.append(decision)
            if decision["action"] == "stop":
                terminal = decision["payload"]
                break
            result = host.execute({"kind": decision["action"], "tenant": host.grant.tenant,
                                   "taskId": decision["taskId"], "input": decision["payload"]})
            observations.append(result)
            snapshot = {"stage": "running", "observation": result["kind"],
                        "taskId": result["taskId"], "remaining": host.max_calls-host.dispatches,
                        "evidence": result["value"], "input": case.get("input", "")}
        host.close()
        stats = peer.stats()
        actual = {"terminal": terminal,
                  "actions": [e["action"] for e in host.trace if e["event"] == "dispatch"],
                  "created": stats["created"]}
        if "continuationInput" in case["expected"]:
            actual["continuationInput"] = stats["tasks"].get("t1",{}).get("continuationInput")
        return {"arm": arm, "case": case["id"], "expected": case["expected"], "actual": actual,
                "passed": actual == case["expected"], "decisions": decisions,
                "observations": observations, "hostTrace": host.trace, "peerStats": stats}


def action(kind="read", tenant="team-a", task_id="", value=""):
    return {"kind": kind, "tenant": tenant, "taskId": task_id, "input": value}


def host_attribution():
    """Direct requests bypass both language checkers. Independent literal oracles."""
    rows = []
    def save(name, actual, expected):
        rows.append({"id":name, "layer":"shared_host_or_peer", "actual":actual,
                     "expected":expected, "passed":actual == expected})
    with FixturePeer() as peer:
        host = GuardedHost(peer, allowed_ops={"read"}, max_calls=1)
        save("wrong_tenant", [host.execute(action(tenant="team-b"))["kind"],host.dispatches], ["denied",0])
        save("ungranted_operation", [host.execute(action("submit"))["kind"],host.dispatches], ["denied",0])
        extra = action(); extra["endpoint"] = "http://ungranted.invalid/"
        save("endpoint_injection", [host.execute(extra)["kind"],host.dispatches], ["invalid",0])
        save("authorized_control", [host.execute(action())["value"],host.dispatches], ["evidence:42",1])
        save("client_ignores_quota", [host.execute(action())["kind"],host.dispatches], ["budget",1])
        host.close()
        save("after_root_close", [host.execute(action())["kind"],host.dispatches], ["denied",1])
    with FixturePeer() as peer:
        old = GuardedHost(peer, root_id="old")
        pending = old.execute(action("submit",value="evidence:42"))
        old.close()
        foreign = GuardedHost(peer, principal="bob", root_id="foreign")
        result = foreign.execute(action("poll",task_id=pending["taskId"]))
        save("foreign_principal_reattach", [result["kind"],result["value"]], ["denied",""])
        current = GuardedHost(peer, root_id="new")
        result = current.execute(action("poll",task_id=pending["taskId"]))
        save("authorized_reattach", [result["kind"],result["value"],peer.stats()["created"]],
             ["completed","report:evidence:42",1])
    with FixturePeer() as peer:
        host=GuardedHost(peer)
        task=host.execute(action("submit",value="evidence:42"))
        cancelled=host.execute(action("cancel",task_id=task["taskId"]))
        observed=host.execute(action("poll",task_id=task["taskId"]))
        save("cancel_observed", [cancelled["kind"],observed["kind"],peer.stats()["created"]],
             ["cancelled","cancelled",1])
    return rows


def ablations():
    """Test-only source mutants; never edit the real host or expose a toggle."""
    source=(ROOT / "host.py").read_text()
    rows=[]
    mutants={
        "removed_call_limit": ("if self.dispatches >= self.max_calls:", "if False:", {"max_calls":0}, action(), ["budget",0]),
        "removed_operation_grant": ("action[\"tenant\"] != self.grant.tenant or kind not in self.grant.allowed_ops", "action[\"tenant\"] != self.grant.tenant", {"allowed_ops":set()}, action(), ["denied",0]),
    }
    for name,(old,new,config,request,expected) in mutants.items():
        if source.count(old)!=1:
            raise RuntimeError(f"Ablation selector drift: {name}")
        with tempfile.TemporaryDirectory(prefix="meda-host-ablation-") as directory:
            path=Path(directory)/"host_mutant.py"
            path.write_text(source.replace(old,new))
            spec=importlib.util.spec_from_file_location(name,path)
            module=importlib.util.module_from_spec(spec)
            sys.modules[name]=module
            try:
                spec.loader.exec_module(module)
                with FixturePeer() as peer:
                    mutant=module.GuardedHost(peer.url,**config)
                    observed=mutant.execute(request)
                    actual=[observed["kind"],mutant.dispatches]
                rows.append({"id":name,"originalOracle":expected,"mutantActual":actual,
                             "detected":actual!=expected})
            finally:
                sys.modules.pop(name,None)
    return rows


def policy_attribution():
    """A well-typed explicit resubmit is not stopped by the library's no-retry rule."""
    from maintenance import broken_source, snap
    rows=[]
    for arm in ARMS:
        with tempfile.TemporaryDirectory(prefix="meda-policy-mutant-") as directory:
            path=Path(directory)/("policy.meda" if arm=="meda" else "policy.ts")
            path.write_text(broken_source(arm,"uncertain_delivery",source_path(arm).read_text()))
            checked=compile_client(arm,path)
            with FixturePeer("lost_submit") as peer:
                host=GuardedHost(peer,max_calls=3)
                first=host.execute(action("submit",value="evidence:42"))
                decision=invoke_client(arm,snap("unknown",2,"",evidence="evidence:42"),path)
                second=host.execute(action(decision["action"],task_id=decision["taskId"],value=decision["payload"]))
                actual={"outcomes":[first["kind"],second["kind"]],"created":peer.stats()["created"],
                        "dispatches":host.dispatches}
            rows.append({"arm":arm,"id":"well_typed_resubmit_after_unknown","sourceChecked":True,
                         "checker":checked["checker"],"decision":decision,"actual":actual,
                         "safePolicyExpectedCreated":1,"semanticDefectDetected":actual["created"]!=1,
                         "expectedMutantBehaviorObserved":actual=={"outcomes":["unknown","unknown"],"created":2,"dispatches":2},
                         "attribution":"Client policy prevents explicit duplicate submissions; the host only disables its own retries."})
    return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    cases=json.loads((ROOT/"cases.json").read_text())["cases"]
    # Freeze identities before any measured case. Compilation is preflight.
    identities=file_manifest()
    provenance={arm:compile_client(arm) for arm in ARMS}
    rows=[]
    for i,case in enumerate(cases):
        for arm in ARMS[::1 if i%2==0 else -1]:
            try:
                rows.append(run_case(arm,case))
            except Exception as error:
                rows.append({"arm":arm,"case":case["id"],"passed":False,"infrastructure":type(error).__name__,"message":str(error)})
    comparisons=[]
    for case in cases:
        paired=[row for row in rows if row["case"]==case["id"]]
        comparisons.append({"case":case["id"],"equal":len(paired)==2 and all("actual" in r for r in paired)
                            and paired[0]["actual"]==paired[1]["actual"]
                            and paired[0]["decisions"]==paired[1]["decisions"]
                            and paired[0]["observations"]==paired[1]["observations"]
                            and paired[0]["hostTrace"]==paired[1]["hostTrace"]})
    probes=checker_probes()
    attribution=host_attribution()
    mutants=ablations()
    policy_mutants=policy_attribution()
    summary={"scenariosPerArm":len(cases),
             "passedByArm":{arm:sum(r["passed"] for r in rows if r["arm"]==arm) for arm in ARMS},
             "equalPairs":sum(r["equal"] for r in comparisons),
             "checkerRows":len(probes),
             "checkerExpectationsMet":sum(v["accepted"]==p["expectedAccepted"] for p in probes for v in p["arms"].values()),
             "hostAttributionCases":len(attribution),"hostAttributionPassed":sum(r["passed"] for r in attribution),
             "hostAblations":len(mutants),"hostAblationsDetected":sum(r["detected"] for r in mutants),
             "clientPolicyMutants":len(policy_mutants),
             "clientPolicyMutantsDetected":sum(r["semanticDefectDetected"] for r in policy_mutants)}
    okay=(all(r["passed"] for r in rows) and all(r["equal"] for r in comparisons)
          and all(v["accepted"]==p["expectedAccepted"] for p in probes for v in p["arms"].values())
          and all(r["passed"] for r in attribution) and all(r["detected"] for r in mutants)
          and all(r["expectedMutantBehaviorObserved"] for r in policy_mutants))
    result={"kind":"executed_decision_boundary_comparison","profile":"shared-host-decision-comparison/1",
            "runAtUtc":datetime.now(timezone.utc).isoformat(),"sourceManifest":identities,
            "sourceUnchanged":file_manifest()==identities,"clientProvenance":provenance,
            "python":platform.python_version(),"node":subprocess.check_output(["node","--version"],text=True).strip(),
            "typescript":"5.9.3","typescriptCompiler":compiler_manifest(),
            "summary":summary,"cases":rows,"paired":comparisons,"checkerProbes":probes,
            "hostAttribution":attribution,"hostAblations":mutants,"clientPolicyMutants":policy_mutants,
            "notMeasured":["Meda effect runtime","official MCP/A2A conformance","production authentication",
                           "global remote quotas","durable recovery","language productivity","live model cost",
                           "dynamic descriptor/binding drift","host-enforced final domain contract",
                           "production cancellation containment"],
            "passed":okay and file_manifest()==identities}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"output":str(args.output),"passed":result["passed"],**summary},indent=2))
    return 0 if result["passed"] else 1


if __name__=="__main__":
    raise SystemExit(main())
