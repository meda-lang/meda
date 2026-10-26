# Meda and TypeScript over the same host

This executable development experiment compares real Meda source evaluated by
the existing pure interpreter with TypeScript 5.9.3 compiled in strict mode.
Both decision clients use exactly the same guarded host and local HTTP peer.
It is a decision-boundary comparison, not the unfinished Meda effect runtime,
official MCP/A2A conformance, or a production security boundary.

## Run

Requirements: Python 3.11+, Node.js, TypeScript **5.9.3**. Either install the exact
dependency in this directory with `npm install --ignore-scripts` or set
`MEDA_COMPARE_TSC` to that version's `lib/tsc.js`. No dependency downloads or model
calls happen when the experiment runs. A missing/wrong compiler is an error, not
a skipped passing comparison.

From the repository root:

```sh
python3 -m unittest discover -s experiments/interop_compare/tests -v
python3 experiments/interop_compare/run.py --output /tmp/meda-comparison.json
python3 -m unittest discover -s experiments/gates/tests -v
```

The runner starts separate local peer processes, invokes each checked source
client in supervised subprocesses, asserts independent expected values and
dispatch counts, then compares decisions, observations and host traces. Both
arms receive fresh peer state. The numeric domain is explicitly bounded so
Python integers and TypeScript numbers agree on these counters. Timings are
not used to compare interpreter performance with compiled JavaScript.

The host wire fixture has protocol-shaped messages but custom method/data
contracts, including `tasks/continue`; it is deliberately **not** a conforming
MCP or A2A implementation. Identity headers model principal/tenant partitions
without authenticating a real user. There is no SSE, OAuth, dynamic discovery,
binding-drift enforcement, global job ledger, durable recovery or full replay.

## Evidence

- [EXPERIMENT.md](EXPERIMENT.md): questions and decision rules written before results.
- [cases.json](cases.json): independently specified workflow expectations.
- [results/baseline.json](results/baseline.json): final paired runs, checkers,
  direct host checks, isolated host mutants and client-policy mutants.
- [results/maintenance.json](results/maintenance.json): saved fresh-agent repairs
  checked against common acceptance cases; all failures and unknown controls explicit.
- [maintenance_packets](maintenance_packets): original tasks, broken sources,
  final candidates and visible-check records. These are archival packets, not
  a protected benchmark or independent held-out task collection.

Host ablations remove a grant check or call ceiling in a temporary source copy;
the tests must detect the resulting unsafe admission. A separate well-typed
client mutation resubmits after unknown delivery. The host permits that explicit
second submission, so the no-duplicate workflow policy belongs to application
code and tests, not the host's narrower no-automatic-retry rule.

## Maintenance demonstrations

To generate fresh equivalent task packets in a new location:

```sh
python3 experiments/interop_compare/maintenance.py prepare /tmp/new-meda-repairs
```

Preparation rejects an existing directory and verifies that each broken start
fails acceptance while its reference passes. Give a fresh repair agent only its
own packet; it may edit the candidate and run `check.py`. After all candidates
are final, evaluate them outside the agent:

```sh
python3 experiments/interop_compare/maintenance.py collect /tmp/new-meda-repairs \
  --output /tmp/new-meda-repair-results.json
```

The recorded six repairs were fresh-context, instruction-isolated demonstrations,
not filesystem-sandboxed trials. Exact model revision, sampling and tokens were
not exposed; equal hard time budgets were not enforced. Each candidate received
one visible-check invocation and no hidden feedback before finalization. Do not
interpret the resulting 3/3 per arm as a productivity estimate. The stored
`check.py` files record the original environment; generating new packets creates
relative paths for the current checkout.

## Development corrections and limits

`development-run-1.json` retains the initial 11/12 results per arm. The one paired
failure was a harness expectation that a continuation answer would be appended
to the final report. The fixture's declared report was unchanged. The corrected
case keeps that report and independently checks the peer received the exact
answer in `continuationInput`. No client was repaired to make this pass.

`development-run-2.json` retains the earlier 12/12 pass before independent review
expanded attribution. The final run adds explicit source-policy mutation probes,
full observation/trace comparison, and a hash of the entire TypeScript package
rather than only its loader. These are stronger checks, not extra independent
tasks.

Review also added three supplemental checks after repair candidates were final:
zero-budget read, zero-budget submit, and empty input at zero budget. The last
exposes ambiguous wording in the original pending-input task; it uses the
reference's existing budget precedence. Original packets and original sixteen
acceptance cases remain unchanged; supplemental outcomes are reported separately.

Binding/schema drift and final domain-acceptance enforcement in the proposed
protocol remain unmeasured. The experiment is a partial screen against that
protocol, not completion of every minimum family. Observation strings remain
open in both clients; the exhaustive-enum checker probe is separate from the
real client's future-state fallback.
