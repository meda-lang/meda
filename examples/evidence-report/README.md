# Evidence-to-report application

This is an ordinary TypeScript application using the local `@meda/evidence-client` package and Python `meda-runtime` host. It reads evidence through MCP, asks an A2A agent for a selected-facts report, and checks that report against the evidence. The local demonstration uses deterministic SDK peers and makes no model calls.

[main.ts](main.ts) is the entire worker entry point:

```ts
import {runWorker} from "@meda/evidence-client";
import {decodeInput, runWorkflow} from "./workflow";

void runWorker(decodeInput, runWorkflow);
```

[workflow.ts](workflow.ts) owns the task-state decisions and application input. [domain.ts](domain.ts) owns report validation: the document/revision and fact values must agree with the evidence, and selected IDs must match the request. A peer may reorder the same selected facts; validation returns them in request order. This business rule is not supplied by the runtime.

## Try all seven local cases

From the repository root, on Linux x86_64 with Python 3.12, Node 24/npm, and OpenSSL:

```sh
python3.12 -m venv experiments/interop_d0/.venv
experiments/interop_d0/.venv/bin/python -m pip install --require-hashes --only-binary=:all: -r experiments/interop_d0/requirements.lock
npm ci --ignore-scripts --prefix packages/evidence-client
experiments/interop_d0/.venv/bin/python tools/runtime-demo/verify.py --output results/runtime-library/generated/local.json
```

Use a fresh output filename. The driver builds a wheel and tarball, installs a fresh consumer outside this repository, and runs success, required input, unknown delivery, malformed response, invalid report, reordered report, and cancellation refusal. Package installation may access dependency registries; the workflow exchanges use local peers. See the [runtime guide](../../docs/runtime-library.md) for checks and result interpretation.

## Build and run against configured peers

From the repository root:

```sh
python3 -m venv .venv-runtime
.venv-runtime/bin/python -m pip install ./packages/runtime
npm ci --ignore-scripts --prefix packages/evidence-client
npm run build --prefix packages/evidence-client
npm ci --ignore-scripts --prefix examples/evidence-report
npm run build --prefix examples/evidence-report
```

The client package must be built first: this example's `file:../../packages/evidence-client` dependency uses its compiled exports. Both packages are experimental local artifacts; no registry publication is required.

Copy [config.example.json](config.example.json) to `config.local.json` in this directory. Replace the `.invalid` endpoints, CA path, authority identity, and complete approved tool descriptor/Agent Card. Metadata must match what the compatible peers serve; a changed binding is rejected. The sample is a valid configuration shape, not a running service configuration.

Provide `MEDA_MCP_TOKEN` and `MEDA_A2A_TOKEN` in the Python parent's environment. The configuration names those environment variables; it does not contain credentials. Then, from the repository root:

```sh
.venv-runtime/bin/python -m meda_runtime \
  --config examples/evidence-report/config.local.json \
  --input examples/evidence-report/input.json \
  -- node examples/evidence-report/dist/main.js
```

The CLI returns one receipt. `result.outcome: "Success"` with exit code `0` means the report was accepted and published after worker retirement and cleanup. Other published outcomes use exit code `1`; configuration/input and launch failures use `2` and `3`. The host gives Node a minimal environment without the parent's credential variables. Application results containing known credentials or internal task references in strings or object keys are rejected before final publication; matching proposal/output diagnostics are redacted in the receipt.

## Application inputs

The supplied [input.json](input.json) selects `f1` and `f2` from `evidence-42`. Optional workflow inputs are:

| Field | Meaning |
| --- | --- |
| `documentId` | Evidence document; defaults to `evidence-42` |
| `includeIds` | Nonempty unique selection; defaults to `["f1", "f2"]` |
| `requestClarification` | Submit without an initial selection so the agent can request input |
| `suppliedInput` | Selection to provide once when the task requests input |
| `cancelAfterSubmit` | Request cancellation after a nonterminal submission result |

The host still checks document authority and profile bounds. Without `suppliedInput`, an input-requesting task produces `NeedsInput`; the host then performs its bounded cleanup policy. This example does not store tasks for a later process or user session.

The profile supports five operations and evidence revision **1**. It is not a general MCP/A2A SDK. Await each host call and reserve stdout for `runWorker`. The Python host supplies credential separation, bounded exchange handling, and process supervision; it is not an OS security sandbox. See [the supported boundary](../../docs/runtime-library.md#supported-boundary) before adapting this example.
