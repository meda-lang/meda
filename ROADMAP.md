# Meda experimental roadmap

The current candidate is [Draft 2.1](docs/design-draft-2.1.md). Implementation and
evaluation status is tracked in [gate-status.md](docs/gate-status.md).

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
