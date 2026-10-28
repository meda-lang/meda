"""Execute frozen case scenarios and independently assess the resulting receipts.

The inventory remains immutable. Missing implementations and missing evidence
never receive passing credit. This is a TypeScript/shared-host pilot; it does
not execute the effectful Meda arm or a maintenance experiment.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time

from . import oracle, runner
from .freeze import runtime_source_paths

HERE = Path(__file__).resolve().parent

# These labels are deliberately fixed rather than derived from exception text,
# scenario values, endpoints, or protocol payloads.  They can therefore be
# retained in a public receipt without exposing credentials or private task
# references when an unexpected dependency exception escapes a case runner.
_EXECUTION_STAGES = {
    "workflow": "workflow_execution",
    "host_probe": "host_probe_execution",
    "adapter_probe": "adapter_probe_execution",
    "peer_probe": "peer_probe_execution",
}


def execute(case):
    surface = case["surface"]
    if surface == "workflow":
        return runner.execute_workflow(case["scenario"])
    if surface == "host_probe":
        from .acceptance_host import execute_host_probe
        return execute_host_probe(case["scenario"])
    if surface == "adapter_probe":
        from .acceptance_adapters import execute_adapter_probe
        return execute_adapter_probe(case["scenario"])
    if surface == "peer_probe":
        from .acceptance_peers import execute_peer_probe
        return execute_peer_probe(case["scenario"])
    raise runner.UnsupportedScenario("No executable implementation for " + surface)


def source_hashes():
    paths = [path for path in HERE.rglob("*") if path.is_file()
             and not any(part in {".venv", "node_modules", "dist", "__pycache__", "results"}
                         or part.startswith("ts-probe-") for part in path.relative_to(HERE).parts)]
    paths.extend(runtime_source_paths(HERE.parents[1]))
    return {os.path.relpath(path, HERE): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(paths) if path.is_file()}


def execute_case(case):
    """Execute and assess one case while retaining only safe failure metadata."""
    start = time.monotonic()
    row = {"caseId": case["id"], "surface": case["surface"], "scenario": case["scenario"]}
    stage = _EXECUTION_STAGES.get(case["surface"], "case_dispatch")
    try:
        row["receipt"] = execute(case)
        stage = "oracle_assessment"
        row["assessment"] = oracle.evaluate_case(case, row["receipt"])
        row["executionStatus"] = "executed"
    except runner.UnsupportedScenario as exc:
        row.update(executionStatus="not_run", reason=str(exc))
    except Exception as exc:
        # Never copy exception text: an unexpected library exception can
        # contain credentials or private reference data.  ``errorStage`` is a
        # closed, locally-authored label and not data supplied by the peer.
        row.update(executionStatus="execution_error", errorType=type(exc).__name__,
                   errorStage=stage)
    row["elapsedSeconds"] = time.monotonic() - start
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--surface", action="append")
    parser.add_argument("--case", action="append")
    args = parser.parse_args()
    inventory = json.loads((HERE / "acceptance.json").read_text())
    compiler = runner.compile_client()
    hashes = source_hashes()
    selected = [case for case in inventory["cases"]
                if (not args.surface or case["surface"] in args.surface)
                and (not args.case or case["id"] in args.case)]
    output = {"kind": "d0_reference_pilot", "profile": inventory["profile"],
              "startedAt": datetime.now(timezone.utc).isoformat(),
              "arms": ["typescript", "shared"], "medaExecuted": False,
              "maintenanceMeasured": False, "compiler": compiler,
              "sourceSha256": hashes, "inventoryCases": len(inventory["cases"]),
              "selectedCases": len(selected), "runs": []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for case in selected:
        row = execute_case(case)
        output["runs"].append(row)
        output["executionCounts"] = dict(Counter(item["executionStatus"] for item in output["runs"]))
        output["assessmentCounts"] = dict(Counter(item["assessment"]["status"] for item in output["runs"] if "assessment" in item))
        args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"caseId": case["id"], "executionStatus": row["executionStatus"],
                          "assessment": row.get("assessment", {}).get("status"),
                          "outcome": row.get("receipt", {}).get("result", {}).get("outcome")}), flush=True)
    output["finishedAt"] = datetime.now(timezone.utc).isoformat()
    output["sourceUnchangedDuringRun"] = hashes == source_hashes()
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
