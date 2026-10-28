# Direct Meda versus TypeScript decision screen

Real Meda source now calls the same shared host as the TypeScript application.
The host talks to official MCP and A2A SDK peers over local TLS. The peers remain
deterministic fixtures; this example makes no LLM provider calls.

Start with [workflow.meda](workflow.meda), the existing
[TypeScript workflow](../interop_d0/client/workflow.ts), or the
[decision and results](../../docs/decision-screen-results.md).

## Run one Meda workflow

Requirements are unchanged from [the SDK reference](../interop_d0/README.md):
Linux x86_64 with glibc 2.34+, CPython 3.12, Node 24, and OpenSSL 3. From the
repository root:

```sh
python3 -m venv experiments/interop_d0/.venv
experiments/interop_d0/.venv/bin/python -m pip install --require-hashes --only-binary=:all: -r experiments/interop_d0/requirements.lock
npm ci --ignore-scripts --prefix experiments/interop_d0
experiments/interop_d0/.venv/bin/python -m experiments.decision_screen.run --case S1-success --output experiments/decision_screen/generated-results/one-workflow.json
```

This runs both applications and prints their reports plus independent assessments.
The successful report selects `f1=blue` and `f2=square` from `evidence-42`.
Output paths must be new: the runner refuses to overwrite a receipt.

## Run the bounded comparison

```sh
experiments/interop_d0/.venv/bin/python -m experiments.decision_screen.run --output experiments/decision_screen/generated-results/baseline.json
experiments/interop_d0/.venv/bin/python -m experiments.decision_screen.static_checks > experiments/decision_screen/generated-results/static-checks.json
experiments/interop_d0/.venv/bin/python experiments/decision_screen/maintenance/collect.py --output experiments/decision_screen/generated-results/maintenance.json
experiments/interop_d0/.venv/bin/python -m unittest discover -s experiments/decision_screen/tests -v
```

The first command runs five workflow cases and six prerequisite probes per arm.
The maintenance command verifies the stored, frozen repair candidates; it does
not call new model agents or repeat a controlled productivity trial. The static
probe receipt has a `passed` field; a typo accepted by Meda is an expected,
explicit limitation in those probes, not a successful rejection.

## What the Meda implementation adds

[language.py](language.py) extends the existing parser, checker and evaluator.
Source performs all application sequencing and domain validation. There are five
fixed host operations with monomorphic declared effects, private task-reference
membership, shape decoding and bounded result export. A pure operation cannot
call an effectful helper without declaring its effects; contracts and assertions
remain pure. The original pure profile still rejects external effects.

[worker.py](worker.py) decodes inputs and bridges calls over the same JSONL
protocol as the Node worker. The existing shared controller supervises both
processes, owns credentials, and decides final publication. It is not a Python
replacement for the Meda workflow.

This limited profile has no general module system, user-defined opacity, effect
polymorphism, concurrency, or integrated guarded semantic edits. Outcome/error
payloads currently use `Text`, so they have weaker typo checking than the
TypeScript client's finite unions. The fixed wire decoder still allowlists
received error codes. Local process supervision is not an OS security sandbox.

## Evidence

- [Prospective contract](../../docs/decision-screen-contract.md): shutdown rules,
  five-case requirements, frozen maintenance change, and decision criteria.
- [Baseline receipts](results/baseline.json): 22 independently passing executions,
  equal paired outcomes/calls/dispatches, and unchanged execution sources.
- [Checker probes](results/static-checks.json): four matched rejections and three
  explicitly reported differences.
- [Maintenance receipt](results/maintenance.json): both candidates pass 18 final
  cases and the changed end-to-end scenario.
- [Maintenance packets](maintenance): original sources, frozen fixtures, each
  submitted candidate and visible-check receipt. Shared filesystem access was
  restricted by instructions only; model version and token usage were unavailable.
- [Verification](results/verification.json): 141 passing test methods, distinct
  from workflow runs and maintenance acceptance cases.

Historical D0 receipts and its broader acceptance gaps remain unchanged.
