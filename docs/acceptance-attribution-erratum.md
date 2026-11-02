# Repeat-submit attribution correction

Revision `attribution-1` corrects one expectation in the frozen D0 acceptance
inventory. It changes `W12-client-repeat-submit.attribution` from
`["application", "independent_oracle"]` to `["shared_host"]`.

The original expectation confused the location of the injected defect with the
layer enforcing the denial. The TypeScript mutation attempts a second submit
after unknown delivery; the shared host rejects that attempt before dispatch.
The observed enforcement is unchanged. This correction improves the specification,
not the runtime, and is not new evidence of protocol or language capability.

## Exact scope and provenance

The [erratum](../experiments/interop_d0/acceptance-attribution-erratum.json) pins
the original inventory's SHA-256 and records the exact before/after values and
reason. Its loader accepts only this single case/field change. A changed base,
additional field, different case, or different attribution is rejected.
No scenario, phase, outcome, counter, invariant, witness, resource limit, or
other case changes. `acceptance.json` itself remains byte-for-byte unchanged.

The runner still produces ordinary original-inventory receipts. The screen
requires an explicit revision to reassess them. Its output records the selected
revision, base/effective inventory hashes, erratum hash, evaluator-source hashes,
and a canonical JSON hash of the input receipt. Original and selected assessment
statuses and failed checks appear together, evaluated from the same observations.

Under the original expectations, repeat-submit remains **failed**. Under
`attribution-1`, it is **unverified**, because missing evidence remains missing.
The other three mutation cases remain unverified. Neither Meda source arm is
executed, and `acceptanceClosed` remains false.

## CI behavior

The previous bounded screen permitted a named failed attribution check. That
exception has been removed. Every failed check in the selected revision now
rejects the screen; attribution must explicitly pass. Missing behavior evidence
also rejects it. CI chooses `attribution-1` explicitly and preserves the original
failed assessment in its summary.

```sh
# Reassess the preserved PR #19 observations; this makes no protocol calls.
experiments/interop_d0/.venv/bin/python -m experiments.interop_d0.mutation_screen \
  results/acceptance-mutations/frozen-run.json --revision attribution-1

# The original revision still rejects the attribution mismatch (exit code 1).
experiments/interop_d0/.venv/bin/python -m experiments.interop_d0.mutation_screen \
  results/acceptance-mutations/frozen-run.json --revision original
```

The [retained reassessments](../results/acceptance-attribution/README.md) are new
files. Historical execution receipts and prior screen outputs are untouched.
Resolving the specification error does not close #11's remaining accounting,
source-continuation, visibility, timing, or deferred-language obligations.
