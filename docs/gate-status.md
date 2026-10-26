# Meda semantic gates status

Updated October 24, 2026. Baseline repository: `6d01d7a1ff77f2fd04d0b7175f0b24bcf14ee19e`.

Draft 2.1 is amended and a pure research implementation is executable. The
maintenance experiment is prepared, but its model comparison has not run.

| Work | Status and evidence |
| --- | --- |
| Focused design amendment | Contract dependency protection, owned timeout cleanup, label-based callable compatibility, narrower shadowing, package identity and test boundaries are specified. |
| Gate A executable profile | 55 source cases specify values or parse/check/runtime diagnostics and run from outside through the CLI. |
| Edit enforcement | Tests cover selective/transitive helper weakening, constant changes, new dependency edges, unrelated edits, explicit specification grants, stale revisions/receipts, altered checks, scope escape and repair after type errors. |
| Gate B interpreter and tools | Pure operations, nominal records/enums, lists, loops/match, contracts, profile formatter, context description and single-file guarded edits are implemented. |
| Maintenance harness | 12 paired Meda/Python tasks, 24 reference-repair smoke rows. Every broken start is rejected and every reference repair accepted. |
| Model trials | Not run. No model-driver executable or inference tool was available in the execution environment. The harness requires explicit configuration; it does not use a hidden provider. |
| Full gate decision | Open. The Python control needs comparable static checking; independent models, repeated trials, held-out tasks and outcome analysis are outstanding. |

The test command runs 23 test methods, including the parameterized 55-case CLI
corpus. The smoke runner also exercises all 12 Meda repairs through validation and
atomic publication. Stored [smoke results](../experiments/gates/benchmark/smoke-results.json)
are labeled `oracle_smoke`, `modelTrials: 0`, and `gateBDecision: not_evaluated`.
Smoke elapsed times are harness measurements and must not be interpreted as model
performance or language implementation benchmarks.

The prototype's implementation language is Python, chosen to execute the corpus
with the available runtime and no package installation. The production reference
design remains Rust. This does not change the target language semantics, but the
implemented profile is deliberately smaller; [PROFILE.md](../experiments/gates/PROFILE.md)
and the [deferred cases](../experiments/gates/corpus/deferred.json) define the boundary.

## Next acceptance gates

1. Add a conventional static checker to the Python control and document remaining
   differences in context, diagnostics, runtime limits, and edit capabilities.
2. Supply an explicitly identified model driver, freeze provider/version/sampling
   settings and budgets, and run the preregistered 12-task screen for at least two
   models with repeated fresh contexts. Track real tokens; unknown usage stays unknown.
3. Analyze paired task outcomes and all-attempt cost, retaining unsuccessful runs
   and uncertainty. A promising screen justifies a powered held-out experiment,
   not an edition or superiority claim.
4. Complete Gate C composition cases and package/opaque invariants before language
   freeze. Implement generation cancellation and wrapper-bound authority before
   admitting tools; implement replay arbitration before exposing replay guarantees.

No broad redesign is needed to execute these steps. Additions should respond to
failed acceptance cases or measured maintenance friction.
