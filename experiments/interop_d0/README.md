# Bounded SDK interoperability experiment

The [direct-call decision screen](../decision_screen/README.md) now reuses this
host for both Meda and TypeScript and records the cancellation-refusal repair.
The original D0 pilot and its broader acceptance gaps are preserved below.

Start with the [wiring walkthrough and runnable example](../../docs/wiring-walkthrough.md)
to follow an application call through the bindings, shared host and SDK peers.

This directory implements the conventional TypeScript reference workflow and
common host for `meda-interop-d0/1`. MCP and A2A run through separate official
SDK server processes over verified local TLS. The independent fault proxy can
alter or lose actual SDK responses. The acceptance oracle does not import the
host, adapters, client, or their validators.

This is a development candidate, not a completed gate or a protocol conformance
suite. The narrow Meda arm and one uncontrolled maintenance demonstration live in
`../decision_screen/`; the controlled maintenance study is still unimplemented. See [the workflow contract](../../docs/interop-workflow.md),
[roadmap](../../docs/interop-roadmap.md), and
[execution report](../../docs/interop-reference-results.md).

## Reproduce

Run from the repository root on Linux x86_64, CPython 3.12, Node 24 and OpenSSL 3.
The hash lock targets the recorded Linux wheels and requires glibc 2.34 or newer.

```sh
python3 -m venv experiments/interop_d0/.venv
experiments/interop_d0/.venv/bin/python -m pip install --require-hashes --only-binary=:all: -r experiments/interop_d0/requirements.lock
npm ci --ignore-scripts --prefix experiments/interop_d0
experiments/interop_d0/.venv/bin/python -m experiments.interop_d0.freeze
experiments/interop_d0/.venv/bin/python -m unittest discover -s experiments/interop_d0/tests -v
experiments/interop_d0/.venv/bin/python -m experiments.interop_d0.acceptance_run --output experiments/interop_d0/generated-results/acceptance.json
```

The runner compiles the actual strict TypeScript source, then launches a fresh
Node process for each workflow. TypeScript checks application source and imported
types with `strict` and `noEmitOnError`; `skipLibCheck` skips internal checking of
the pinned dependencies' declaration files. A compiler budget of 10 seconds and
256 MiB observed RSS is supervised. Node heap limits are additional GC controls,
not a substitute for RSS measurement. Memory sampling and process retirement do
not constitute a hardened OS sandbox for adversarial JavaScript.

`--case ID` and `--surface workflow` select a development subset. The receipt
records that selection, immutable inventory and source hashes, actual outcomes,
safe host/peer/proxy observations, and independent assessment. `passed` requires
every case obligation; `unverified` means execution lacks evidence for one or
more obligations; `failed` means at least one observed check contradicts the
contract. `not_run` and `execution_error` never receive passing credit.

The nine unimplemented Meda source checks and the controlled mutant/maintenance
work remain explicit in the inventory. Unit methods, protocol stimuli, workflow
rows, and independently satisfied acceptance cases are different counts.

## Boundaries

The trusted Python controller owns credentials, grants, quotas, references and
TLS sockets. Application code calls five typed operations through a binding
whose task wrappers have private membership. The wire reference token stays
inside the trusted bridge. Local fake bearer credentials are checked by the
SDK peer boundary for principal, tenant, audience, operation and expiry; this is
not a production OAuth deployment.

The host validates the bounded supported envelope and data profile. It does not
claim to validate arbitrary extensions or every message in either protocol.
Deadline and cancellation evidence covers numeric loopback endpoints; blocking
external DNS resolution has not been established within the same bound.
Owned socket cancellation, worker retirement, and later remote cancellation
have separate observations. Remote uncertainty does not become rollback or
permission to resend. The full no-source-continuation-after-close property is
not established by observing no late dispatch or publication.

`candidate-manifest.json` pins resource limits, descriptors, Agent Card template,
dependency locks and the independent case inventory. Each actual run records its
allocated endpoints and corresponding binding hashes. No real service account,
paid model, or external side effect is involved.
