# Suppress automatic cleanup cancellation after a validated explicit refusal

The SDK pilot's W04-explicit-cancel-terminal-refusal returns TaskNotCancelable
and then dispatches another cancellation during root cleanup. The frozen case
permits zero cleanup cancellations. Diagnostic reruns reproduce the mismatch.

Evidence: experiments/interop_d0/results/reference-pilot.json and
experiments/interop_d0/results/diagnostic-reruns.json. Implementation: host.py.

## Proposed policy

Record a validated explicit refusal separately from task state. Suppress automatic
cleanup cancellation until another validated nonterminal observation changes the
situation. Refusal is not proof that the remote task completed. Never manufacture
Completed or consult the fixture's private ledger.

## Acceptance

- Preserve the original failed receipts and unchanged expected dispatch count.
- Add a separate repair receipt proving no cleanup request was sent after refusal.
- Record skipped cleanup with prior-refusal provenance.
- A lost cancellation response still permits authorized bounded cleanup.
- A subsequent validated nonterminal observation restores cleanup eligibility.

This is a bounded host-policy repair, not evidence for language-specific value.
