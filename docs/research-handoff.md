# Meda research handoff

Updated October 27, 2026. This repository preserves the design, executable work,
reviews, results and remaining questions from the research thread. Start here
when resuming; external ChatGPT Pages and downloadable patches are supplementary.

## Goal and current decision

Determine whether Meda provides enough protection or maintenance benefit beyond
a conventional strict TypeScript client using the same runtime and adapters to
justify a new language. Be willing to pursue the library instead.

Current recommendation: **library-first; pause further language expansion.**
The [direct-call screen](decision-screen-results.md) now executes real Meda and
TypeScript applications through the same SDK host. Both pass five required
workflows, six prerequisite probes, and one frozen maintenance change. Meda's
incremental value remains insufficiently demonstrated. Preserve the working
language example and focus the next investment on the reusable host and
conventional client. The broader production and acceptance backlog remains open.

## Where the work lives

| Work | Canonical repository location | Observed status |
| --- | --- | --- |
| Language proposal | [Design Draft 2.1](design-draft-2.1.md) | Proposed design, broader than the implemented language |
| Gate A and Gate B | [Status](gate-status.md), [implementation](../experiments/gates/README.md) | 55-case pure corpus; maintenance harness and reference smoke, controlled model study outstanding |
| Pure Meda versus TypeScript | [Results](runtime-comparison.md), [reproduction](../experiments/interop_compare/README.md) | Both 12/12 workflows and four matched static rejections; three uncontrolled repairs per arm |
| Protocol architecture and panel conclusions | [Amendment](interop-design-amendment.md) | Shared host, protocol adapters, explicit attribution, scoped authority |
| Bounded real protocol contract | [Workflow](interop-workflow.md) | MCP 2026-07-28 and A2A 1.0.0 profile |
| Real SDK reference implementation | [Results](interop-reference-results.md), [reproduction](../experiments/interop_d0/README.md) | Original host/TypeScript pilot; direct Meda extension is recorded separately below |
| Direct Meda decision screen | [Decision](decision-screen-results.md), [implementation](../experiments/decision_screen/README.md) | 22 independently passing runs; both maintenance candidates pass 18 cases; library-first recommendation |
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

The October 25 isolated verification passed 85 new test methods plus 23 Gate A/B and
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

## Completed bounded deliverable and next priority

The cancellation-refusal repair, prospective shutdown contract, direct-call Meda
profile, paired workflow screen, and frozen maintenance demonstration are now
implemented and recorded in [the decision report](decision-screen-results.md).
The current verification passes 141 test methods. The original pilot's failed
and unverified rows remain untouched; the smaller screen does not close full D0.

Next, make the existing shared host/client usable independently of the language
experiment and retain [issue #11](https://github.com/meda-lang/meda/issues/11) for
broader acceptance work. Reopen language investment only around a specific
claimed benefit and an equally equipped conventional control. One small
maintenance tie cannot establish general productivity equivalence.

## Original local implementation history

| Original commit | Work |
| --- | --- |
| `1053416ff04d100072fd0cd32458111726bae60d` | Draft amendment and executable semantic gates |
| `0d8b94e2913832070d4850a2a0aa23b4c6c08b25` | Shared-runtime pure Meda/TypeScript comparison |
| `6e958e6faff669c7068509647582ad503ddad244` | Bounded real-protocol design and evaluation plan |
| `011011db17dc60c454cb9d76a164da0d068852ab` | SDK reference pilot and retained acceptance gaps |

GitHub publication through its API may assign different commit IDs. The published
stage trees must match the corresponding local Git trees byte for byte; the
[publication record](research-publication.md) records the verified mapping.
The research archive was merged in [PR #12](https://github.com/meda-lang/meda/pull/12).
The [wiring walkthrough](wiring-walkthrough.md) was added in
[PR #13](https://github.com/meda-lang/meda/pull/13).
