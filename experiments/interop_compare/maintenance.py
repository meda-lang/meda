#!/usr/bin/env python3
"""Matched repair packets and independent acceptance for a small demonstration.

Fresh repair agents are instruction-isolated, not filesystem-sandboxed. No
token/sampling/model identity is inferred. This is not the full Gate B study.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
from pathlib import Path
import sys

from clients import ARMS, ClientError, compile_client, invoke_client, source_path

ROOT=Path(__file__).resolve().parent


def snap(observation="pending",remaining=1,task_id="task-9",evidence="",answer="",stage="running"):
    return {"stage":stage,"observation":observation,"taskId":task_id,"remaining":remaining,
            "evidence":evidence,"input":answer}


def expected(action,task="task-9",payload=""):
    return {"action":action,"taskId":task,"payload":payload}


def acceptance_cases():
    # Authored independently of either client's branch implementation.
    return [
        ("start",snap("",1,"",stage="start"),expected("read","")),
        ("evidence",snap("evidence",1,"","evidence:42"),expected("submit","","evidence:42")),
        ("known_pending",snap(),expected("poll")),
        ("pending_budget_zero",snap(remaining=0),expected("stop",payload="budget")),
        ("unknown_delivery",snap("unknown",3,""),expected("stop","","unknown")),
        ("unknown_delivery_with_id",snap("unknown",0),expected("stop",payload="unknown")),
        ("input_missing",snap("input_required",3),expected("stop",payload="input_required")),
        ("input_supplied",snap("input_required",1,answer="answer-9"),expected("continue",payload="answer-9")),
        ("input_supplied_no_allowance",snap("input_required",0,answer="answer-9"),expected("stop",payload="budget")),
        ("completed_at_limit",snap("completed",0,evidence="report:42"),expected("stop",payload="report:42")),
        ("completed_above_limit",snap("completed",4,evidence="report:53"),expected("stop",payload="report:53")),
        ("cancelled",snap("cancelled",0),expected("stop",payload="cancelled")),
        ("denied",snap("denied",1),expected("stop",payload="denied")),
        ("invalid",snap("invalid",0),expected("stop",payload="invalid")),
        ("budget",snap("budget",1),expected("stop",payload="budget")),
        ("unknown_state",snap("new_peer_state",1),expected("stop",payload="unsupported")),
    ]


def supplemental_cases():
    # Added by independent review after final candidates, not preregistered.
    # Budget precedence for missing input is an explicitly recorded interpretation
    # of the original packet's 'preserve every other existing behavior' clause.
    return [
        ("start_budget_zero",snap("",0,"",stage="start"),expected("stop","","budget")),
        ("evidence_budget_zero",snap("evidence",0,"","evidence:42"),expected("stop","","budget")),
        ("input_missing_budget_zero",snap("input_required",0),expected("stop",payload="budget")),
    ]


TASKS={
    "uncertain_delivery": {
        "request":"Fix the unknown-delivery handling. Once a submission may have reached the peer, an unknown outcome must stop with payload unknown; it must never resubmit automatically. Preserve known pending polling and every other existing behavior.",
        "visible":["unknown_delivery","known_pending","completed_at_limit"],
    },
    "pending_input": {
        "request":"Fix missing-input handling. An existing task asking for input must stop with payload input_required when the answer is empty. A provided answer with remaining allowance must continue that same task. Never start a replacement task. Preserve every other existing behavior.",
        "visible":["input_missing","input_supplied","completed_at_limit"],
    },
    "budget_boundary": {
        "request":"Fix the request-budget boundary. Zero remaining allowance must prevent any new request, including a poll, read, submission, or continuation. A completed observation may still publish its result at zero allowance, and terminal errors retain their category. Preserve other behavior.",
        "visible":["pending_budget_zero","known_pending","completed_at_limit"],
    },
}


def broken_source(arm,task,source):
    if task=="budget_boundary":
        old="snapshot.remaining <= 0"
        new="snapshot.remaining < 0"
    elif task=="pending_input":
        if arm=="meda":
            old='return Decision { action: Action.Stop, taskId: snapshot.taskId, payload: "input_required" }'
            new='return Decision { action: Action.Submit, taskId: "", payload: snapshot.evidence }'
        else:
            old='return { action: "stop", taskId: snapshot.taskId, payload: "input_required" };'
            new='return { action: "submit", taskId: "", payload: snapshot.evidence };'
    else:
        if arm=="meda":
            old='operation next(snapshot: Snapshot) -> Decision effects [] {'
            new=old+'\n  if snapshot.observation == "unknown" {\n    return Decision { action: Action.Submit, taskId: "", payload: snapshot.evidence }\n  }'
        else:
            old='export function next(snapshot: Snapshot): Decision {'
            new=old+'\n  if (snapshot.observation === "unknown") {\n    return { action: "submit", taskId: "", payload: snapshot.evidence };\n  }'
    if source.count(old)!=1:
        raise RuntimeError(f"Mutation selector drift: {arm}/{task}")
    return source.replace(old,new)


def evaluate(arm,path,case_ids=None,supplemental=False):
    try:
        provenance=compile_client(arm,path)
    except Exception as error:
        return {"passed":False,"checkError":str(error),"cases":[]}
    rows=[]
    for case_id,snapshot,wanted in (supplemental_cases() if supplemental else acceptance_cases()):
        if case_ids is not None and case_id not in case_ids:
            continue
        try:
            got=invoke_client(arm,snapshot,path)
            rows.append({"id":case_id,"expected":wanted,"actual":got,"passed":got==wanted})
        except Exception as error:
            rows.append({"id":case_id,"passed":False,"error":str(error)})
    return {"passed":bool(rows) and all(r["passed"] for r in rows),"provenance":provenance,"cases":rows}


def prepare(directory):
    if directory.exists():
        raise RuntimeError("Refusing to overwrite existing trial packets")
    directory.mkdir(parents=True)
    rows=[]
    for task,definition in TASKS.items():
        for arm in ARMS:
            folder=directory/f"{task}-{arm}"
            folder.mkdir()
            filename="candidate.meda" if arm=="meda" else "candidate.ts"
            reference=source_path(arm).read_text()
            original=broken_source(arm,task,reference)
            candidate=folder/filename
            candidate.write_text(original)
            (folder/"starting-source.txt").write_text(original)
            packet={"id":task,"arm":arm,"request":definition["request"],"candidate":filename,
                    "visible":[{"id":name,"snapshot":snapshot,"expected":wanted}
                               for name,snapshot,wanted in acceptance_cases() if name in definition["visible"]]}
            (folder/"task.json").write_text(json.dumps(packet,indent=2)+"\n")
            relative_root=os.path.relpath(ROOT,folder.resolve())
            script=("import sys\nfrom pathlib import Path\n"
                    f"sys.path.insert(0, str((Path(__file__).resolve().parent / {relative_root!r}).resolve()))\nfrom maintenance import visible_check\n"
                    "raise SystemExit(visible_check(Path(__file__).resolve().parent))\n")
            (folder/"check.py").write_text(script)
            guide=("# Repair packet\n\nRead task.json and edit only "+filename+".\n"
                   "Run `python3 check.py` for visible checks. Keep the interface and existing declarations.\n"
                   "No imports, unsafe casts, dynamic code, or new I/O. Use the existing code style.\n"
                   "Do not inspect sibling trial folders, reference source, acceptance harness, or other project files.\n"
                   "The checker may invoke installed tools outside this directory; that does not authorize reading them.\n"
                   "Finish when your candidate is ready; do not change check.py or task.json.\n")
            if arm=="meda":
                guide+=("\nMeda uses named call arguments, immutable record values, `if`/`else`, `and`/`or`, "
                        "explicit `return`, and newline-terminated statements. Action cases are "
                        "`Action.Read`, `Action.Submit`, `Action.Poll`, `Action.Continue`, `Action.Cancel`, `Action.Stop`. "
                        "Records construct as `Decision { action: Action.Stop, taskId: snapshot.taskId, payload: \"unknown\" }`.\n")
            else:
                guide+="\nTypeScript is compiled with strict checking, explicit returns and a finite Action union.\n"
            (folder/"README.md").write_text(guide)
            pristine={name:hashlib.sha256((folder/name).read_bytes()).hexdigest()
                      for name in ("starting-source.txt","task.json","check.py","README.md")}
            (folder/"packet-hashes.json").write_text(json.dumps(pristine,indent=2)+"\n")
            broken=evaluate(arm,candidate)
            repaired=evaluate(arm,source_path(arm))
            rows.append({"task":task,"arm":arm,"startingRejected":not broken["passed"],
                         "referenceAccepted":repaired["passed"],"starting":broken,"reference":repaired})
    okay=all(r["startingRejected"] and r["referenceAccepted"] for r in rows)
    result={"kind":"reference_smoke_not_model_trial","tasks":len(TASKS),"rows":rows,"passed":okay}
    (directory/"smoke.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"prepared":str(directory),"rows":len(rows),"passed":okay}))
    return 0 if okay else 1


def visible_check(folder):
    packet=json.loads((folder/"task.json").read_text())
    result=evaluate(packet["arm"],folder/packet["candidate"],{r["id"] for r in packet["visible"]})
    with (folder/"visible-checks.jsonl").open("a") as stream:
        stream.write(json.dumps({"atUtc":datetime.now(timezone.utc).isoformat(),"result":result})+"\n")
    print(json.dumps(result,indent=2))
    return 0 if result["passed"] else 1


def collect(directory,output):
    rows=[]
    for folder in sorted(p for p in directory.iterdir() if p.is_dir()):
        packet=json.loads((folder/"task.json").read_text())
        candidate=folder/packet["candidate"]
        hashes=json.loads((folder/"packet-hashes.json").read_text())
        unchanged=all(hashlib.sha256((folder/name).read_bytes()).hexdigest()==digest for name,digest in hashes.items())
        result=evaluate(packet["arm"],candidate)
        supplemental=evaluate(packet["arm"],candidate,supplemental=True)
        before=(folder/"starting-source.txt").read_text().splitlines()
        after=candidate.read_text().splitlines()
        diff=list(difflib.unified_diff(before,after,lineterm=""))
        changed=sum(line.startswith(("+","-")) and not line.startswith(("+++","---")) for line in diff)
        checks=folder/"visible-checks.jsonl"
        rows.append({"task":packet["id"],"arm":packet["arm"],"packetUnchanged":unchanged,
                     "accepted":unchanged and result["passed"],"result":result,
                     "supplementalAfterReview":supplemental,
                     "visibleCheckCalls":len(checks.read_text().splitlines()) if checks.exists() else 0,
                     "changedLines":changed,"diff":diff,"candidateSha256":hashlib.sha256(candidate.read_bytes()).hexdigest()})
    result={"kind":"fresh_context_repair_demonstration","runAtUtc":datetime.now(timezone.utc).isoformat(),
            "controls":{"freshContext":True,"filesystemIsolation":"instruction_only_not_enforced",
                        "sampling":"not_exposed","modelVersion":"not_exposed","tokens":None,
                        "equalHardTimeBudgetEnforced":False,"hiddenAcceptanceFeedbackBeforeFinal":False,
                        "trialsPerTaskArm":1,"note":"Agent completions, not driver-enforced repeated model trials"},
            "summary":{"tasks":len(TASKS),"trials":len(rows),
                       "acceptedByArm":{arm:sum(r["accepted"] for r in rows if r["arm"]==arm) for arm in ARMS}},
            "trials":rows,"productivityConclusion":"inconclusive",
            "postTrialReview":"Three supplemental cases were added after candidates finalized. Missing input at zero allowance retains the original reference's budget precedence; the task packet was ambiguous about this intersection and was preserved unchanged."}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result["summary"],indent=2))
    return 0 if all(r["accepted"] and r["supplementalAfterReview"]["passed"] for r in rows) else 1


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    p=sub.add_parser("prepare");p.add_argument("directory",type=Path)
    p=sub.add_parser("collect");p.add_argument("directory",type=Path);p.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    raise SystemExit(prepare(args.directory) if args.command=="prepare" else collect(args.directory,args.output))
