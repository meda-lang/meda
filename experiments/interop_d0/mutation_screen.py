"""Reassess raw mutation receipts with explicit original/revised expectations.

Every failed check in the selected revision rejects the bounded screen. Both
assessments are retained; no acceptance failure is exempted or overwritten.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from . import oracle
from .acceptance_revisions import REVISIONS, canonical_sha256, load_inventory

HERE = Path(__file__).resolve().parent
CASE_IDS = frozenset({"W12-mutant-remove-grant", "W12-mutant-remove-quota",
                      "W12-client-repeat-submit", "W12-wrong-domain-validator"})


def summarize(document, revision="original"):
    inventory, provenance = load_inventory(revision)
    original, _ = load_inventory()
    if (document.get("profile") != inventory["profile"]
            or document.get("sourceSha256", {}).get("acceptance.json") != provenance["baseInventorySha256"]):
        raise ValueError("Receipt does not identify the pinned original inventory")
    cases = {case["id"]: case for case in inventory["cases"] if case["id"] in CASE_IDS}
    original_cases = {case["id"]: case for case in original["cases"] if case["id"] in CASE_IDS}
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
        original_assessment = (assessment if revision == "original" else
                               oracle.evaluate_case(original_cases[case_id], row["receipt"]))
        checks = {check["name"]: check["status"] for check in assessment["checks"]}
        required = {"outcomeCategory", "phase", "invariant.one_terminal", "invariant.attribution_recorded"}
        required.update("count." + name for name in cases[case_id]["expected"]["businessDispatches"])
        required.update({"count.peerTaskCreations", "count.successfulPublications"})
        required.add("invariant.unknown_not_refunded" if case_id == "W12-client-repeat-submit"
                     else "invariant.independent_mutant_detection")
        failed = sorted(name for name, status in checks.items() if status == "failed")
        verified = all(checks.get(name) == "passed" for name in required) and not failed
        results.append({"caseId": case_id, "behaviorVerified": verified,
                        "fullAcceptanceStatus": assessment["status"],
                        "failedFrozenChecks": failed,
                        "originalFullAcceptanceStatus": original_assessment["status"],
                        "originalFailedFrozenChecks": sorted(check["name"] for check in original_assessment["checks"]
                                                             if check["status"] == "failed"),
                        "unverifiedChecks": sorted(name for name, status in checks.items()
                                                   if status == "unverified")})
    unchanged = document.get("sourceUnchangedDuringRun") is True
    return {"kind": "bounded_mutation_screen", "acceptanceClosed": False,
            "evaluationMode": "receipt_reassessment", "acceptanceRevision": provenance,
            "receiptCanonicalSha256": canonical_sha256(document),
            "assessmentSourceSha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                                       for name in ("oracle.py", "acceptance_revisions.py", "mutation_screen.py")},
            "behavioralScreenPassed": unchanged and all(row["behaviorVerified"] for row in results),
            "sourceUnchangedDuringRun": unchanged,
            "fullAcceptanceStatusCounts": dict(Counter(row["fullAcceptanceStatus"] for row in results)),
            "originalFullAcceptanceStatusCounts": dict(Counter(row["originalFullAcceptanceStatus"] for row in results)),
            "medaSourceArmExecuted": False, "cases": results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--revision", choices=REVISIONS, default="original")
    args = parser.parse_args()
    result = summarize(json.loads(args.receipt.read_text()), revision=args.revision)
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["behavioralScreenPassed"] else 1)


if __name__ == "__main__":
    main()
