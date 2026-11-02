"""Apply one explicit erratum without rewriting the frozen D0 inventory."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_SHA256 = "724e5626054ced2ac444fcf759371fca43f5f91d1efcff09b2e67d205b2d9a8d"
REVISIONS = ("original", "attribution-1")
_CORRECTION = {
    "schema": "meda-acceptance-erratum/1",
    "id": "attribution-1",
    "baseInventorySha256": BASE_SHA256,
    "caseId": "W12-client-repeat-submit",
    "field": "attribution",
    "before": ["application", "independent_oracle"],
    "after": ["shared_host"],
}


def canonical_sha256(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def load_inventory(revision="original", *, inventory_path=HERE / "acceptance.json",
                   erratum_path=HERE / "acceptance-attribution-erratum.json"):
    """Return a fresh effective inventory plus its explicit revision provenance.

    This is deliberately not a general patch language. Any second correction,
    changed base, or different expected value requires a new reviewed revision.
    """
    if revision not in REVISIONS:
        raise ValueError("Unknown acceptance revision")
    raw = Path(inventory_path).read_bytes()
    base_hash = hashlib.sha256(raw).hexdigest()
    if base_hash != BASE_SHA256:
        raise ValueError("Frozen acceptance inventory hash does not match")
    inventory = json.loads(raw)
    erratum_hash = None
    if revision == "attribution-1":
        erratum_raw = Path(erratum_path).read_bytes()
        erratum = json.loads(erratum_raw)
        if (not isinstance(erratum, dict) or set(erratum) != set(_CORRECTION) | {"reason"}
                or any(erratum[key] != value for key, value in _CORRECTION.items())
                or not isinstance(erratum["reason"], str) or not erratum["reason"].strip()):
            raise ValueError("Erratum differs from the single approved attribution correction")
        matches = [case for case in inventory["cases"] if case["id"] == erratum["caseId"]]
        if len(matches) != 1 or matches[0].get("attribution") != erratum["before"]:
            raise ValueError("Erratum precondition does not match")
        matches[0]["attribution"] = list(erratum["after"])
        erratum_hash = hashlib.sha256(erratum_raw).hexdigest()
    return inventory, {"id": revision, "baseInventorySha256": base_hash,
                       "effectiveInventorySha256": canonical_sha256(inventory),
                       "erratumSha256": erratum_hash}
