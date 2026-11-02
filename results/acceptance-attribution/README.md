# Attribution erratum verification

These are **reassessments of the preserved PR #19 observations**, not new
protocol executions. Runtime behavior and the underlying receipt did not change.
The [erratum design](../../docs/acceptance-attribution-erratum.md) explains the
single corrected expectation and the removal of the CI failure exception.

| Selected revision | Full-acceptance summaries | Bounded screen | CLI exit |
| --- | --- | --- | --- |
| Original | 3 unverified, 1 failed | Rejected | 1 |
| `attribution-1` | 4 unverified | Accepted | 0 |

Both outputs retain the original failed attribution check. Neither closes
acceptance or supplies missing evidence. All other behavior expectations and
the original inventory bytes remain unchanged.

- [Original reassessment](original.json)
- [Corrected reassessment](attribution-1.json)
- [Commands and input hash](reassessment.json)
- [54 focused regression tests](validation.json) and [test log](tests.log)
- [Unchanged input receipt](../acceptance-mutations/frozen-run.json)

The focused tests include adversarial revision, receipt, attribution, behavior,
and missing-witness checks, plus the existing independent oracle, inventory,
and dispatch regressions. CI also runs the existing live protocol workflows and
the four mutation cases, then explicitly selects the corrected revision.
