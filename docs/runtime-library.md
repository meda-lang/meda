# Using the Meda runtime packages

The runtime packages let an ordinary TypeScript application use the evidence/report host outside the experiment harness. The application reads evidence through MCP, submits an A2A task, handles task states, and checks the returned report. It does not need the Meda language or compiler.

There are two local packages: Python `meda-runtime` (`0.1.0.dev0`) and TypeScript `@meda/evidence-client` (`0.1.0-alpha.0`). Both have zero runtime dependencies. They are experimental, locally installable packages; the npm package is private, and this work does not publish either package to a registry.

## Run the installed-package demonstration

Use Linux with `/proc`, Python 3.12, Node 24/npm, and OpenSSL. The pinned SDK fixture lock targets Python 3.12 on Linux x86_64. Run these commands from the repository root:

```sh
python3.12 -m venv experiments/interop_d0/.venv
experiments/interop_d0/.venv/bin/python -m pip install --require-hashes --only-binary=:all: -r experiments/interop_d0/requirements.lock
npm ci --ignore-scripts --prefix packages/evidence-client
experiments/interop_d0/.venv/bin/python tools/runtime-demo/verify.py --output results/runtime-library/generated/local.json
```

Choose a new output filename for each run; the driver refuses to overwrite receipts. Dependency installation and package build tooling may use the network. The seven workflow cases run against local HTTPS SDK peers and make no model calls.

The driver builds a Python wheel and npm tarball, installs them into a fresh temporary environment and application directory, compiles the example against the installed npm package, and invokes the installed Python CLI. It checks that the consumer cannot import `experiments` and that neither package contains experiment code. Only the development driver imports the historical SDK fixtures.

| Case | Expected application outcome | What it exercises |
| --- | --- | --- |
| `success` | `Success` | Evidence read, task observation, exact validated report |
| `required-input` | `Success` | Input continues the same task |
| `unknown-delivery` | `TransportFailure`, `Unknown` | Lost response after remote commit; no resubmission |
| `malformed-response` | `ProtocolRejected` | Wrong response correlation |
| `invalid-report` | `DomainRejected` | Application rejects a fact value that disagrees with evidence |
| `reordered-report` | `Success` | Application accepts the same selected facts in a different order |
| `cancel-refusal` | `TaskNotCancelable` | Explicit refusal is preserved; cleanup does not retry cancellation |

Each case also checks worker retirement, one final publication, peer observations, and the defined credential/reference output scan. The JSON receipt contains package hashes and file inventories, individual checks, and source snapshots. A passing demonstration establishes this installed local workflow, not general MCP/A2A interoperability or a new language-benefit result.

For one case, append `--case success` and use a fresh output filename.

## How the pieces connect

The example's complete [main.ts](../examples/evidence-report/main.ts) is four lines:

```ts
import {runWorker} from "@meda/evidence-client";
import {decodeInput, runWorkflow} from "./workflow";

void runWorker(decodeInput, runWorkflow);
```

| Piece | Responsibility |
| --- | --- |
| [workflow.ts](../examples/evidence-report/workflow.ts) | Application input, selected facts, task-state decisions, bounded polling |
| [domain.ts](../examples/evidence-report/domain.ts) | Verify report document/revision, selected IDs, and exact evidence values; normalize selection order |
| [`@meda/evidence-client`](../packages/evidence-client/README.md) | Typed five-operation API, private task-reference membership, profile decoding, worker JSONL framing |
| [`meda-runtime`](../packages/runtime/src/meda_runtime/api.py) | Credentials, approved peers and metadata, operation/document grants, request/deadline budgets, cleanup, worker supervision, final publication |
| MCP evidence server and A2A report agent | Remote protocol handling and task execution |

`runWorker` supplies a `HostApi` to the application. Calls travel over standard input/output to the Python host, which performs the HTTPS exchange and returns a typed result. The host publishes the application result only after the worker exits and cleanup completes. A cleanup failure can change the final published outcome.

`validateReport` belongs to this application. The runtime does not decide whether a report is true or appropriate for another domain. The returned task artifact remains `unknown` until the application checks it. Do not move the example's business rule into a generic runtime guarantee.

## Build the example in this checkout

Use Python 3.11 or later for the runtime itself; the SDK demonstration above uses its narrower pinned Python 3.12 environment. From the repository root:

```sh
python3 -m venv .venv-runtime
.venv-runtime/bin/python -m pip install ./packages/runtime
npm ci --ignore-scripts --prefix packages/evidence-client
npm run build --prefix packages/evidence-client
npm ci --ignore-scripts --prefix examples/evidence-report
npm run build --prefix examples/evidence-report
```

Build `packages/evidence-client` before the example: the example's local `file:` dependency resolves the package's compiled `dist` exports. The demonstration driver separately verifies a real tarball install outside the repository.

To make a local npm tarball manually, run `npm pack` from `packages/evidence-client`. To make a wheel, run `python3 -m pip wheel --no-deps --wheel-dir /tmp/meda-wheels ./packages/runtime` from the repository root. These are local artifact builds, not publication commands.

