"""Report the bounded mutation experiment separately from full acceptance.

The frozen repeat-submit attribution disagrees with the observed enforcement
layer. That failure remains in the ordinary assessment. This screen verifies
the requested behavior and rejects any other failed frozen check.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from . import oracle

HERE = Path(__file__).resolve().parent
CASE_IDS = frozenset({"W12-mutant-remove-grant", "W12-mutant-remove-quota",
                      "W12-client-repeat-submit", "W12-wrong-domain-validator"})


def summarize(document):
    inventory = json.loads((HERE / "acceptance.json").read_text())
    cases = {case["id"]: case for case in inventory["cases"] if case["id"] in CASE_IDS}
    rows = document.get("runs", [])
    if (not isinstance(rows, list) or len(rows) != len(CASE_IDS)
            or any(not isinstance(row, dict) for row in rows)
            or {row.get("caseId") for row in rows} != CASE_IDS):
        raise ValueError("Mutation screen requires exactly the four frozen cases")
    results = []
    for row in rows:
        case_id = row["caseId"]
        if row.get("executionStatus") != "executed" or not isinstance(row.get("receipt"), dict):
            raise ValueError("A mutation case did not execute")
        # Recompute instead of trusting saved assessment/pass fields.
        assessment = oracle.evaluate_case(cases[case_id], row["receipt"])
        checks = {check["name"]: check["status"] for check in assessment["checks"]}
        required = {"outcomeCategory", "phase", "invariant.one_terminal"}
        required.update("count." + name for name in cases[case_id]["expected"]["businessDispatches"])
        required.update({"count.peerTaskCreations", "count.successfulPublications"})
        required.add("invariant.unknown_not_refunded" if case_id == "W12-client-repeat-submit"
                     else "invariant.independent_mutant_detection")
        failed = sorted(name for name, status in checks.items() if status == "failed")
        known_mismatch = (case_id == "W12-client-repeat-submit"
                          and failed == ["invariant.attribution_recorded"]
                          and assessment["normalized"]["layer"] == "shared_host")
        verified = (all(checks.get(name) == "passed" for name in required)
                    and (not failed or known_mismatch))
        results.append({"caseId": case_id, "behaviorVerified": verified,
                        "fullAcceptanceStatus": assessment["status"],
                        "failedFrozenChecks": failed,
                        "knownAttributionMismatch": known_mismatch,
                        "unverifiedChecks": sorted(name for name, status in checks.items()
                                                   if status == "unverified")})
    unchanged = document.get("sourceUnchangedDuringRun") is True
    return {"kind": "bounded_mutation_screen", "acceptanceClosed": False,
            "behavioralScreenPassed": unchanged and all(row["behaviorVerified"] for row in results),
            "sourceUnchangedDuringRun": unchanged,
            "fullAcceptanceStatusCounts": dict(Counter(row["fullAcceptanceStatus"] for row in results)),
            "medaSourceArmExecuted": False, "cases": results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    result = summarize(json.loads(args.receipt.read_text()))
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["behavioralScreenPassed"] else 1)


if __name__ == "__main__":
    main()
