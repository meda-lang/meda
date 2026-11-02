"""Paired, actually compiled TypeScript mutants over the canonical SDK host.

Only copied application source changes. Bindings, controller, runtime, resource
limits and protocol peers are identical in both arms. The raw bad publication
or denied repeat remains the receipt outcome; the independent oracle decides
whether those observations expose the intended defect.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time

from . import runner


HERE = Path(__file__).resolve().parent
_MUTATIONS = {
    "repeat_after_unknown_submit": (
        "workflow.ts",
        "  let polls = 0;",
        "  // Deliberate source mutant: retry an uncertain submission.\n"
        '  if (task.kind === "Error" && task.remoteOutcome === "Unknown" && !task.fatal) {\n'
        "    task = await host.submit(evidence.value,\n"
        "      input.requestClarification ? undefined : selectedIds);\n"
        "  }\n"
        "  let polls = 0;",
    ),
    "accept_wrong_report": (
        "domain.ts",
        "    if (item === null || expected === undefined || item.id !== expected.id ||\n"
        "        item.value !== expected.value) return null;",
        "    // Deliberate source mutant: retain shape/ID checks but omit value agreement.\n"
        "    if (item === null || expected === undefined || item.id !== expected.id) return null;",
    ),
}


def _compile(project: Path, options: dict) -> dict:
    """Use the canonical compiler pin and the same supervised compile limits."""
    compiler = HERE / "node_modules/typescript/bin/tsc"
    package = HERE / "node_modules/typescript/package.json"
    if not package.is_file() or json.loads(package.read_text())["version"] != "5.9.3":
        raise RuntimeError("Install the pinned TypeScript dependency with npm ci")
    if not Path("/proc/self/status").is_file():
        raise RuntimeError("RSS supervision requires Linux /proc in this profile")
    with tempfile.TemporaryFile() as output:
        process = subprocess.Popen(
            [runner._node(), "--max-old-space-size=96", str(compiler), "-p", str(project / "tsconfig.json")],
            cwd=project, stdout=output, stderr=subprocess.STDOUT,
            env=runner._safe_environment(), start_new_session=True,
        )
        start, peak = time.monotonic(), 0
        try:
            while process.poll() is None:
                peak = max(peak, runner._rss(process.pid))
                if peak > runner.MAX_RSS or time.monotonic() - start >= 10:
                    raise RuntimeError("TypeScript mutation compilation exceeded its supervised limit")
                time.sleep(.02)
            if process.returncode:
                # Diagnostics are unnecessary for a public receipt and could
                # include paths or source text. Do not forward them.
                raise RuntimeError("TypeScript mutation compilation failed")
        finally:
            if process.poll() is None:
                runner._kill(process)
        return {"compiler": "TypeScript", "version": "5.9.3", "passed": True,
                "sourceStrict": options.get("strict") is True, "options": options,
                "peakRssBytesObserved": peak, "elapsedSeconds": time.monotonic() - start,
                "rssLimitBytes": runner.MAX_RSS, "wallLimitSeconds": 10, "v8OldSpaceMiB": 96}


@contextlib.contextmanager
def _compiled_pair(mutation: str):
    if mutation not in _MUTATIONS:
        raise runner.UnsupportedScenario("Unsupported TypeScript source mutation")
    filename, before, after = _MUTATIONS[mutation]
    sources = {str(path.relative_to(HERE / "client")): path.read_text()
               for path in sorted((HERE / "client").rglob("*.ts"))}
    if sources.get(filename, "").count(before) != 1:
        raise RuntimeError("Source mutation anchor changed; review the fixture")
    config = json.loads((HERE / "tsconfig.json").read_text())
    if config["compilerOptions"].get("strict") is not True:
        raise RuntimeError("The source mutation baseline must remain strict")
    with tempfile.TemporaryDirectory(prefix="meda-source-mutants-") as directory:
        projects, compilers, hashes = {}, {}, {}
        for arm in ("control", "mutant"):
            project = Path(directory) / arm
            project.mkdir()
            projects[arm] = project
            # Resolution uses the very same locked dependency installation.
            (project / "node_modules").symlink_to(HERE / "node_modules", target_is_directory=True)
            values = dict(sources)
            if arm == "mutant":
                values[filename] = values[filename].replace(before, after, 1)
            for relative, content in values.items():
                path = project / "client" / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            (project / "tsconfig.json").write_text(json.dumps(config))
            hashes[arm] = {name: hashlib.sha256(value.encode()).hexdigest()
                           for name, value in values.items()}
            compilers[arm] = _compile(project, config["compilerOptions"])
        yield projects, {"kind": "source_mutant", "mutation": mutation, "arm": "typescript",
                         "changedFiles": [filename], "sourceSha256": hashes,
                         "compiler": compilers}


def execute_source_mutant(scenario: dict) -> dict:
    """Execute a frozen scenario against one canonical and one mutated client."""
    mutation = scenario.get("sourceMutation")
    if mutation not in _MUTATIONS:
        raise runner.UnsupportedScenario("Unsupported TypeScript source mutation")
    scenario = {key: value for key, value in scenario.items() if key != "sourceMutation"}
    with _compiled_pair(mutation) as (projects, execution):
        control = runner.execute_workflow(scenario, worker_path=projects["control"] / "dist/main.js")
        mutant = runner.execute_workflow(scenario, worker_path=projects["mutant"] / "dist/main.js")
    mutant.update(mutationControl=control, mutationExecution=execution)
    return mutant
