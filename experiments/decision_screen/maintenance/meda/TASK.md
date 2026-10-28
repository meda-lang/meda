# Maintenance task: unordered report facts

A report-producing service now returns its selected facts in any order. Change only the body of validateReport so it accepts valid permutations and returns a report with selected facts in the caller's includeIds order.

Preserve validation of document/revision, exact fields and types, requested IDs, matching evidence values, uniqueness, missing/extra facts, empty selection and subsets. Never mutate input report/evidence/requested IDs. Host, adapters, bindings, compiler, input decoding and other application functions must remain unchanged. No new helpers outside this function body.

Use only this packet's files and the command below; do not read the other arm, final acceptance fixtures/results, or ask another agent to do so. This is instruction isolation on a shared filesystem. You may submit at most three candidates through the visible command. Preserve every submitted source and result. Stop once visible checks pass; final acceptance happens after both candidates are frozen and cannot guide repair.

The two visible examples show an already ordered success and a reversed success that must normalize to request order. Return a concise report of edited behavior and the number of visible attempts. Do not commit. Exact model/usage metadata may be unavailable; do not invent it.

Visible command:

```sh
/workspace/scratch/bf91ba952a37/meda-decision/experiments/interop_d0/.venv/bin/python /workspace/scratch/bf91ba952a37/meda-decision/experiments/decision_screen/maintenance.py visible /workspace/scratch/bf91ba952a37/meda-decision/experiments/decision_screen/maintenance/meda
```
