# Meda semantic gates status

October 27 update: the separate [bounded direct-call decision screen](decision-screen-results.md)
now runs both languages and recommends library-first. It does not close the
broader gates below; their October 25 historical criteria and results remain.

Updated October 25, 2026. Gate A/B baseline repository: `6d01d7a1ff77f2fd04d0b7175f0b24bcf14ee19e`.

Draft 2.1 and its interoperability amendment specify the next bounded experiment.
The pure research implementation and shared-runtime comparison are executable.
The real-protocol D0 TypeScript reference now runs against official SDK peers;
its full acceptance remains open. The full Gate B controlled model study and
effectful Meda protocol arm have not run.

| Work | Status and evidence |
| --- | --- |
| Focused design amendment | Contract dependency protection, owned timeout cleanup, label-based callable compatibility, narrower shadowing, package identity and test boundaries are specified. |
| Gate A executable profile | 55 source cases specify values or parse/check/runtime diagnostics and run from outside through the CLI. |
| Edit enforcement | Tests cover selective/transitive helper weakening, constant changes, new dependency edges, unrelated edits, explicit specification grants, stale revisions/receipts, altered checks, scope escape and repair after type errors. |
| Gate B interpreter and tools | Pure operations, nominal records/enums, lists, loops/match, contracts, profile formatter, context description and single-file guarded edits are implemented. |
| Maintenance harness | 12 paired Meda/Python tasks, 24 reference-repair smoke rows. Every broken start is rejected and every reference repair accepted. |
| Full Gate B model trials | Not run. The harness requires an explicitly configured model driver. The separate shared-runtime study completed six uncontrolled fresh-context repair demonstrations; these do not satisfy the named-model controlled-study requirements. |
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

1. Resolve the [reference candidate's remaining acceptance and scope](interop-reference-results.md)
   under D0-01/02/03 in the [roadmap](interop-roadmap.md). Exact dependencies,
   protocol artifacts and a 111-case inventory now exist.
2. Close acceptance for the shared real-protocol host/adapters and strict
   TypeScript reference, then implement the minimum checked effectful Meda
   profile. Preserve direct host probes and independent expected outcomes;
   passing integration does not establish language value.
3. Admit the [maintenance pilot and held-out screen](interop-evaluation.md) only
   after matching edit facilities, protected workers, a named model driver and
   enforced budgets exist. Preserve failed attempts and all-attempt costs.
4. Retain the broader Gate B/C/D/E/F obligations. The pure Python control still
   lacks comparable static checking and cannot independently support a language
   advantage claim. D0's TypeScript control does not retroactively fix that study.

The [design amendment](interop-design-amendment.md) permits this bounded C/D0
sequence before broad model-runtime investment. It leaves general composition,
generation, concurrency, replay and edition readiness outside the new milestone.

## Shared runtime comparison on October 25

An isolated [Meda and TypeScript comparison](runtime-comparison.md) now executes
the real pure Meda client and a strict TypeScript client over identical shared
host/adapters. Both pass 12 workflow cases and reject the same four static defects.
Direct host tests and client-policy mutants distinguish library enforcement from
application sequencing. Three fresh-context repairs per arm pass, but these are
uncontrolled repair demonstrations, not the full Gate B model comparison.

The result supports prioritizing reusable host/adapters with a first-class
TypeScript client. It leaves Meda's incremental language value unproven. The
custom loopback wire fixtures do not establish MCP/A2A conformance or complete
Gate D0. The separate real-SDK reference candidate now supplies actual peers
and binding-drift probes; its acceptance and the effectful Meda runtime remain
open. Existing Gate A/B implementation and pass counts are unchanged.

## Interoperability profile and reference candidate

`meda-interop-d0/1` now has a workflow specification, twelve acceptance families,
a paired evaluation plan and seven dependency-ordered work packets. Its
111-case inventory preserves planned status separately from observed pilot
receipts. Protocol pins are MCP 2026-07-28 Streamable HTTP and A2A 1.0.0 JSON-RPC;
SDK, schema and build pins are recorded in the executable candidate. The profile
requires real checked direct host calls,
one-package modules/visibility, opaque references, monomorphic effect checking
and bounded root cleanup. The current pure interpreter implements none of those
new mechanisms yet. The [real-protocol reference results](interop-reference-results.md)
record implementation, adversarial repairs, evidence and remaining acceptance
gaps. No existing gate is marked complete by this work.
