# Controlled mutations of the host and application

This follow-up to [#11](https://github.com/meda-lang/meda/issues/11) executes the
four mutation cases that were missing from the original D0 pilot. It tests
whether independent observations detect broken enforcement and whether the
canonical host contains a faulty application. It does not expand the public API
or resume language development.

Every case runs an unchanged control and a narrowly modified version against
the same pinned SDK peers over local TLS. Raw control and mutant receipts stay
separate. The independent oracle reads their observations; the injected defect
cannot declare itself detected.

| Frozen case | Deliberate change | Evidence required |
| --- | --- | --- |
| `W12-mutant-remove-grant` | Remove the operation-grant check | The control denies submission; the peer creates a task under the mutant despite the same denied grant |
| `W12-mutant-remove-quota` | Remove the request quota check | The control dispatches nothing; the peer reads evidence under the mutant with zero normal request allowance |
| `W12-client-repeat-submit` | Repeat submission after losing its response | The first attempt creates one task; the canonical host denies the second attempt before dispatch |
| `W12-wrong-domain-validator` | Accept an incorrect report | The control rejects the report; the mutant publishes it and the independent domain checker rejects its contents |

Host mutations affect isolated fixture instances, with no runtime bypass flag
and no global replacement of production methods. Source mutations compile real
TypeScript with the existing binding and strict compiler configuration. The
Meda source arms remain unexecuted. Recorded source hashes identify the changes;
the ordinary source tree remains unchanged during execution.

## Keep behavioral results and full acceptance separate

The frozen repeat-submit case lists `application` and `independent_oracle` as
its allowed attribution layers. The actual admission denial belongs to
`shared_host`. The oracle retains that real attribution and reports the frozen
`attribution_recorded` requirement as **failed**. The inventory is unchanged.
Correct duplicate containment does not erase this specification mismatch.

The bounded mutation screen demands the intended outcomes, exact dispatch/task/
publication counts, the relevant independently checked invariant, and no other
failed frozen checks. It explicitly reports the known attribution mismatch.
This is a regression check for the four behaviors, not an acceptance waiver:
its output retains the ordinary full-acceptance statuses and always records
`acceptanceClosed: false`.

Independent observations for complete discovery accounting, source continuation,
secret visibility, and cleanup timing remain incomplete. The nine language
source checks remain deferred. Issue #11 stays open, and no new complete
111-case acceptance run or general MCP/A2A conformance claim is made.

## Reproduce

After the dependency setup in the [experiment README](../experiments/interop_d0/README.md),
run from the repository root with a new result path:

```sh
experiments/interop_d0/.venv/bin/python -m experiments.interop_d0.acceptance_run \
  --surface host_mutant --surface source_mutant \
  --output results/acceptance-mutations/my-run.json
experiments/interop_d0/.venv/bin/python -m experiments.interop_d0.mutation_screen \
  results/acceptance-mutations/my-run.json
```

Retained results and regression evidence are in the
[verification record](../results/acceptance-mutations/README.md).
