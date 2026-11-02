# Workflow fixture verification

The two originally unrun workflow rows now execute through the real SDK peers,
research TypeScript application, and canonical host. The implementation and
scope are described in [the follow-up](../../docs/acceptance-workflow-fixtures.md).

- [Regression summary](validation.json): 189 tests passed across six suites.
- [Replay summary](replay-summary.json): three isolated rounds, two exact frozen
  scenarios per round, six executions, no failed frozen checks.
- Raw receipts: [trial 1](trial-1.json), [trial 2](trial-2.json), [trial 3](trial-3.json).
- Regression logs: [language](gates.log), [protocol/host](interop.log),
  [earlier comparison](comparison.log), [decision screen](decision-screen.log),
  [runtime package](runtime.log), [TypeScript package](typescript-package.log).

Every trial records an unchanged source snapshot, and the snapshots are identical
across trials. Both scenarios use the original default resource limits. Receipts
are written outside the frozen source directory so writing a result does not
invalidate its source check. `acceptance.json`, `oracle.py`, the canonical runtime
and all historical result files are unchanged.

All six assessments remain **unverified**, with zero full acceptance passes.
Expected `Timeout`/`CleanupFailure` outcomes and zero failed checks do not satisfy
missing independent witnesses. This is a focused fixture replay, not a complete
111-case acceptance run or protocol conformance result.

Reproduce each trial from the repository root after the dependency setup in
[the experiment README](../../experiments/interop_d0/README.md):

```sh
experiments/interop_d0/.venv/bin/python -m experiments.interop_d0.acceptance_run \
  --case W02-wait-deadline --case W04-cleanup-cannot-join \
  --output results/acceptance-workflow-fixtures/my-new-trial.json
```

Use a new output path; retain the committed receipts. The CI workflow checks
execution status, both exact terminal outcomes, unchanged sources, and the
absence of failed frozen checks. It does not treat `unverified` as `passed`.
