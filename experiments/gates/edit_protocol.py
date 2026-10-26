"""Single-file guarded edit protocol for a trusted experimental host.

Grants and checks are loaded by the host, not accepted over the editing stream.
Publication uses a cooperative lock and atomic replacement. This is not an OS
sandbox or the full edition's durable multi-file publication protocol.
"""
from __future__ import annotations

import copy
import fcntl
import json
import os
from pathlib import Path
import tempfile
import time
import uuid
import sys

from meda_core import Diagnostic, Evaluator, Program, PROFILE, digest, format_source, run_tests


def read_utf8(path):
    return Path(path).read_bytes().decode("utf-8")


def atomic_write(path, text):
    path = Path(path)
    fd, name = tempfile.mkstemp(prefix=".meda-stage-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            os.chmod(name, path.stat().st_mode & 0o777)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class Host:
    def __init__(self, source_path, grant_path):
        self.path = Path(source_path).resolve()
        self.grant_path = Path(grant_path).resolve()
        self.grant_text = read_utf8(self.grant_path)
        self.grant = json.loads(self.grant_text)
        required = {"version", "grantId", "baseRevision", "allowedTargets", "allowSpecificationRoots", "checkFile", "checkDigest", "testIds", "expiresAt"}
        if set(self.grant) != required or self.grant["version"] != 1:
            raise Diagnostic("InvalidGrant", "Unexpected grant schema.", phase="edit")
        if not isinstance(self.grant["allowedTargets"], list) or not self.grant["allowedTargets"]:
            raise Diagnostic("InvalidGrant", "Grant needs allowed operation names.", phase="edit")
        for key in ("allowedTargets", "allowSpecificationRoots", "testIds"):
            value = self.grant[key]
            if not isinstance(value, list) or any(not isinstance(v, str) for v in value) or len(value) != len(set(value)):
                raise Diagnostic("InvalidGrant", f"{key} must contain distinct strings.", phase="edit")
        if any(not isinstance(self.grant[key], str) for key in ("grantId", "baseRevision", "checkFile", "checkDigest")):
            raise Diagnostic("InvalidGrant", "Invalid grant string field.", phase="edit")
        if self.grant["expiresAt"] is not None and type(self.grant["expiresAt"]) not in (int, float):
            raise Diagnostic("InvalidGrant", "Expiry must be a timestamp or null.", phase="edit")
        self.check_path = (self.grant_path.parent / self.grant["checkFile"]).resolve()
        self.check_text = read_utf8(self.check_path)
        if digest(self.check_text) != self.grant["checkDigest"]:
            raise Diagnostic("CheckChanged", "Required check definition changed.", phase="edit")
        self.checks = json.loads(self.check_text)
        ids = [case["id"] for case in self.checks]
        if not self.checks or len(ids) != len(set(ids)):
            raise Diagnostic("TestDiscovery", "Acceptance cases must be nonempty with unique IDs.", phase="edit")
        self.transactions = {}
        self.engine_digest = digest({"python": sys.version, "sources": {
            name: read_utf8(Path(__file__).parent / name)
            for name in ("meda_core.py", "edit_protocol.py")}})

    def guard(self, expected):
        if self.grant["expiresAt"] is not None and time.time() >= self.grant["expiresAt"]:
            raise Diagnostic("ExpiredGrant", "Edit grant has expired.", phase="edit")
        if read_utf8(self.grant_path) != self.grant_text:
            raise Diagnostic("GrantChanged", "Host grant file changed.", phase="edit")
        if read_utf8(self.check_path) != self.check_text:
            raise Diagnostic("CheckChanged", "Acceptance check file changed.", phase="edit")
        if digest(read_utf8(self.path)) != expected:
            raise Diagnostic("StaleRevision", "Workspace revision changed.", phase="edit")

    def describe(self, symbol):
        source = read_utf8(self.path)
        p = Program(source)
        if symbol not in p.ops:
            raise Diagnostic("UnknownOperation", symbol)
        op = p.ops[symbol]
        dependencies = sorted(p.dependencies[symbol])
        return {"symbol": symbol, "revision": digest(source), "profile": PROFILE,
                "params": op.params, "output": op.output, "effects": [],
                "source": source[op.start:op.body_end],
                "dependencies": {name: p.definition(name) for name in dependencies},
                "affectedSpecificationRoots": [root for root, data in p.specification().items() if symbol in data["dependencies"]],
                "tests": list(p.p.tests), "requiredCheckIds": [c["id"] for c in self.checks]}

    def begin_edit(self, expectedRevision):
        self.guard(expectedRevision)
        if expectedRevision != self.grant["baseRevision"]:
            raise Diagnostic("GrantRevision", "Grant does not cover this revision.", phase="edit")
        source = read_utf8(self.path)
        Program(source)
        tx = uuid.uuid4().hex
        self.transactions[tx] = {"base": source, "staged": source, "status": "open", "receipt": None}
        return {"transaction": tx, "revision": expectedRevision}

    def transaction(self, tx):
        if tx not in self.transactions:
            raise Diagnostic("UnknownTransaction", "No such active-process transaction.", phase="edit")
        return self.transactions[tx]

    def replace_body(self, transaction, symbol, body):
        tx = self.transaction(transaction)
        if tx["status"] == "committed":
            raise Diagnostic("TransactionClosed", "Transaction already committed.", phase="edit")
        if symbol not in self.grant["allowedTargets"]:
            raise Diagnostic("EditScope", "Target is outside the grant.", phase="edit")
        from meda_core import Parser
        p = Parser(tx["staged"]).parse()
        if symbol not in p.ops:
            raise Diagnostic("EditScope", "Unknown target.", phase="edit")
        op = p.ops[symbol]
        if not isinstance(body, str) or not body.strip().startswith("{"):
            raise Diagnostic("EditScope", "Body must be a complete block.", phase="edit")
        candidate = tx["staged"][:op.body_start] + body + tx["staged"][op.body_end:]
        # Parse first so invalid candidates can be repaired without publishing them.
        parsed = Parser(candidate).parse()
        if set(parsed.ops) != set(p.ops) or symbol not in parsed.ops:
            raise Diagnostic("EditScope", "Body payload changed declarations.", phase="edit")
        new_op = parsed.ops[symbol]
        # Mask only the selected body. Every other source byte must be unchanged.
        before = tx["staged"][:op.body_start] + "<BODY>" + tx["staged"][op.body_end:]
        after = candidate[:new_op.body_start] + "<BODY>" + candidate[new_op.body_end:]
        if before != after:
            raise Diagnostic("EditScope", "Body payload changed protected source.", phase="edit")
        tx.update(staged=candidate, status="open", receipt=None)
        return {"transaction": transaction, "stagedRevision": digest(candidate)}

    def validate_edit(self, transaction):
        tx = self.transaction(transaction)
        if tx["status"] == "committed":
            raise Diagnostic("TransactionClosed", "Transaction already committed.", phase="edit")
        self.guard(digest(tx["base"]))
        old, new = Program(tx["base"]), Program(tx["staged"])
        old_spec, new_spec = old.specification(), new.specification()
        affected = [root for root in sorted(set(old_spec) | set(new_spec)) if old_spec.get(root) != new_spec.get(root)]
        unauthorized = set(affected) - set(self.grant["allowSpecificationRoots"])
        if unauthorized:
            raise Diagnostic("SpecificationChange", "Protected roots changed: " + ", ".join(sorted(unauthorized)), phase="edit")
        # Tests in the source are optional, but the discovery set is always pinned.
        if set(new.p.tests) != set(self.grant["testIds"]):
            raise Diagnostic("TestDiscovery", "Source test set changed.", phase="edit")
        tests = run_tests(new, self.grant["testIds"]) if self.grant["testIds"] else []
        cases = acceptance(new, self.checks)
        if any(t["status"] != "pass" for t in tests + cases):
            tx["receipt"] = None
            return {"status": "failed", "tests": tests, "checks": cases, "specificationRoots": affected}
        # Formatting must preserve executable meaning and comments outside edited bodies.
        # Formatting is a separate operation in b0; body publication preserves all other bytes.
        receipt = {"transaction": transaction, "baseRevision": digest(tx["base"]),
                   "stagedRevision": digest(tx["staged"]), "grantDigest": digest(self.grant_text),
                   "checkDigest": digest(self.check_text), "engineDigest": self.engine_digest,
                   "profile": PROFILE, "specificationRoots": affected, "tests": tests, "checks": cases}
        receipt["receiptId"] = digest(receipt)
        tx.update(receipt=copy.deepcopy(receipt), status="validated")
        return {"status": "validated", **receipt}

    def commit_edit(self, transaction, receiptId, expectedRevision):
        tx = self.transaction(transaction)
        if tx["status"] == "committed":
            raise Diagnostic("TransactionClosed", "Use transaction_status to reconcile.", phase="edit")
        receipt = tx["receipt"]
        if not receipt or receipt["receiptId"] != receiptId or digest(tx["staged"]) != receipt["stagedRevision"]:
            raise Diagnostic("InvalidReceipt", "A current successful validation receipt is required.", phase="edit")
        if expectedRevision != digest(tx["base"]):
            raise Diagnostic("StaleRevision", "Wrong expected revision.", phase="edit")
        lock = self.path.with_suffix(self.path.suffix + ".lock")
        with lock.open("a") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            self.guard(expectedRevision)
            atomic_write(self.path, tx["staged"])
            tx["status"] = "committed"
        return {"status": "committed", "revision": digest(tx["staged"])}

    def transaction_status(self, transaction):
        tx = self.transaction(transaction)
        return {"status": tx["status"], "stagedRevision": digest(tx["staged"]),
                "workspaceRevision": digest(read_utf8(self.path))}


def acceptance(program, checks):
    results = []
    for case in checks:
        try:
            value = Evaluator(program, case.get("fuel", 100_000)).invoke(case["operation"], case["arguments"])
            passed = "error" not in case and "expected" in case and same_value(value, case["expected"])
            results.append({"id": case["id"], "status": "pass" if passed else "fail"})
        except Diagnostic as error:
            results.append({"id": case["id"], "status": "pass" if error.code == case.get("error") else "fail", "code": error.code})
    return results


def same_value(actual, expected):
    """JSON oracle equality is type-sensitive at every depth (True is not 1)."""
    if type(actual) is not type(expected):
        return False
    if isinstance(actual, list):
        return len(actual) == len(expected) and all(same_value(a, b) for a, b in zip(actual, expected))
    if isinstance(actual, dict):
        return set(actual) == set(expected) and all(same_value(actual[k], expected[k]) for k in actual)
    return actual == expected
