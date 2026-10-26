"""Real Meda and strict TypeScript clients behind one checked JSON boundary.

This bridge is research tooling, not an effect runtime or security sandbox.
Both source programs are deliberately pure decision kernels. Runtime guards and
network behavior live in host.py, which the application source cannot override
through this API. Process supervision bounds ordinary accidental loops; it does
not contain malicious TypeScript that deliberately uses Node capabilities.
"""
from __future__ import annotations

import atexit
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
MEDA_CLI = ROOT.parent / "gates" / "meda.py"
ARMS = ("meda", "typescript")
SNAPSHOT_FIELDS = frozenset({"stage", "observation", "taskId", "remaining", "evidence", "input"})
DECISION_FIELDS = frozenset({"action", "taskId", "payload"})
ACTIONS = frozenset({"read", "submit", "poll", "continue", "cancel", "stop"})
MEDA_ACTION_CASES = {action.capitalize(): action for action in ACTIONS}
MAX_FIELD_BYTES = 16_384
MAX_REMAINING = 100_000
FLAGS = json.loads((ROOT / "toolchain.json").read_text())["typescriptFlags"]
_compiled: dict[tuple[str, str, str], dict] = {}
_temps: list[tempfile.TemporaryDirectory] = []
_tsc_versions: dict[str, str] = {}


class ClientError(Exception):
    def __init__(self, phase: str, message: str):
        self.phase = phase
        self.message = message
        super().__init__(f"{phase}: {message}")


def _cleanup():
    for temporary in _temps:
        temporary.cleanup()


atexit.register(_cleanup)


def _text(value):
    return (type(value) is str and not any(0xD800 <= ord(c) <= 0xDFFF for c in value)
            and len(value.encode("utf8")) <= MAX_FIELD_BYTES)


def validate_snapshot(snapshot: dict) -> None:
    if type(snapshot) is not dict or set(snapshot) != SNAPSHOT_FIELDS:
        raise ClientError("input", "Snapshot fields do not match the shared schema")
    if any(not _text(value) for key, value in snapshot.items() if key != "remaining"):
        raise ClientError("input", "Snapshot text fields must be bounded Unicode scalar strings")
    remaining = snapshot["remaining"]
    if type(remaining) is not int or not 0 <= remaining <= MAX_REMAINING:
        raise ClientError("input", "remaining must be an exact integer from 0 through 100000")


def validate_decision(decision: dict) -> None:
    if type(decision) is not dict or set(decision) != DECISION_FIELDS:
        raise ClientError("output", "Decision fields do not match the shared schema")
    if any(not _text(value) for value in decision.values()):
        raise ClientError("output", "Decision values must be bounded Unicode scalar strings")
    if decision["action"] not in ACTIONS:
        raise ClientError("output", "Unknown decision action")


def normalize_meda_decision(value: dict) -> dict:
    """Lossless enum codec only; the shared boundary still validates all fields."""
    if type(value) is not dict or set(value) != DECISION_FIELDS:
        raise ClientError("output", "Meda Decision fields do not match the shared schema")
    action = value["action"]
    if (type(action) is not dict or set(action) != {"case", "fields"}
            or type(action["case"]) is not str or action["case"] not in MEDA_ACTION_CASES
            or type(action["fields"]) is not dict or action["fields"]):
        raise ClientError("output", "Meda action is not a valid payload-free Action case")
    return {**value, "action": MEDA_ACTION_CASES[action["case"]]}


