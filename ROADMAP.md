# Meda experimental roadmap

The current candidate is [Draft 2.1](docs/design-draft-2.1.md). The next decision
is whether a language adds enough value beyond strict TypeScript using the same
runtime and adapters. The [research handoff](docs/research-handoff.md) records the
current recommendation and evidence; detailed language gate status remains in
[gate-status.md](docs/gate-status.md).

## Next milestone: decide whether to continue the language

1. Fix the [cancellation-refusal cleanup defect](https://github.com/meda-lang/meda/issues/8)
   and define the [shutdown guarantees](https://github.com/meda-lang/meda/issues/9)
   needed for a reliable comparison.
2. Run the [minimum effectful Meda versus TypeScript experiment](https://github.com/meda-lang/meda/issues/10)
   through the same host and adapters, including one equivalent maintenance change.
3. Publish a continue-Meda, library-first, or stop decision, counting both benefits
   and the cost of the additional language implementation.

Broader [reference acceptance gaps](https://github.com/meda-lang/meda/issues/11)
remain tracked. This smaller experiment will not close those gates or establish
a general productivity advantage by itself.

## Broader language research backlog

These earlier gates remain recorded; they are not prerequisites to finish in
full before the next product decision.

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
