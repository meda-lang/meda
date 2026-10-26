# Run the minimum effectful Meda versus TypeScript decision experiment

Determine whether Meda adds enough protection or maintenance benefit beyond
strict TypeScript using the same host/adapters to justify a language. Current
evidence supports prioritizing the library, while language value is unproven.

## Scope

1. Define the minimum supported effectful Meda semantics before implementation.
   Reuse the real parser/checker/evaluator. Do not substitute a Python workflow
   for Meda source. Record omitted semantics and implementation effort.
2. Execute both clients through the same adapters and independent expectations:
   success, required input, uncertain delivery, malformed response and a
   domain-invalid report. Resolve only defects that prevent a reliable screen.
3. Freeze one equivalent realistic maintenance change before either attempt.
   Supply equal context and editing facilities; retain all attempts, validation
   evidence and available model/usage metadata.
4. Publish a continue-Meda, library-first or stop decision, including protections
   attributed to their actual layer, implementation costs and uncertainty.

## Constraints

Keep the TypeScript control strong. Count substantial additional language
machinery as a cost. A small maintenance screen does not establish a broad
productivity advantage. The screen must not be reported as full D0 completion.
Avoid expanding the harness simply to increase coverage before the decision.

Dependencies: cancellation-refusal.md and shutdown-contract.md. Canonical
context: docs/research-handoff.md; detailed future study: docs/interop-evaluation.md.