## Configure approved peers and run the CLI

Copy [config.example.json](../examples/evidence-report/config.example.json) to a local configuration and replace the placeholders before contacting your own compatible peers. The file is a shape example: its `.invalid` URLs and CA path do not identify working services. Its descriptor and Agent Card are illustrative SDK fixture metadata.

The CLI configuration supplies:

- `mcp_url`, `a2a_url`, and `ca_file`: explicit HTTPS endpoints and a trusted CA file. Use an absolute CA path.
- `mcp_token_env` and `a2a_token_env`: names of nonempty environment variables in the Python parent. Literal `mcp_token`/`a2a_token` fields are rejected by the CLI. The sample names are `MEDA_MCP_TOKEN` and `MEDA_A2A_TOKEN`.
- `principal`, `tenant`, `grants`, and `allowed_documents`: the caller's explicit authority. The sample grants all five profile operations for `evidence-42`; narrow these to the intended workflow.
- `tool_descriptor` and `agent_card`: the complete, reviewed metadata approved for those endpoints. The host fetches metadata and compares its digest to these configured objects. Replace the sample metadata with exact approved values, including the Agent Card's matching A2A URL. Discovery does not automatically approve a changed binding.
- `expected_revision: 1` and `limits`: the fixed evidence revision and finite request, byte, polling, event, and cleanup budgets. The sample lists the current defaults. Cleanup requests are reserved within `max_requests`.

After setting the two token environment variables in the Python parent's environment and replacing configuration placeholders, run from the repository root:

```sh
.venv-runtime/bin/python -m meda_runtime \
  --config examples/evidence-report/config.local.json \
  --input examples/evidence-report/input.json \
  -- node examples/evidence-report/dist/main.js
```

The CLI prints one JSON receipt to stdout. `receipt.result` is the final result; the receipt also includes host trace, cleanup, worker-retirement observations, and the defined output-channel scan. Exit code `0` means the published outcome is `Success`; `1` means a different published outcome, `2` means invalid configuration/input, and `3` means launch or supervision failure. Configuration and launch errors use generic stderr messages.

The Python parent supplies credentials directly to its transport. The Node process starts with a minimal environment and does not inherit those credential variables. Do not put credentials in application arguments or JSON input; `run_application` rejects known credentials in those channels. Keep stdout reserved for the worker protocol.

Application results must not carry known credentials or raw internal task references in string values or object keys. A matching proposal causes `ProtocolRejected` before final publication, including the common JSON-escaped forms the output policy checks. The receipt redacts matching application proposals and output diagnostics while preserving runtime-owned fields and outcomes. Its scan includes the ordinary host trace; the top-level credential/reference detection flags derive from the application output channels, so a coincidental match in fixed host vocabulary does not set them.

For Python embedding, the public API is `HostConfig`, `Limits`, and `run_application`:

```python
from meda_runtime import HostConfig, Limits, run_application

# config is a trusted HostConfig with token strings supplied by the parent.
# Its fields match the JSON example except mcp_token/a2a_token replace *_token_env,
# and limits is a Limits instance rather than a JSON object.
receipt = run_application(
    config,
    ["node", "/absolute/path/to/application/dist/main.js"],
    {"documentId": "evidence-42", "includeIds": ["f1", "f2"]},
    cwd="/absolute/path/to/application",
)
```

The caller chooses the executable, working directory, approved metadata, credentials, and grants. `run_application` raises `ValueError` for invalid prelaunch input and `RuntimeError` for process startup/supervision failure; it does not include credentials or child arguments in those exception messages.

## Supported boundary

This release exposes exactly `readEvidence`, `submit`, `observe`, `provideInput`, and `cancel`, with evidence revision **1**. Evidence contains one to 32 facts with unique IDs; IDs and values are nonempty strings of at most 256 Unicode scalar values. Explicit selections contain one to 32 unique IDs. Task references belong to one active binding and cannot be restored from JSON.

The protocol adapter is the existing bounded MCP evidence-read/A2A report-task profile. It does not turn arbitrary tools, arbitrary agent skills, new protocol versions, or new LLM protocols into supported operations. Support for those requires a deliberate adapter and profile change with corresponding tests. The runtime uses no model itself.

Host calls are sequential and must be awaited. Worker frames are limited to 65,536 bytes including their newline. The Python controller also checks JSON shape/depth and supervises Linux process lifetime and sampled RSS. This is not an operating-system security sandbox for hostile Node code: applications retain ordinary filesystem and network facilities, and sampled RSS is not a hard kernel memory limit.

A delivery outcome of `Completed` describes the exchange, not necessarily a terminal remote task. `Unknown` remains unknown; the runtime does not automatically resubmit. Cancellation is a request, not rollback. The output scan reports conservative matches in the named observed channels; coincidental matches are possible. It is not a proof of noninterference or a check of every possible exfiltration path.

The frozen comparisons and their limitations remain in [runtime-comparison.md](runtime-comparison.md) and [decision-screen-results.md](decision-screen-results.md). Packaging does not improve or replace those measurements.
