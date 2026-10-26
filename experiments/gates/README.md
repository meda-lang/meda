# Meda Gate A corpus and Gate B prototype

This directory turns the Draft 2.1 amendment into executable pure-language cases,
an experimental interpreter, guarded editing, and a paired maintenance harness.
It does not replace the legacy scanner or implement Meda Edition 1.

Run everything from the repository root:

```sh
python3 -m unittest discover -s experiments/gates/tests -v
python3 experiments/gates/benchmark.py --smoke --output /tmp/meda-smoke.json
```

No third-party dependencies or model API keys are required. See [PROFILE.md](PROFILE.md)
for supported syntax, constraints and commands, [PROTOCOL.md](PROTOCOL.md) for the
editing API, and [benchmark/PROTOCOL.md](benchmark/PROTOCOL.md) for trial design.

| Deliverable | Current evidence |
| --- | --- |
| Design amendment | [Draft 2.1](../../docs/design-draft-2.1.md) preserves the reviewed core and specifies focused fixes. |
| Executable Gate A subset | 55 source cases, run through the actual CLI with phase/code/value expectations. |
| Guarded editing | Direct/transitive contract-helper protection, scope rejection, independent checks, revision/receipt guards, single-file commit. |
| Gate B task corpus | 12 paired Meda/Python body-repair tasks with separate visible and acceptance cases. |
| Smoke evidence | 24 reference repairs accepted; all 24 starting programs rejected. No model trials. |
| Deferred work | [corpus/deferred.json](corpus/deferred.json) enumerates unimplemented acceptance decisions; these are not passes. |

The interpreter is Python to make the first semantic experiments executable with
no toolchain installation. The target reference implementation remains Rust.
The Python baseline has no third-party static checker, so the harness cannot yet
support an equally equipped language comparison. Gate A is implemented for this
declared profile; full corpus coverage and the Gate B decision remain open.

The acceptance model and fixtures are research code with finite input/fuel limits,
not a production compiler, security sandbox, formal proof, or edition-readiness
claim. Runtime tools/cancellation and replay cases are deferred to their gates.
