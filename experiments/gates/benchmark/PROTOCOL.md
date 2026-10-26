# Gate B maintenance screening experiment

Status: executable harness and development corpus; controlled model trials pending.
The 12 tasks compare small, existing-body repairs in compact Meda and annotated
Python. Every initial program fails at least one acceptance case, while reference
repairs pass. This establishes usable tasks, not an AI-authoring advantage.

## Preregistered screening procedure

Freeze `tasks.json`, the implementation, this protocol, driver source, provider
configuration, and documentation with content digests before each model run.
Use at least two explicitly identified models. For each model run all 12 tasks
in both languages, three fresh trials per task/language, four proposals maximum,
and 120 seconds total per trial. Randomize the 72-trial order using seed 1729.
The follow-up must counterbalance/order-check repeated tasks to limit carryover.

Each driver process gets only objective, initial source, identical profile
documentation, visible examples, output schema, and that trial's prior feedback.
It receives no acceptance values, reference repair, repository path, or previous
trial transcript. Acceptance checks remain in the controller. Separate driver
working directories avoid accidental access; a deployment must also restrict
filesystem and model-side memory/tool access. Public checked-in tasks are a
development screen, not a contamination-resistant held-out benchmark.

Feedback includes syntax/type/scope diagnostics or a binary acceptance result,
equally for both arms. Whole-body replacement is the only edit operation. Meda
edits use the grant/receipt/commit host. Python edits preserve the function
interface and other declarations through AST comparison; both must pass exactly
the same acceptance cases. Python has no full static type checker yet, so even
measured differences must not be attributed solely to source syntax.

Record successful changes, failed attempts, elapsed time, validation time,
request/response bytes, and measured input/output token usage for every attempt.
Unknown token usage stays unknown; byte counts are not token estimates. Failed
trials remain in denominators, including driver/time failures as separate reasons.
Capture provider/model version, sampling settings, cache billing conventions and
retry behavior in the driver provenance. Do not mix oracle smoke rows with trials.

Primary screening metric: task-level paired difference in acceptance success,
aggregating repeats within task. Secondary: total tokens and time per trial,
reported for all attempts and with success/failure strata. Do not compare only
successful trials or divide by zero when no trial succeeds. A promising effect is
at least 10 percentage points higher success with no material cost regression,
or at least 20% lower whole-change cost at comparable success (within 5 points).
These are screening margins, not proof thresholds. Bootstrap by task, not by
individual repeat; 12 tasks are too few for a strong general claim. Report intervals
and sensitivity to task/model; use screening variance to power a held-out follow-up.

Gate B remains **open** until the Python static-checking gap, driver provenance,
independent repeated trials, outcome analysis, and reviewer effort measurement
are complete. The initial harness records the metrics it can observe; human
reviewer effort must be recorded separately. No automatic retain/stop verdict is
produced from a smoke run or a single model's screen.

## Running the harness

```sh
python3 experiments/gates/benchmark.py --smoke --output /tmp/meda-smoke.json
python3 experiments/gates/benchmark.py \
  --agent-command '["/absolute/path/to/model-driver"]' \
  --model-id 'provider/model-and-version' \
  --repeats 3 --attempts 4 --timeout 120 --seed 1729 \
  --output /tmp/meda-model-screen.json
```

The explicitly configured driver reads one JSON request on stdin and writes one
JSON response to stdout:

```json
{"body":"{\n  return value\n}","usage":{"inputTokens":1200,"outputTokens":60}}
```

For Python, `body` is an indented suite. The driver owns model credentials and
provider calls; none are embedded here. It must use fresh model context per trial
and include only that request's history. Exact measured usage includes all
internal driver/model retries. Missing usage is flagged. No live calls occur
without `--agent-command` and `--model-id`.

## Excluded claims and later task families

This screen does not measure sectioned syntax, text-versus-structured editing,
opaque construction, callbacks, new declarations, extraction, interface/schema
evolution, concurrent edits, LLM runtime integration, or multi-file maintenance.
Their implementations/edit paths are absent; they are excluded, not scored as
failures or successes. Gate C and F tasks must include the cost of creating their
abstractions. A shared-runtime language comparison belongs after Gate D.
