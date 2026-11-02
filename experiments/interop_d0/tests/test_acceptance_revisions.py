"""A versioned correction may change attribution, never frozen behavior."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from experiments.interop_d0 import acceptance_revisions as revisions


HERE = Path(__file__).resolve().parents[1]
INVENTORY = HERE / "acceptance.json"
ERRATUM = HERE / "acceptance-attribution-erratum.json"
BASE_SHA = "724e5626054ced2ac444fcf759371fca43f5f91d1efcff09b2e67d205b2d9a8d"
CASE_ID = "W12-client-repeat-submit"


class AcceptanceRevisionTests(unittest.TestCase):
    def test_original_inventory_is_byte_pinned_and_unchanged(self):
        before = INVENTORY.read_bytes()
        inventory, provenance = revisions.load_inventory()
        self.assertEqual(hashlib.sha256(before).hexdigest(), BASE_SHA)
        self.assertEqual(inventory, json.loads(before))
        self.assertEqual(provenance["id"], "original")
        self.assertEqual(provenance["baseInventorySha256"], BASE_SHA)
        self.assertEqual(INVENTORY.read_bytes(), before)

    def test_erratum_changes_only_the_one_attribution_field(self):
        original, original_provenance = revisions.load_inventory("original")
        revised, provenance = revisions.load_inventory("attribution-1")
        expected = copy.deepcopy(original)
        case = next(case for case in expected["cases"] if case["id"] == CASE_ID)
        self.assertEqual(case["attribution"], ["application", "independent_oracle"])
        case["attribution"] = ["shared_host"]
        self.assertEqual(revised, expected)
        self.assertEqual(provenance["id"], "attribution-1")
        self.assertEqual(provenance["baseInventorySha256"], BASE_SHA)
        self.assertEqual(provenance["erratumSha256"], hashlib.sha256(ERRATUM.read_bytes()).hexdigest())
        self.assertNotEqual(provenance["effectiveInventorySha256"],
                            original_provenance["effectiveInventorySha256"])
        # Returned inventories must not be cached aliases that callers can alter.
        revised_case = next(case for case in revised["cases"] if case["id"] == CASE_ID)
        revised_case["expected"]["peerTaskCreations"]["max"] = 9
        again, _ = revisions.load_inventory("attribution-1")
        self.assertEqual(again, expected)
        self.assertEqual(revisions.load_inventory("original")[0], original)

    def test_changed_inventory_bytes_require_a_new_reviewed_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "acceptance.json"
            path.write_bytes(INVENTORY.read_bytes() + b"\n")
            with self.assertRaises(ValueError):
                revisions.load_inventory("attribution-1", inventory_path=path)

    def test_erratum_cannot_change_another_field_case_or_allow_more_layers(self):
        mutations = [
            ("field", "expected.peerTaskCreations.max"),
            ("caseId", "W12-wrong-domain-validator"),
            ("before", ["shared_host"]),
            ("after", ["shared_host", "application"]),
            ("after", ["application"]),
            ("baseInventorySha256", "0" * 64),
            ("id", "attribution-2"),
            ("schema", "unreviewed-schema"),
            ("additionalChanges", {"normalRequests": 100}),
        ]
        for key, value in mutations:
            with self.subTest(field=key, value=value), tempfile.TemporaryDirectory() as directory:
                content = json.loads(ERRATUM.read_text())
                content[key] = value
                path = Path(directory) / "erratum.json"
                path.write_text(json.dumps(content))
                with self.assertRaises(ValueError):
                    revisions.load_inventory("attribution-1", erratum_path=path)

    def test_unknown_revision_cannot_silently_select_original_or_latest(self):
        for revision in ("latest", "attribution-2", "", None):
            with self.subTest(revision=revision), self.assertRaises(ValueError):
                revisions.load_inventory(revision)

    def test_missing_erratum_fields_do_not_apply_a_partial_correction(self):
        for key in ("before", "after", "caseId", "baseInventorySha256"):
            with self.subTest(field=key), tempfile.TemporaryDirectory() as directory:
                content = json.loads(ERRATUM.read_text())
                del content[key]
                path = Path(directory) / "erratum.json"
                path.write_text(json.dumps(content))
                with self.assertRaises(ValueError):
                    revisions.load_inventory("attribution-1", erratum_path=path)
