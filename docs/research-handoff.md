# Meda research handoff

Updated October 25, 2026. This repository preserves the design, executable work,
reviews, results and remaining questions from the research thread. Start here
when resuming; external ChatGPT Pages and downloadable patches are supplementary.

## Goal and current decision

Determine whether Meda provides enough protection or maintenance benefit beyond
a conventional strict TypeScript client using the same runtime and adapters to
justify a new language. Be willing to pursue the library instead.

Current recommendation: prioritize the reusable host/adapters and retain a
first-class TypeScript client. Meda's incremental value is unproven. The pure
comparison tied; the effectful real-protocol comparison has not been executed.

The thread spent substantial effort on protocol infrastructure. The next
deliverable should be a bounded comparison and a product decision. Fix defects
that prevent that comparison, retain broader gaps explicitly, and avoid expanding
the harness merely to increase test counts. This execution-priority correction
does not change the criteria or results of earlier frozen experiments.

## Where the work lives

| Work | Canonical repository location | Observed status |
| --- | --- | --- |
| Language proposal | [Design Draft 2.1](design-draft-2.1.md) | Proposed design, broader than the implemented language |
| Gate A and Gate B | [Status](gate-status.md), [implementation](../experiments/gates/README.md) | 55-case pure corpus; maintenance harness and reference smoke, controlled model study outstanding |
| Pure Meda versus TypeScript | [Results](runtime-comparison.md), [reproduction](../experiments/interop_compare/README.md) | Both 12/12 workflows and four matched static rejections; three uncontrolled repairs per arm |
| Protocol architecture and panel conclusions | [Amendment](interop-design-amendment.md) | Shared host, protocol adapters, explicit attribution, scoped authority |
| Bounded real protocol contract | [Workflow](interop-workflow.md) | MCP 2026-07-28 and A2A 1.0.0 profile |
| Real SDK reference implementation | [Results](interop-reference-results.md), [reproduction](../experiments/interop_d0/README.md) | Host, adapters, SDK peers and TypeScript implemented; effectful Meda absent |
| Experimental evidence | [Reference receipts](../experiments/interop_d0/results/reference-pilot.json), [diagnostic reruns](../experiments/interop_d0/results/diagnostic-reruns.json), [verification](../experiments/interop_d0/results/verification.json) | Original failures, incomplete checks and reruns retained separately |
| Detailed future evaluation | [Evaluation](interop-evaluation.md), [roadmap](interop-roadmap.md) | Longer study remains dependent work |

## Review conclusions to preserve

- Compare both languages through identical adapters. Credit grants, quotas,
  authentication and response limits to the layer that enforces them.
- Agent-to-agent communication and MCP belong behind pinned adapter bindings.
  New protocols need explicit capability, version, authority and lifecycle tests;
  compatibility is not automatic.
- Unknown delivery is not permission to resend. Local retirement does not prove
  remote cancellation or rollback.
- Opaque application wrappers may serialize into inert data; serialization must
  not recreate authority. Trusted internal RPC tokens have a different scope.
- Keep conventional tooling strong: strict checking, private references, domain
  validators and comparable editing facilities.
- A useful host library does not itself demonstrate language value. Small repair
  demonstrations do not establish model productivity or statistical advantage.

These are synthesized review conclusions. The documents and test receipts retain
their substantive findings; this is not a verbatim archive of the chat or panels.

## Evidence and limitations

The latest isolated verification passed 85 new test methods plus 23 Gate A/B and
15 prior-comparison regression methods. The independent 111-case pilot produced
93 receipts, three execution errors and 15 unrun rows. It reported zero complete
acceptance passes, two failed cases and 91 cases with incomplete evidence.

A separate five-case diagnostic run reproduced the extra cleanup cancellation
after explicit refusal. The other four produced expected outcomes but remained
incompletely verified. The original failures are retained. The first run's
whole-tree freeze check is false because one RSS unit test changed; its runtime,
client, adapter, oracle and fixture sources were unchanged. The diagnostic run's
snapshot was unchanged. See the result report for the exact scope.

Outstanding guarantees include full source-continuation ordering, complete
discovery accounting and per-case cleanup timing. RSS is sampled supervision,
not a hardened OS sandbox. Network cancellation evidence covers numeric loopback
endpoints. Credentials are local test credentials, not production OAuth.

## Bounded next deliverable

1. Resolve explicit cancellation-refusal cleanup policy without inventing a
   terminal remote state. Preserve the failed receipt and add a separate repair
   receipt. Investigate intermittent execution errors only as needed for reliable
   comparison runs.
2. State the minimum effectful Meda semantics before implementing them. Reuse the
   real parser/checker/evaluator and common host; do not substitute a hand-written
   Python workflow for Meda source. Record any omitted semantics as limitations.
3. Run the same evidence-to-task workflow in both arms, including required input,
   uncertain delivery, a malformed response and a domain-invalid report. Define
   independent success criteria before execution.
4. Freeze one realistic equivalent maintenance change before either attempt.
   Provide equal context and editing facilities; preserve all attempts and report
   actual available model/usage metadata. A small screen can inform the next
   investment but cannot establish a broad productivity advantage.
5. Publish a continue-Meda, library-first or stop decision, including implementation
   effort, rejected defects by layer, maintenance results and uncertainty. If the
   minimal Meda arm requires substantial new machinery, count that cost explicitly.

The detailed roadmap remains useful as a backlog. Broad D0 acceptance remains
open; a smaller screen must be labeled as such rather than reported as closing
those gates. No further language expansion is justified solely by shared-library
protections or a small tie.

## Original local implementation history

| Original commit | Work |
| --- | --- |
| `1053416ff04d100072fd0cd32458111726bae60d` | Draft amendment and executable semantic gates |
| `0d8b94e2913832070d4850a2a0aa23b4c6c08b25` | Shared-runtime pure Meda/TypeScript comparison |
| `6e958e6faff669c7068509647582ad503ddad244` | Bounded real-protocol design and evaluation plan |
| `011011db17dc60c454cb9d76a164da0d068852ab` | SDK reference pilot and retained acceptance gaps |

GitHub publication through its API may assign different commit IDs. The published
stage trees must match the corresponding local Git trees byte for byte; the
publication PR records the mapping. Research is preserved on a branch pending
review rather than silently changing the default branch.
