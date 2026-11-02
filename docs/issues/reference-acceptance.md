# Retain and resolve broader real-protocol reference acceptance gaps

The 111-case pilot produced 93 receipts, three execution errors and 15 unrun
rows. The independent oracle reports two failed and 91 incompletely verified
cases, with zero full acceptance passes. Unit verification passes 85 new tests
plus 38 existing regressions; those counts do not override the acceptance result.

## Backlog

- The explicit-cancellation, duplicate-fact-ID, foreign-peer, cancellation-refusal,
  and wrong-RPC-ID cases now execute with their expected semantic results in five
  focused rounds. Safe stage attribution is implemented for future execution
  errors. Preserve the original rows and the focused follow-up separately; the
  replay does not turn historically failed or incomplete receipts into passes.
- Complete independently observed discovery accounting and cleanup timing where
  required. Keep source-continuation and authority-exposure scope explicit.
- The two missing workflow fixtures execute with the expected outcomes in
  PR #18. Their full acceptance remains unverified; see
  `docs/acceptance-workflow-fixtures.md`.
- Four controlled host/TypeScript mutation cases now have executable fixtures;
  see `docs/acceptance-mutations.md`. Keep their full acceptance statuses
  separate from behavioral mutation detection. The frozen repeat-submit case
  has an attribution mismatch: the host enforces the denial, but the inventory
  lists application/independent-oracle attribution. Preserve that failure.
- Nine Meda source checks remain deferred with language expansion. The two
  Meda source-mutation arms also remain unexecuted.
- Repeat a complete immutable acceptance run when closing the full gate. The
  original whole-tree check is false because one RSS unit test changed; runtime
  sources did not change. Preserve that record.

Do not turn missing witnesses into passes, widen frozen expectations to hide
defects or claim general MCP/A2A conformance. Preserve numeric-loopback, sampled
RSS, body-byte accounting and local test-authentication limitations.

Priority: retain this broader backlog without indefinitely blocking the smaller
decision experiment. Evidence: docs/interop-reference-results.md and
experiments/interop_d0/results/.
