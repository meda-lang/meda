# Meda experimental roadmap

The [bounded comparison](docs/decision-screen-results.md) is complete. Both
real applications pass the same protocol workflow and maintenance screen.
The recommendation is **library-first**, with further language expansion paused.
[Draft 2.1](docs/design-draft-2.1.md) remains a proposal rather than a release plan.

## Completed decision milestone

- [x] Repair cancellation-refusal cleanup and retain a separate repair receipt.
- [x] Define and measure the narrower shutdown contract for both applications.
- [x] Run real direct-call Meda and TypeScript through the same host and adapters.
- [x] Freeze and execute one equivalent maintenance change, preserving all attempts.
- [x] Publish a decision that counts shared protections and additional language cost.

## Recommended next investment

Make the shared host and TypeScript client easier to consume independently of
the experiment. Address the [broader reference acceptance gaps](https://github.com/meda-lang/meda/issues/11)
before claiming production readiness. Keep the runnable Meda prototype and its
receipts available for future, specific language hypotheses.

## Broader language research backlog

These earlier gates remain recorded as deferred language research. The small
decision screen does not complete them.

- [x] Amend the second review's contract protection and timeout ownership gaps.
- [x] Define callable label compatibility and narrow lexical shadowing.
- [x] Implement an executable pure corpus, structured diagnostics and edit schemas.
- [x] Exercise guarded body changes, protected helper dependencies and acceptance checks.
- [x] Prepare 12 paired maintenance tasks and verify their failure/repair oracles.
- [ ] Finish Gate A coverage outside the declared pure profile.
- [ ] Equip the Python control with comparable static checking.
- [ ] Run independent repeated model trials and decide Gate B from measured evidence.
- [ ] Gate C: callable/opaque/validator variants and package identity conformance.
- [ ] Gate D: one typed model component, fake effects and an exported-client lifecycle.
- [ ] Gate E: owned cancellation, scoped tools, bounded maps and resource accounting.
- [ ] Gate F: deterministic replay and broader recoverable editing.
- [ ] Gate G: maintained applications, two adapters and supported-edition policy.

The legacy JavaScript scanner and Rust argument-parsing starter remain available
for history. The pure research profile is isolated in `experiments/gates/`.
