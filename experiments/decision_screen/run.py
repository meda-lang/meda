"""Run the predeclared small comparison against fresh official SDK peers."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from experiments.interop_d0.runner import compile_client,execute_workflow
from experiments.decision_screen.language import Program
from experiments.decision_screen.oracle import load_cases,assess
HERE=Path(__file__).resolve().parent


def source_snapshot():
    files=set()
    for directory,patterns in [
        (ROOT/'experiments/gates',['*.py']),
        (ROOT/'experiments/interop_d0',['*.py','*.json','requirements.lock','client/*.ts']),
        (HERE,['*.py','*.meda','cases.json']),
    ]:
        for pattern in patterns: files.update(directory.glob(pattern))
    files.add(ROOT/'docs/decision-screen-contract.md')
    return {str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(files) if path.is_file()}


def write(path,data):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
    temporary.replace(path)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--case',action='append')
    args=parser.parse_args()
    if args.output.exists(): raise ValueError('Refusing to replace an existing receipt')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    cases=load_cases()
    if args.case:
        if set(args.case)-{c['id'] for c in cases}:raise ValueError('Unknown case')
        cases=[c for c in cases if c['id'] in args.case]
    Program((HERE/'workflow.meda').read_text())
    compiler=compile_client()
    before=source_snapshot()
    output={'profile':'meda-decision-screen/1','kind':'bounded_screen_not_full_D0_acceptance',
            'startedUnixSeconds':time.time(),'sourceBefore':before,'compiler':compiler,'runs':[],
            'fixtureMode':'official_SDK_peers_deterministic_no_model_calls',
            'selectedCases':[c['id'] for c in cases]}
    write(args.output,output)
    for index,case in enumerate(cases):
        for arm in (('typescript','meda') if index%2==0 else ('meda','typescript')):
            row={'caseId':case['id'],'kind':case['kind'],'arm':arm,'scenario':case['scenario']}
            try:
                command=[sys.executable,str(HERE/'worker.py')] if arm=='meda' else None
                row['receipt']=execute_workflow(case['scenario'],worker_command=command)
                row['assessment']=assess(case,row['receipt'])
                row['status']='passed' if row['assessment']['passed'] else 'failed'
            except Exception as error:
                row.update(status='execution_error',errorType=type(error).__name__)
            output['runs'].append(row)
            write(args.output,output)
            print(json.dumps({'case':case['id'],'arm':arm,'status':row['status'],
                  'outcome':row.get('receipt',{}).get('result'),
                  'failedChecks':row.get('assessment',{}).get('failedChecks')}),flush=True)
    after=source_snapshot()
    output.update(sourceAfter=after,sourceUnchanged=before==after,finishedUnixSeconds=time.time())
    output['pairs']=[]
    for case in cases:
        rows=[r for r in output['runs'] if r['caseId']==case['id']]
        both_passed=len(rows)==2 and all(r['status']=='passed' for r in rows)
        same=False
        if all('receipt' in r for r in rows):
            def normalized(row):
                return {'result':row['receipt']['result'],
                        'calls':row['receipt']['worker']['calls'],
                        'dispatches':[{k:e.get(k) for k in ('protocol','method','cleanup')}
                                      for e in row['receipt']['trace'] if e['event']=='dispatch']}
            same=normalized(rows[0])==normalized(rows[1])
        output['pairs'].append({'caseId':case['id'],'bothIndependentlyPassed':both_passed,'sameOutcomesCallsDispatches':same})
    output['passed']=output['sourceUnchanged'] and all(p['bothIndependentlyPassed'] and p['sameOutcomesCallsDispatches'] for p in output['pairs'])
    write(args.output,output)
    print(json.dumps({'passed':output['passed'],'sourceUnchanged':output['sourceUnchanged'],'runs':len(output['runs'])}),flush=True)
    return 0 if output['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