def _run(command: list[str], *, stdin: str | None = None, timeout: int = 15):
    try:
        return subprocess.run(command, input=stdin, text=True, encoding="utf8",
                              capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        raise ClientError("supervisor", "Client/checker wall-time limit exceeded") from error
    except OSError as error:
        raise ClientError("infrastructure", str(error)) from error


def _node() -> str:
    executable = shutil.which("node")
    if executable is None:
        raise ClientError("infrastructure", "Node is required; no automatic download is performed")
    return executable


def resolve_tsc() -> Path:
    candidate = os.environ.get("MEDA_COMPARE_TSC") or os.environ.get("TSC_PATH")
    compiler = Path(candidate) if candidate else ROOT / "node_modules" / "typescript" / "lib" / "tsc.js"
    if not compiler.is_file():
        raise ClientError("infrastructure", "Install pinned TypeScript 5.9.3 locally or set MEDA_COMPARE_TSC to tsc.js")
    resolved = str(compiler.resolve())
    if resolved not in _tsc_versions:
        result = _run([_node(), resolved, "--version"])
        version = result.stdout.strip()
        if result.returncode or version != "Version 5.9.3":
            raise ClientError("infrastructure", f"Expected TypeScript 5.9.3, found {version!r}")
        _tsc_versions[resolved] = version
    return Path(resolved)


def source_path(arm: str, path: str | Path | None = None) -> Path:
    if arm not in ARMS:
        raise ClientError("input", "arm must be meda or typescript")
    return Path(path).resolve() if path else ROOT / "clients" / ("policy.meda" if arm == "meda" else "policy.ts")


def _prepare(arm: str, path: str | Path | None = None) -> dict:
    source = source_path(arm, path)
    raw = source.read_bytes()
    if len(raw) > 128_000:
        raise ClientError("input", "Source exceeds research profile limit")
    digest = hashlib.sha256(raw).hexdigest()
    compiler = resolve_tsc() if arm == "typescript" else MEDA_CLI
    key = arm, digest, str(compiler)
    if key in _compiled:
        return _compiled[key]
    directory = tempfile.TemporaryDirectory(prefix=f"meda-compare-{arm}-")
    _temps.append(directory)
    staging = Path(directory.name)
    copied = staging / ("policy.meda" if arm == "meda" else "policy.ts")
    copied.write_bytes(raw)
    if arm == "meda":
        checked = _run([sys.executable, str(MEDA_CLI), "check", str(copied)])
        executable = copied
        checker = "meda-pure-b0/1"
    else:
        output = staging / "compiled"
        checked = _run([_node(), str(compiler), *FLAGS, "--outDir", str(output), str(copied)])
        executable = output / "policy.js"
        checker = "TypeScript 5.9.3 strict"
    if checked.returncode:
        raise ClientError("check", (checked.stdout + checked.stderr).strip())
    value = {"arm": arm, "source": str(source), "sha256": digest,
             "checker": checker, "executable": str(executable)}
    _compiled[key] = value
    return value


def compile_client(arm: str, path: str | Path | None = None) -> dict:
    """Check and freeze source bytes; return provenance, raising on failure."""
    compiled = _prepare(arm, path)
    return {**{key: value for key, value in compiled.items() if key != "executable"},
            "source": str(source_path(arm, path))}


def invoke_client(arm: str, snapshot: dict, path: str | Path | None = None) -> dict:
    """Run the actual checked source; both arms share input/output validators."""
    validate_snapshot(snapshot)
    compiled = _prepare(arm, path)
    if arm == "meda":
        result = _run([sys.executable, str(MEDA_CLI), "run", compiled["executable"],
                       "--operation", "next", "--arguments", json.dumps({"snapshot": snapshot}),
                       "--fuel", "100000"], timeout=5)
    else:
        result = _run([_node(), str(ROOT / "clients" / "invoke.cjs"), compiled["executable"]],
                      stdin=json.dumps(snapshot), timeout=5)
    if result.returncode:
        raise ClientError("runtime", (result.stdout + result.stderr).strip())
    try:
        output = json.loads(result.stdout)
        value = normalize_meda_decision(output["value"]) if arm == "meda" else output
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise ClientError("output", "Client emitted an invalid JSON envelope") from error
    validate_decision(value)
    return value


def check_source(arm: str, source: str) -> dict:
    """Run a checker probe using the same flags and real compiler as the clients."""
    with tempfile.TemporaryDirectory(prefix="meda-compare-probe-") as tmp:
        path = Path(tmp) / ("probe.meda" if arm == "meda" else "probe.ts")
        path.write_text(source)
        try:
            provenance = compile_client(arm, path)
            return {"accepted": True, "diagnostic": None, "checker": provenance["checker"]}
        except ClientError as error:
            if error.phase != "check":
                raise
            return {"accepted": False, "diagnostic": error.message}


def checker_probes() -> list[dict]:
    """Matched semantic probes; no claim that this is a whole-language comparison."""
    samples = {
        "wrong_field_type": {
            "meda": 'record R { value: Text }\noperation main() -> R effects [] { return R { value: 1 } }\n',
            "typescript": 'type R = Readonly<{value: string}>;\nexport function main(): R { return {value: 1}; }\n',
        },
        "missing_record_field": {
            "meda": 'record R { value: Text, id: Text }\noperation main() -> R effects [] { return R { value: "x" } }\n',
            "typescript": 'type R = Readonly<{value: string; id: string}>;\nexport function main(): R { return {value: "x"}; }\n',
        },
        "missing_enum_case": {
            "meda": 'enum State { Ready, Pending }\noperation main(state: State) -> Text effects [] {\n  match state {\n    State.Ready => { return "ready" }\n  }\n}\n',
            "typescript": 'type State = "ready" | "pending";\nexport function main(state: State): string { switch (state) { case "ready": return "ready"; } }\n',
        },
        "misspelled_action": {
            "meda": 'enum Action { Read, Poll }\noperation main() -> Action effects [] { return Action.Pol }\n',
            "typescript": 'type Action = "read" | "poll";\nexport function main(): Action { return "pol"; }\n',
        },
        "complete_enum_cases": {
            "meda": 'enum State { Ready, Pending }\noperation main(state: State) -> Text effects [] {\n  match state {\n    State.Ready => { return "ready" }\n    State.Pending => { return "pending" }\n  }\n}\n',
            "typescript": 'type State = "ready" | "pending";\nexport function main(state: State): string { switch (state) { case "ready": return "ready"; case "pending": return "pending"; } }\n',
        },
    }
    return [{"id": name, "expectedAccepted": name == "complete_enum_cases",
             "arms": {arm: check_source(arm, text) for arm, text in paired.items()}}
            for name, paired in samples.items()]


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("arm", choices=ARMS)
    parser.add_argument("--source")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        value = compile_client(args.arm, args.source) if args.check else invoke_client(args.arm, json.load(sys.stdin), args.source)
        print(json.dumps(value, sort_keys=True))
    except ClientError as error:
        print(json.dumps({"error": error.phase, "message": error.message}))
        raise SystemExit(2)
