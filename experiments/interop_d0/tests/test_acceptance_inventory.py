"""Validate the independent D0 acceptance specification, not workflow execution.

Actual run receipts belong in separate result files. Passing this module proves
only that the planned oracle inventory is structurally consistent.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import re
import unittest


INVENTORY = Path(__file__).resolve().parents[1] / "acceptance.json"
FAMILIES = {f"W{number:02d}" for number in range(1, 13)}
OPERATIONS = {
    "readEvidence", "submit", "observe", "provideInput", "cancel", "cleanupCancel"
}
ARMS = {"meda", "typescript", "shared"}
SURFACES = {
    "workflow", "source_check", "source_mutant", "host_probe", "peer_probe",
    "adapter_probe", "host_mutant",
}
LAYERS = {
    "shared_host", "shared_adapter", "application", "remote_peer",
    "language_checker", "independent_oracle",
}


def validate_inventory(document: object) -> list[str]:
    """Return errors without admitting missing/unsupported cases as successes."""
    errors: list[str] = []
    if not isinstance(document, dict):
        return ["inventory must be an object"]
    if document.get("inventoryVersion") != "interop-d0-acceptance/1":
        errors.append("unsupported inventory version")
    if document.get("profile") != "meda-interop-d0/1":
        errors.append("wrong profile")
    if document.get("status") != "draft_pending_dependency_freeze":
        errors.append("inventory cannot claim execution readiness")
    pins = document.get("protocolPins", {})
    if pins != {
        "mcp": "2026-07-28", "mcpTransport": "streamable-http",
        "a2a": "1.0.0", "a2aTransport": "json-rpc-http",
    }:
        errors.append("protocol pin changed without a new inventory version")
    execution = document.get("execution", {})
    if not isinstance(execution, dict) or execution.get("status") != "not_run":
        errors.append("inventory is not an execution receipt")
    else:
        for name in ("supportedCaseCount", "passedCaseCount", "failedCaseCount"):
            if name not in execution or execution[name] is not None:
                errors.append(f"{name} must remain unknown before separate execution")
    for name in ("counting", "defaults", "fixtures", "invariantDefinitions"):
        if not isinstance(document.get(name), dict) or not document[name]:
            errors.append(f"missing {name}")
    for name in ("outcomeCategories", "phases", "witnessKinds"):
        values = document.get(name)
        if not isinstance(values, list) or not values or not all(
            isinstance(value, str) and value for value in values
        ):
            errors.append(f"invalid {name}")
    if errors:
        return errors

    invariant_definitions = document["invariantDefinitions"]
    if not all(isinstance(k, str) and isinstance(v, str) and v.strip()
               for k, v in invariant_definitions.items()):
        errors.append("invariant definitions must be named, nonempty predicates")
    cases = document.get("cases")
    if not isinstance(cases, list) or not cases:
        return errors + ["cases must be a nonempty list"]
    seen: set[str] = set()
    covered: set[str] = set()

    def bounds(value: object, label: str) -> None:
        if not isinstance(value, dict) or set(value) != {"min", "max"}:
            errors.append(f"{label}: require explicit min/max bounds")
        elif any(type(value[k]) is not int for k in ("min", "max")):
            errors.append(f"{label}: bounds must be integers, not booleans")
        elif value["min"] < 0 or value["max"] < value["min"]:
            errors.append(f"{label}: invalid bounds")

    for index, case in enumerate(cases):
        label = f"case[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{label}: must be an object")
            continue
        case_id = case.get("id")
        if not isinstance(case_id, str) or not re.fullmatch(r"W\d{2}-[A-Za-z0-9_-]+", case_id):
            errors.append(f"{label}: invalid ID")
        else:
            label = case_id
            if case_id in seen:
                errors.append(f"{label}: duplicate ID")
            seen.add(case_id)
        family = case.get("family")
        if family not in FAMILIES:
            errors.append(f"{label}: unknown family")
        else:
            covered.add(family)
            if not isinstance(case_id, str) or not case_id.startswith(family + "-"):
                errors.append(f"{label}: ID/family mismatch")
        surface = case.get("surface")
        if surface not in SURFACES:
            errors.append(f"{label}: invalid surface")
        arms = case.get("arms")
        if not isinstance(arms, list) or not arms or any(a not in ARMS for a in arms):
            errors.append(f"{label}: invalid arms")
            continue
        if len(set(arms)) != len(arms):
            errors.append(f"{label}: duplicate arm")
        if case.get("executionStatus") != "not_run":
            errors.append(f"{label}: inventory cannot claim a run result")
        support = case.get("support")
        if not isinstance(support, dict) or set(support) != set(arms):
            errors.append(f"{label}: explicit per-arm support state required")
        else:
            for arm in arms:
                expected_support = "blocked_effectful_profile" if arm == "meda" else "pending_implementation"
                if support[arm] != expected_support:
                    errors.append(f"{label}: unsupported arm cannot count as implemented")
        if not isinstance(case.get("scenario"), dict) or not case["scenario"]:
            errors.append(f"{label}: concrete scenario required")
        attribution = case.get("attribution")
        if not isinstance(attribution, list) or not attribution or any(
            layer not in LAYERS for layer in attribution
        ):
            errors.append(f"{label}: invalid layer attribution")
        requirements = case.get("requirements")
        if not isinstance(requirements, list) or not all(isinstance(x, str) for x in requirements):
            errors.append(f"{label}: requirements must be a list")

        expected = case.get("expected")
        if not isinstance(expected, dict):
            errors.append(f"{label}: expected observations required")
            continue
        if expected.get("phase") not in document["phases"]:
            errors.append(f"{label}: unknown expected phase")
        outcome = expected.get("outcomeCategory")
        if outcome not in document["outcomeCategories"]:
            errors.append(f"{label}: unknown outcome category")
        dispatches = expected.get("businessDispatches")
        if not isinstance(dispatches, dict) or set(dispatches) != OPERATIONS:
            errors.append(f"{label}: all business counters must be explicit")
        else:
            for operation, value in dispatches.items():
                bounds(value, f"{label}.{operation}")
        for counter in ("peerTaskCreations", "successfulPublications"):
            bounds(expected.get(counter), f"{label}.{counter}")
        for name, registry in (
            ("invariants", invariant_definitions),
            ("witnesses", document["witnessKinds"]),
        ):
            refs = expected.get(name)
            if not isinstance(refs, list) or not refs or not all(
                isinstance(ref, str) and ref in registry for ref in refs
            ):
                errors.append(f"{label}: invalid {name} references")
            elif len(set(refs)) != len(refs):
                errors.append(f"{label}: duplicate {name}")
        if "fixtureRef" in expected and expected["fixtureRef"] not in document["fixtures"]:
            errors.append(f"{label}: invalid fixture reference")
        if outcome == "success" and expected.get("fixtureRef") != "report":
            errors.append(f"{label}: successful workflow requires an independent report fixture")
        if surface == "source_check":
            if expected.get("phase") != "check" or not requirements:
                errors.append(f"{label}: source checks require a checker prerequisite and phase")
            values = list((dispatches or {}).values()) + [
                expected.get("peerTaskCreations"), expected.get("successfulPublications")
            ]
            if any(value != {"min": 0, "max": 0} for value in values):
                errors.append(f"{label}: check-only probes cannot dispatch or publish")
        if surface.endswith("mutant") and outcome == "mutation_detected":
            if "independent_mutant_detection" not in expected.get("invariants", []):
                errors.append(f"{label}: mutant requires an independent detection oracle")
    if covered != FAMILIES:
        errors.append("incomplete W01-W12 family coverage")
    return errors


class AcceptanceInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inventory = json.loads(INVENTORY.read_text())

    def changed(self) -> dict:
        return copy.deepcopy(self.inventory)

    def test_planned_inventory_is_consistent(self) -> None:
        self.assertEqual(validate_inventory(self.inventory), [])

    def test_validation_does_not_manufacture_execution_counts(self) -> None:
        before = copy.deepcopy(self.inventory)
        validate_inventory(self.inventory)
        self.assertEqual(self.inventory, before)
        self.assertIsNone(self.inventory["execution"]["passedCaseCount"])

    def test_claimed_success_is_rejected(self) -> None:
        document = self.changed()
        document["cases"][0]["executionStatus"] = "passed"
        self.assertTrue(validate_inventory(document))
        document = self.changed()
        document["execution"]["passedCaseCount"] = 0
        self.assertTrue(validate_inventory(document))

    def test_missing_family_and_duplicate_ids_are_rejected(self) -> None:
        document = self.changed()
        document["cases"] = [c for c in document["cases"] if c["family"] != "W10"]
        self.assertTrue(validate_inventory(document))
        document = self.changed()
        document["cases"].append(copy.deepcopy(document["cases"][0]))
        self.assertTrue(validate_inventory(document))

    def test_unresolved_predicate_witness_and_fixture_are_rejected(self) -> None:
        for field, value in (
            ("invariants", ["unwritten_predicate"]),
            ("witnesses", ["unavailable_witness"]),
            ("fixtureRef", "missing_fixture"),
        ):
            with self.subTest(field=field):
                document = self.changed()
                document["cases"][0]["expected"][field] = value
                self.assertTrue(validate_inventory(document))

    def test_counter_bounds_cannot_be_missing_negative_or_boolean(self) -> None:
        for value in ({"min": 1}, {"min": -1, "max": 0}, {"min": 2, "max": 1},
                      {"min": False, "max": True}):
            with self.subTest(value=value):
                document = self.changed()
                document["cases"][0]["expected"]["peerTaskCreations"] = value
                self.assertTrue(validate_inventory(document))

    def test_source_check_cannot_claim_side_effects_or_implementation(self) -> None:
        document = self.changed()
        case = next(c for c in document["cases"] if c["surface"] == "source_check")
        case["expected"]["businessDispatches"]["submit"] = {"min": 1, "max": 1}
        self.assertTrue(validate_inventory(document))
        document = self.changed()
        case = next(c for c in document["cases"] if c["surface"] == "source_check")
        case["support"]["meda"] = "implemented"
        self.assertTrue(validate_inventory(document))

    def test_mutant_without_detection_oracle_is_rejected(self) -> None:
        document = self.changed()
        case = next(c for c in document["cases"] if c["surface"] == "host_mutant")
        case["expected"]["invariants"].remove("independent_mutant_detection")
        self.assertTrue(validate_inventory(document))

    def test_protocol_changes_require_explicit_inventory_revision(self) -> None:
        document = self.changed()
        document["protocolPins"]["mcp"] = "2025-11-25"
        self.assertTrue(validate_inventory(document))


if __name__ == "__main__":
    unittest.main()
