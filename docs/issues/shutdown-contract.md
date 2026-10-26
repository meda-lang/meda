# Define testable root shutdown guarantees before the paired screen

The current profile's complete no-source-continuation-after-close invariant is
unverified. Revoking host admission, retiring local work and observing remote
cancellation are distinct promises. A controller's response ordering and process
retirement do not prove that no runnable source instruction executes after close.

## Proposed prospective clarification

- Closing a root immediately revokes new host-effect admission and successful
  publication for both language arms.
- The supervisor retires owned local work within a measured bound; residual pure
  computation during asynchronous termination is not new authority.
- Remote cancellation is reported separately and may remain unknown.

## Acceptance

Document an explicit decision before the next implementation packet, including
the required observations for each promise and equal treatment of both arms.
Retain the historical criteria and unverified results. If zero source steps after
close remains essential, identify an execution model that can establish it.

Reference: docs/interop-reference-results.md and docs/interop-workflow.md.
