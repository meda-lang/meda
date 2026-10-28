"""Actual paired checker probes, including limitations favoring TypeScript.

run_checks() returns a JSON-serializable receipt. It compiles copied conventional
client sources with their existing strict configuration and evaluates real Meda
source using this screen's Program. No timings are interpreted as performance.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from experiments.gates.meda_core import Diagnostic
from .language import Program, PROFILE

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
D0 = REPO / "experiments/interop_d0"


def _sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _sources():
    paths = [HERE / "workflow.meda", HERE / "language.py", REPO / "experiments/gates/meda_core.py",
             D0 / "tsconfig.json", D0 / "package-lock.json"]
    paths += sorted((D0 / "client").glob("*.ts"))
    return {str(path.relative_to(REPO)): path.read_text() for path in paths}


def _cases():
    read_meda = '''operation probe() -> EvidenceResult effects [ReadEvidence] {
  return host.readEvidence(documentId: "evidence-42")
}
'''
    read_ts = '''import {type HostApi, type EvidenceResult} from "./bindings";
export async function probe(host: HostApi): Promise<EvidenceResult> {
  return host.readEvidence("evidence-42");
}
'''
    fact_meda = 'operation probe() -> Fact effects [] { return Fact { id: "f1", value: "blue" } }\n'
    fact_ts = 'import {type Fact} from "./domain";\nexport function probe(): Fact { return {id: "f1", value: "blue"}; }\n'
    state_meda = 'operation probe() -> TaskState effects [] { return TaskState.Working }\n'
    state_ts = 'import {type TaskState} from "./bindings";\nexport function probe(): TaskState { return "Working"; }\n'
    names = ['Submitted','Working','InputRequired','AuthRequired','Completed','Failed','Canceled','Rejected']
    match_meda = ('operation probe(state: TaskState) -> Text effects [] {\n  match state {\n' +
                  ''.join(f'    TaskState.{name} => {{ return "{name}" }}\n' for name in names) + '  }\n}\n')
    match_ts = ('import {type TaskState} from "./bindings";\n'
                'function unreachable(value: never): never { throw new Error("unexpected state"); }\n'
                'export function probe(state: TaskState): string {\n  switch (state) {\n' +
                ''.join(f'    case "{name}": return "{name}";\n' for name in names) +
                '    default: return unreachable(state);\n  }\n}\n')
    outcome_meda = 'operation staticOutcomeProbe() -> ApplicationResult effects [] { return ApplicationResult.Stopped(outcome: "DomainRejected") }\n'
    outcome_ts = 'import {type ApplicationResult} from "./workflow";\nexport function probe(): ApplicationResult { return {outcome: "DomainRejected"}; }\n'
    error_meda = 'operation probe() -> HostError effects [] { return HostError { code: "Timeout", remoteOutcome: "Unknown", fatal: false } }\n'
    error_ts = 'import {type HostError} from "./bindings";\nexport function probe(): HostError { return {kind: "Error", code: "Timeout", remoteOutcome: "Unknown", fatal: false}; }\n'
    return [
        dict(id='wrong_host_argument_type', group='matched', meda=read_meda,
             meda_mutated=read_meda.replace('documentId: "evidence-42"', 'documentId: 7'),
             typescript=read_ts, typescript_mutated=read_ts.replace('host.readEvidence("evidence-42")', 'host.readEvidence(7)'),
             expected={'meda':False,'typescript':False}),
        dict(id='missing_required_record_field', group='matched', meda=fact_meda,
             meda_mutated=fact_meda.replace(', value: "blue"', ''),
             typescript=fact_ts, typescript_mutated=fact_ts.replace(', value: "blue"', ''),
             expected={'meda':False,'typescript':False}),
        dict(id='misspelled_task_state', group='matched', meda=state_meda,
             meda_mutated=state_meda.replace('Working', 'Workng'),
             typescript=state_ts, typescript_mutated=state_ts.replace('Working', 'Workng'),
             expected={'meda':False,'typescript':False}),
        dict(id='nonexhaustive_task_state', group='matched', meda=match_meda,
             meda_mutated=match_meda.replace('    TaskState.Rejected => { return "Rejected" }\n', ''),
             typescript=match_ts, typescript_mutated=match_ts.replace('    case "Rejected": return "Rejected";\n', ''),
             expected={'meda':False,'typescript':False}),
        dict(id='omitted_effect_bound', group='asymmetry', meda=read_meda,
             meda_mutated=read_meda.replace('[ReadEvidence]', '[]'),
             typescript=read_ts, typescript_mutated=read_ts,
             expected={'meda':False,'typescript':True},
             interpretation='Meda checks its explicit effect bound. TypeScript has no corresponding declaration here; its source is unchanged and valid. This is a profile-specific check, not a claim that conventional tooling cannot enforce effect policies.'),
        dict(id='misspelled_application_outcome', group='asymmetry', meda=outcome_meda,
             meda_mutated=outcome_meda.replace('DomainRejected', 'DomainRejectd'),
             typescript=outcome_ts, typescript_mutated=outcome_ts.replace('DomainRejected', 'DomainRejectd'),
             append_workflow=True, expected={'meda':True,'typescript':False},
             interpretation='The current Meda ApplicationResult.Stopped payload is Text; the conventional ApplicationResult uses a finite outcome union. Meda accepts this typo and TypeScript rejects it.'),
        dict(id='misspelled_host_error_code', group='asymmetry', meda=error_meda,
             meda_mutated=error_meda.replace('Timeout', 'Timeuot'),
             typescript=error_ts, typescript_mutated=error_ts.replace('Timeout', 'Timeuot'),
             expected={'meda':True,'typescript':False},
             interpretation='The current Meda HostError.code field is Text; the conventional HostError uses ErrorCode. Wire allowlisting does not give Meda-created records a static enum guarantee.'),
    ]


def _meda_check(source):
    try:
        Program(source)
        return {'accepted':True, 'diagnostics':[]}
    except Diagnostic as exc:
        return {'accepted':False, 'diagnostics':[{'code':exc.code,'phase':exc.phase,'message':exc.message,'offset':exc.pos}]}


def run_checks():
    """Run controls and defects; `passed` means observed checks match expectations."""
    sources = _sources()
    compiler = D0 / 'node_modules/typescript/bin/tsc'
    package = D0 / 'node_modules/typescript/package.json'
    node = shutil.which('node')
    if node is None or not compiler.is_file() or json.loads(package.read_text())['version'] != '5.9.3':
        raise RuntimeError('Install the pinned TypeScript 5.9.3 dependency with npm ci first')
    workflow = sources['experiments/decision_screen/workflow.meda']
    hashes = {path:_sha(source) for path,source in sources.items()}
    rows = []
    with tempfile.TemporaryDirectory(prefix='meda-static-screen-') as directory:
        project = Path(directory)
        (project / 'client').mkdir()
        for path,source in sources.items():
            if path.startswith('experiments/interop_d0/client/'):
                (project / 'client' / Path(path).name).write_text(source)
        config = json.loads(sources['experiments/interop_d0/tsconfig.json'])
        config = copy.deepcopy(config)
        config['compilerOptions']['typeRoots'] = [str(D0 / 'node_modules/@types')]
        config['compilerOptions']['noEmit'] = True
        (project / 'tsconfig.json').write_text(json.dumps(config))
        flags = {key:value for key,value in config['compilerOptions'].items() if key != 'typeRoots'}

        def typescript_check(source=None):
            probe = project / 'client/static-probe.ts'
            if source is None:
                if probe.exists(): probe.unlink()
            else:
                probe.write_text(source)
            try:
                result = subprocess.run([node, '--max-old-space-size=96', str(compiler), '-p', str(project / 'tsconfig.json')],
                    cwd=project, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    timeout=10, env={'PATH':os.defpath,'LANG':'C.UTF-8'})
                output = result.stdout.replace(str(project), '<temporary-project>').replace(str(REPO), '<repository>')
                return {'accepted':result.returncode == 0, 'exitCode':result.returncode,
                        'diagnostics':output.splitlines()[:40], 'diagnosticsTruncated':len(output.splitlines()) > 40}
            except subprocess.TimeoutExpired:
                return {'accepted':False, 'infrastructureError':'compiler timeout after 10 seconds', 'diagnostics':[]}

        baseline = {'meda':_meda_check(workflow),'typescript':typescript_check()}
        for case in _cases():
            meda_prefix = workflow + '\n' if case.get('append_workflow') else ''
            meda_control = meda_prefix + case['meda']
            meda_mutation = meda_prefix + case['meda_mutated']
            controls = {'meda':_meda_check(meda_control),'typescript':typescript_check(case['typescript'])}
            observed = {'meda':_meda_check(meda_mutation),'typescript':typescript_check(case['typescript_mutated'])}
            passed = (all(item['accepted'] for item in controls.values()) and
                      all(observed[arm]['accepted'] == expected for arm,expected in case['expected'].items()) and
                      not any('infrastructureError' in item for item in [*controls.values(),*observed.values()]))
            row = {'id':case['id'],'group':case['group'],'expectedMutationAccepted':case['expected'],
                   'controls':controls,'mutations':observed,'passed':passed,
                   'sources':{'meda':{'control':case['meda'],'mutation':case['meda_mutated'],
                                      'prefix':'workflow.meda' if meda_prefix else None,
                                      'controlSha256':_sha(meda_control),'mutationSha256':_sha(meda_mutation)},
                              'typescript':{'control':case['typescript'],'mutation':case['typescript_mutated'],
                                            'controlSha256':_sha(case['typescript']),
                                            'mutationSha256':_sha(case['typescript_mutated'])}}}
            if 'interpretation' in case: row['interpretation'] = case['interpretation']
            rows.append(row)
    after_hashes = {path:_sha(source) for path,source in _sources().items()}
    stable = hashes == after_hashes
    return {'schema':'meda-decision-static/1','profile':PROFILE,
            'compiler':{'name':'TypeScript','version':'5.9.3','options':flags,
                        'typeRoots':'pinned interop_d0/node_modules/@types',
                        'timeoutSeconds':10,'oldSpaceMiB':96},
            'baselineSourceHashes':hashes,'baselineUnchangedDuringChecks':stable,
            'sourceLineCounts':{path:len(source.splitlines()) for path,source in sources.items() if path.endswith(('.ts','.py','.meda'))},
            'baselineControls':baseline,'cases':rows,
            'passed':stable and all(item['accepted'] for item in baseline.values()) and all(row['passed'] for row in rows),
            'scope':'Four matched defects and three explicit asymmetries. These are fixed checker probes, not productivity measurements or comprehensive language guarantees.'}


def main():
    print(json.dumps(run_checks(), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
