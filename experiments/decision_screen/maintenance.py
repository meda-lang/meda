"""Equal ordinary-edit maintenance demonstration; not a controlled model study."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.decision_screen.language import Evaluator, Program, export_value
from experiments.gates.meda_core import Diagnostic
HERE = Path(__file__).resolve().parent
D0 = ROOT / 'experiments/interop_d0'
TSC = D0 / 'node_modules/typescript/bin/tsc'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def body_span(arm, source):
    if arm == 'meda':
        operation = Program(source).ops['validateReport']
        return operation.body_start, operation.body_end
    code = '''const ts=require(process.argv[1]);let s='';process.stdin.on('data',x=>s+=x);process.stdin.on('end',()=>{const f=ts.createSourceFile('domain.ts',s,ts.ScriptTarget.Latest,true);const a=f.statements.filter(x=>ts.isFunctionDeclaration(x)&&x.name?.text==='validateReport');if(a.length!==1||!a[0].body)process.exit(2);console.log(JSON.stringify([a[0].body.getStart(f),a[0].body.getEnd()]));});'''
    run = subprocess.run(['node', '-e', code, str(D0/'node_modules/typescript')], input=source,
                         text=True, capture_output=True, timeout=10, check=True)
    return tuple(json.loads(run.stdout))


def protected_hash(arm, source):
    begin, end = body_span(arm, source)
    return hashlib.sha256((source[:begin] + '\0' + source[end:]).encode()).hexdigest()


def evaluate(arm, source_path, fixtures):
    if arm == 'meda':
        evaluator = Evaluator(Program(Path(source_path).read_text()),
                              lambda *_: (_ for _ in ()).throw(AssertionError('Unexpected host call')))
        outputs = []
        try:
            for fixture in fixtures:
                try:
                    result = evaluator.invoke('validateReport', copy.deepcopy(fixture['arguments']))
                    outputs.append(export_value(result)['fields']['report'] if result['case']=='Value' else None)
                except Diagnostic as error:
                    if error.code != 'InputType':
                        raise
                    outputs.append(None)
        finally:
            evaluator.close()
        return outputs
    with tempfile.TemporaryDirectory(prefix='meda-maintenance-ts-') as tmp:
        root = Path(tmp)
        candidate = root/'domain.ts'
        candidate.write_text(Path(source_path).read_text())
        command = ['node',str(TSC),'--strict','--noImplicitReturns','--noUncheckedIndexedAccess',
                   '--exactOptionalPropertyTypes','--noEmitOnError','--skipLibCheck',
                   '--target','ES2022','--module','commonjs','--outDir',str(root/'dist'),str(candidate)]
        compiled = subprocess.run(command,text=True,capture_output=True,timeout=10)
        if compiled.returncode:
            raise ValueError(compiled.stdout + compiled.stderr)
        driver = '''const {validateReport}=require(process.argv[1]);let s='';process.stdin.on('data',x=>s+=x);process.stdin.on('end',()=>{const rows=JSON.parse(s);console.log(JSON.stringify(rows.map(x=>{const a=x.arguments;const before=JSON.stringify(a);const answer=validateReport(a.value,a.evidence,a.includeIds);if(JSON.stringify(a)!==before)throw Error('InputMutation');return answer;})));});'''
        run = subprocess.run(['node','-e',driver,str(root/'dist/domain.js')],input=json.dumps(fixtures),
                             text=True,capture_output=True,timeout=10,check=True)
        return json.loads(run.stdout)


def assess(arm, source, fixtures):
    actual = evaluate(arm, source, fixtures)
    return [{'id': row['id'], 'passed': value==row['expected'], 'expected':row['expected'], 'actual':value}
            for row,value in zip(fixtures,actual)]


def visible(packet):
    packet=Path(packet)
    meta=json.loads((packet/'packet.json').read_text())
    arm=meta['arm']; candidate=packet/meta['candidate']
    attempts=packet/'attempts';attempts.mkdir(exist_ok=True)
    number=len(list(attempts.glob('attempt-*.json')))+1
    if number>3: raise ValueError('At most three visible candidates are permitted')
    snapshot=attempts/f'candidate-{number}{candidate.suffix}'
    snapshot.write_bytes(candidate.read_bytes())
    start=time.time()
    result={'attempt':number,'sourceSha256':sha(snapshot),'startedUnixSeconds':start}
    try:
        result['protectedScopeUnchanged']=protected_hash(arm,candidate.read_text())==meta['protectedSha256']
        result['checks']=assess(arm,candidate,json.loads((packet/'visible.json').read_text()))
        result['passed']=result['protectedScopeUnchanged'] and all(x['passed'] for x in result['checks'])
    except Exception as error:
        result.update(passed=False,error=type(error).__name__+': '+str(error)[:2000])
    result['elapsedSeconds']=time.time()-start
    (attempts/f'attempt-{number}.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    return result


TASK='''# Maintenance task: unordered report facts

A report-producing service now returns its selected facts in any order. Change only the body of validateReport so it accepts valid permutations and returns a report with selected facts in the caller's includeIds order.

Preserve validation of document/revision, exact fields and types, requested IDs, matching evidence values, uniqueness, missing/extra facts, empty selection and subsets. Never mutate input report/evidence/requested IDs. Host, adapters, bindings, compiler, input decoding and other application functions must remain unchanged. No new helpers outside this function body.

Use only this packet's files and the command below; do not read the other arm, final acceptance fixtures/results, or ask another agent to do so. This is instruction isolation on a shared filesystem. You may submit at most three candidates through the visible command. Preserve every submitted source and result. Stop once visible checks pass; final acceptance happens after both candidates are frozen and cannot guide repair.

The two visible examples show an already ordered success and a reversed success that must normalize to request order. Return a concise report of edited behavior and the number of visible attempts. Do not commit. Exact model/usage metadata may be unavailable; do not invent it.
'''


def fixtures():
    facts=[{'id':'f1','value':'blue'},{'id':'f2','value':'square'},{'id':'f3','value':'round'}]
    evidence={'documentId':'evidence-42','revision':1,'facts':facts}
    def row(name, selected=None, include=None, valid=True, **changes):
        include=['f1','f2'] if include is None else include
        report={'documentId':'evidence-42','revision':1,'selected':copy.deepcopy(facts[:2] if selected is None else selected)}
        report.update(changes)
        expected={'documentId':'evidence-42','revision':1,'selected':[copy.deepcopy(next(f for f in facts if f['id']==i)) for i in include]} if valid else None
        return {'id':name,'arguments':{'value':report,'evidence':copy.deepcopy(evidence),'includeIds':include},'expected':expected}
    visible_rows=[row('ordered'),row('reversed',facts[1::-1])]
    hidden=[row('request-reversed',facts[:2],['f2','f1']),row('three-permuted',[facts[1],facts[2],facts[0]],['f3','f1','f2']),
            row('subset',[facts[2]],['f3']),row('empty',[],[]),row('duplicate',[facts[0],facts[0]],valid=False),
            row('missing',[facts[0]],valid=False),row('extra',facts,valid=False),row('wrong-value',[{'id':'f1','value':'invented'},facts[1]],valid=False),
            row('unknown-request',facts[:2],['f1','missing'],False),row('duplicate-request',[facts[0],facts[0]],['f1','f1'],False),
            row('wrong-document',valid=False,documentId='other'),row('wrong-revision',valid=False,revision=2),
            row('extra-report-field',valid=False,extra=True),row('extra-fact-field',[dict(facts[0],extra=True),facts[1]],valid=False),
            row('wrong-fact-type',[{'id':'f1','value':1},facts[1]],valid=False),row('oversized-value',[{'id':'f1','value':'x'*257},facts[1]],valid=False)]
    return visible_rows,hidden


def prepare():
    base=HERE/'maintenance'
    visible_rows,hidden=fixtures()
    if (base/'freeze.json').exists(): raise ValueError('Already prepared; preserve the original freeze')
    base.mkdir(exist_ok=True)
    (base/'acceptance.json').write_text(json.dumps(visible_rows+hidden,indent=2)+'\n')
    records=[]
    for arm,original,name in [('meda',HERE/'workflow.meda','workflow.meda'),('typescript',D0/'client/domain.ts','domain.ts')]:
        packet=base/arm;packet.mkdir(exist_ok=True)
        (packet/name).write_bytes(original.read_bytes())
        (packet/('baseline'+Path(name).suffix)).write_bytes(original.read_bytes())
        (packet/'visible.json').write_text(json.dumps(visible_rows,indent=2)+'\n')
        command=f'{D0}/.venv/bin/python {HERE}/maintenance.py visible {packet}'
        (packet/'TASK.md').write_text(TASK+'\nVisible command:\n\n```sh\n'+command+'\n```\n')
        if arm=='meda':
            (packet/'PROFILE.md').write_text((ROOT/'experiments/gates/PROFILE.md').read_text()+'\nDirect-call screen types and effects are supplied by the fixed binding. For this pure validator, use the existing Report, Evidence, Fact, and Artifact types; do not add host calls. Artifact.Value(report: ...) is success and Artifact.Invalid is rejection.\n')
        else:
            (packet/'PROFILE.md').write_text('TypeScript 5.9.3. strict, noImplicitReturns, noUncheckedIndexedAccess, exactOptionalPropertyTypes, noEmitOnError; target ES2022. Existing imports and types are provided in candidate source.\n')
        meta={'arm':arm,'candidate':name,'baselineSha256':sha(original),'protectedSha256':protected_hash(arm,original.read_text()),'maxVisibleAttempts':3}
        (packet/'packet.json').write_text(json.dumps(meta,indent=2)+'\n')
        checks=assess(arm,packet/name,visible_rows)
        assert [x['passed'] for x in checks]==[True,False],checks
        records.append({'arm':arm,'baselineChecks':checks,**meta})
    frozen={'kind':'uncontrolled_maintenance_demonstration','createdUnixSeconds':time.time(),'arms':records,
            'files':{str(p.relative_to(ROOT)):sha(p) for p in sorted(base.rglob('*')) if p.is_file()},
            'modelMetadata':{'configuration':'inherited parent configuration for both fresh workers','exactModelRevision':None,'tokenUsage':None,'reasoningSetting':None},
            'isolation':'shared filesystem; instruction isolation only','finalAcceptanceBeforeRepairs':True}
    (base/'freeze.json').write_text(json.dumps(frozen,indent=2)+'\n')
    print(json.dumps({'prepared':True,'baselineReorderedExampleFailsBoth':True,'freezeSha256':sha(base/'freeze.json')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['prepare','visible']);parser.add_argument('packet',nargs='?');a=parser.parse_args()
    if a.command=='prepare': prepare()
    else: visible(a.packet)
