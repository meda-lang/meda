"""Evaluate frozen maintenance candidates; never repair after acceptance feedback."""
from pathlib import Path
import argparse,copy,json,shutil,subprocess,sys,tempfile,time
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from experiments.decision_screen.maintenance import assess,protected_hash,sha,D0,HERE
from experiments.decision_screen.oracle import assess as assess_workflow,load_cases
from experiments.interop_d0.runner import execute_workflow


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():raise ValueError('Preserve earlier results')
    base=HERE/'maintenance';final=json.loads((base/'final-freeze.json').read_text());frozen=json.loads((base/'freeze.json').read_text())
    for name,digest in final['candidates'].items():assert sha(ROOT/name)==digest
    # Original candidates intentionally changed; all other packet/fixture data must match.
    changing={str((base/arm/name).relative_to(ROOT)) for arm,name in [('meda','workflow.meda'),('typescript','domain.ts')]}
    assert all(sha(ROOT/name)==digest for name,digest in frozen['files'].items() if name not in changing)
    fixtures=json.loads((base/'acceptance.json').read_text())
    result={'kind':'uncontrolled_maintenance_demonstration','startedUnixSeconds':time.time(),
            'finalFreezeSha256':sha(base/'final-freeze.json'),'packetFreezeSha256':sha(base/'freeze.json'),
            'acceptanceSha256':sha(base/'acceptance.json'),'arms':[],'integration':[],'modelMetadata':frozen['modelMetadata'],
            'isolation':frozen['isolation'],'parentInterventions':[],'productivityConclusion':None}
    for arm,name in [('meda','workflow.meda'),('typescript','domain.ts')]:
        packet=base/arm;meta=json.loads((packet/'packet.json').read_text());candidate=packet/name
        checks=assess(arm,candidate,fixtures)
        row={'arm':arm,'candidateSha256':sha(candidate),'protectedScopeUnchanged':protected_hash(arm,candidate.read_text())==meta['protectedSha256'],
             'checks':checks,'visibleAttempts':[json.loads(p.read_text()) for p in sorted((packet/'attempts').glob('attempt-*.json'))]}
        row['passed']=row['protectedScopeUnchanged'] and all(c['passed'] for c in checks)
        result['arms'].append(row)
    # The protocol fixture already supports reversed selected IDs. Compile the
    # TS candidate with the unchanged application/binding/compiler configuration.
    with tempfile.TemporaryDirectory(prefix='meda-maintenance-integration-') as tmp:
        tmp=Path(tmp);shutil.copytree(D0/'client',tmp/'client')
        shutil.copyfile(base/'typescript/domain.ts',tmp/'client/domain.ts')
        config=json.loads((D0/'tsconfig.json').read_text());config['compilerOptions']['typeRoots']=[str(D0/'node_modules/@types')]
        (tmp/'tsconfig.json').write_text(json.dumps(config))
        subprocess.run(['node',str(D0/'node_modules/typescript/bin/tsc'),'-p',str(tmp/'tsconfig.json')],check=True,timeout=10,capture_output=True)
        for stage in ('baseline','candidate'):
            for arm in ('meda','typescript'):
                case=copy.deepcopy(load_cases()[0]);case['id']='maintenance-'+stage+'-reordered';case['scenario']={'reportMutation':'reordered_ids'}
                if stage=='baseline':case['expected']['outcome']='DomainRejected'
                source=base/'meda/workflow.meda' if stage=='candidate' else HERE/'workflow.meda'
                command=[sys.executable,str(HERE/'worker.py'),'--source',str(source)] if arm=='meda' else None
                path=tmp/'dist/main.js' if arm=='typescript' and stage=='candidate' else None
                receipt=execute_workflow(case['scenario'],worker_command=command,worker_path=path)
                assessment=assess_workflow(case,receipt)
                mutation=any(e.get('event')=='response_mutated' and e.get('mutation')=='reordered_ids' for e in receipt['proxy']['a2a'])
                row={'arm':arm,'stage':stage,'case':case,'receipt':receipt,'assessment':assessment,'reorderMutationObserved':mutation,
                     'passed':assessment['passed'] and mutation}
                result['integration'].append(row)
                print(json.dumps({'arm':arm,'stage':stage,'passed':row['passed'],'outcome':receipt['result']['outcome']}),flush=True)
    result['candidatesUnchanged']=all(sha(ROOT/name)==digest for name,digest in final['candidates'].items())
    result['finishedUnixSeconds']=time.time();result['passed']=result['candidatesUnchanged'] and all(a['passed'] for a in result['arms']+result['integration'])
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'passed':result['passed'],'acceptanceCasesPerArm':len(fixtures)}),flush=True)
    return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
