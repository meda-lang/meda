# Repair packet

Read task.json and edit only candidate.ts.
Run `python3 check.py` for visible checks. Keep the interface and existing declarations.
No imports, unsafe casts, dynamic code, or new I/O. Use the existing code style.
Do not inspect sibling trial folders, reference source, acceptance harness, or other project files.
The checker may invoke installed tools outside this directory; that does not authorize reading them.
Finish when your candidate is ready; do not change check.py or task.json.

TypeScript is compiled with strict checking, explicit returns and a finite Action union.
