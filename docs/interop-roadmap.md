# Bounded interoperability roadmap

Updated October 25, 2026. Status: specification and implementation backlog;
the real-protocol workflow and effectful Meda profile are not implemented.

The next milestone tests one evidence-read and delegated-task workflow through
the same host and adapters in strict TypeScript and Meda. The
[design amendment](interop-design-amendment.md), [workflow contract](interop-workflow.md)
and [evaluation plan](interop-evaluation.md) govern these work packets. The
[earlier comparison](runtime-comparison.md) remains a completed, narrower result.

## Work packets and dependencies

| Packet | Deliverable | Depends on | Acceptance before closing |
| --- | --- | --- | --- |
| D0-01 Freeze protocol and test artifacts | Exact protocol/schema and SDK or implementation revisions, host manifest, resource profile, independent reference-peer plan, complete case inventory | This specification | No floating dependency or undocumented fallback; every supported operation has request/result/error and authority rules; expected outcomes are specified independently of either client. |
| D0-02 Shared host and real adapters | MCP evidence read, A2A task interaction, resource ledger, authentication boundary, response and schema validation | D0-01 | Direct boundary tests pass without either language checker; independent peer observations verify actual requests, ownership, side effects and cleanup; malformed responses cannot become validated protocol values. |
| D0-03 TypeScript reference workflow | Strict typed source calling the shared host, pure domain validator, validated values and private handles, scoped lifetime and explicit error branches | D0-02 | All required workflow cases pass from the public executable entry; domain-wrong artifacts never become successful reports; complete results and traces retained; no application-specific exception in host admission. |
| D0-04 Minimal effectful Meda profile | Checked direct host calls, finite effect bounds, one local package with module visibility and opaque values, root-bound host reference | D0-01; adapter execution needs D0-02 | Source checks and interpreter execute the declared semantics; invalid transitive effects and opaque construction fail before dispatch; old pure corpus still passes. Stop if this requires the excluded general language features. |
| D0-05 Paired attribution comparison | Both clients run identical independently checked scenarios plus isolated host, adapter and source mutants | D0-03 and D0-04 | Independent success first, then normalized semantic trace comparison; every mismatch explained; shared protections credited to the shared layer; no full-protocol certification claim. |
| D0-06 Maintenance admission and development pilot | Equal context and editing facilities, protected acceptance, isolated fresh workers, named model driver and measured usage | D0-05 | Both arms can perform the same permitted multi-file changes through staged validation and atomic publication; pilot repairs and controlled failures exercise the driver. Unsupported tasks do not enter scoring. |
| D0-07 Held-out screening and decision | Frozen task set, repeated paired trials, all-attempt measurements and task-level uncertainty | D0-06 | Execute the evaluation plan without hidden-test feedback or silent exclusions; publish a continue, library-first, or inconclusive decision with remaining uncertainty. |

D0-02 and D0-03 establish the conventional baseline before spending on full Meda
execution. D0-04 may prepare parser/checker work in parallel after D0-01, but
protocol behavior must remain in the common adapters. D0-06's staged workspace
tooling is an experimental driver capability, not completion of the language's
general Gate F editing/recovery design.

## Scope and stopping rules

Each implementation packet has one initial implementation and at most two repair
cycles against its frozen acceptance contract. A repair cycle ends with a full
packet acceptance run and recorded remaining failures. Hitting that limit leaves
the packet open and triggers a written scope/feasibility decision; it does not
turn missing checks into passes. This is a work-control rule, not a productivity
measurement. Record actual effort separately.

The milestone includes one MCP evidence operation, one A2A skill, two client
languages and the necessary local host boundary. A general scheduler, model
generation, effect polymorphism, arbitrary FFI, durable task recovery, full
replay, a package registry and support for additional protocols are outside it.
Any prerequisite that crosses this boundary must be documented before expanding
the milestone. The stronger maintenance screen remains blocked until its driver,
model configuration, resource budget and hidden-test isolation are real.

A safety or acceptance defect blocks the next dependent packet. Protocol
integration passing is evidence for the library; it does not close the language
maintenance question. If conventional tooling already supplies all proposed
incremental protections, retain the library and require a new testable language
hypothesis before expanding Meda. A small or uncertain maintenance result remains
inconclusive, as specified in the evaluation plan.

## Relationship to the existing gates

Gate A's 55-case pure corpus and Gate B's existing harness remain unchanged.
The new `meda-interop-d0/1` profile is a bounded exploratory branch through
selected composition and host-integration mechanisms. D0-05 does not close Gates
B, C, D or E. General composition, live model usefulness, concurrency and edition
readiness retain their original unmet acceptance obligations.

The immediate implementation task is D0-01: freeze the executable protocol,
dependency and acceptance artifacts. Model trials start only after their
admission controls and resource budget are fixed.
