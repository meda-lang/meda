"""Build/install both packages and run an external TypeScript consumer.

Only this development driver imports the old SDK fixtures. The installed runtime
and application run in a clean temporary cwd, without the repository on sys.path.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from experiments.interop_d0.runner import environment,workflow_input
from experiments.interop_d0 import support


def run(command,**kwargs):
    return subprocess.run(command,check=True,text=True,capture_output=True,timeout=180,**kwargs)


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def snapshot():
    paths=[]
    for folder in ['packages/runtime','packages/evidence-client','examples/evidence-report','experiments/interop_d0']:
        paths.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and p.suffix in ('.py','.ts','.json','.toml','.lock') and
                     not any(part in ('node_modules','dist','build','__pycache__','.venv','results','generated-results') for part in p.parts) and
                     not any(part.endswith('.egg-info') or part.startswith('.type-test-') for part in p.parts))
    paths.append(Path(__file__).resolve())
    return {str(p.relative_to(ROOT)):digest(p) for p in sorted(paths)}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--case',choices=['success','required-input','unknown-delivery','malformed-response','invalid-report','reordered-report','cancel-refusal'])
    args=parser.parse_args()
    if args.output.exists():raise ValueError('Preserve earlier receipts; choose a new output path')
    output={'profile':'meda-runtime-package-check/1','startedUnixSeconds':time.time(),'sourceBefore':snapshot(),
            'scope':'installed evidence/report profile against local deterministic SDK fixtures','runs':[]}
    with tempfile.TemporaryDirectory(prefix='meda-installed-consumer-') as tmp:
        tmp=Path(tmp);artifacts=tmp/'artifacts';artifacts.mkdir()
        run([sys.executable,'-m','pip','wheel','--no-deps','--wheel-dir',str(artifacts),str(ROOT/'packages/runtime')])
        wheel=next(artifacts.glob('meda_runtime-*.whl'))
        run(['npm','run','build','--prefix',str(ROOT/'packages/evidence-client')])
        packed=json.loads(run(['npm','pack','--ignore-scripts','--json','--pack-destination',str(artifacts)],cwd=ROOT/'packages/evidence-client').stdout)
        archive=artifacts/packed[0]['filename']
        venv=tmp/'venv';run([sys.executable,'-m','venv',str(venv)])
        python=venv/'bin/python';run([str(python),'-m','pip','install','--no-deps',str(wheel)])
        consumer=tmp/'consumer';shutil.copytree(ROOT/'examples/evidence-report',consumer,ignore=shutil.ignore_patterns('node_modules','dist'))
        config=json.loads((consumer/'package.json').read_text());config['dependencies']['@meda/evidence-client']='file:'+str(archive)
        (consumer/'package.json').write_text(json.dumps(config))
        (consumer/'package-lock.json').unlink(missing_ok=True)
        run(['npm','install','--ignore-scripts','--no-audit','--no-fund'],cwd=consumer)
        run(['npm','run','build'],cwd=consumer)
        import_probe='''import importlib.util,json,meda_runtime;from importlib.metadata import distribution
assert importlib.util.find_spec("experiments") is None
print(json.dumps({"runtimePath":meda_runtime.__file__,"runtimeDependencies":distribution("meda-runtime").requires or [],"experimentsImportable":False}))'''
        clean_env={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME','NODE_OPTIONS')}
        imported=json.loads(run([str(python),'-I','-c',import_probe],cwd=consumer,env=clean_env).stdout)
        assert str(venv) in imported['runtimePath'] and imported['runtimeDependencies']==[]
        resolved=run(['node','-e','console.log(require.resolve("@meda/evidence-client"))'],cwd=consumer,env=clean_env).stdout.strip()
        assert resolved.startswith(str(consumer/'node_modules')) and ROOT.as_posix() not in resolved
        with zipfile.ZipFile(wheel) as archive_file: wheel_files=archive_file.namelist()
        with tarfile.open(archive) as archive_file:
            npm_files=archive_file.getnames()
            npm_metadata=json.load(archive_file.extractfile('package/package.json'))
        assert not npm_metadata.get('dependencies')
        assert not any('experiments/' in name or '/tests/' in name for name in wheel_files+npm_files)
        output['packages']={'python':{'sha256':digest(wheel),'files':wheel_files,'runtimeDependencies':[]},
                            'typescript':{'sha256':digest(archive),'files':npm_files,'runtimeDependencies':[]},
                            'cleanExternalInstall':True,'experimentsImportableInConsumer':False}
        cases=[('success',{},'Success',1),('required-input',{'initialIncludeIds':None,'suppliedIncludeIds':['f1','f2']},'Success',1),
               ('unknown-delivery',{'dropResponseAfterPeerCommit':'submit'},'TransportFailure',1),
               ('malformed-response',{'wireMutation':'evidence_response_id'},'ProtocolRejected',0),
               ('invalid-report',{'reportMutation':'wrong_value'},'DomainRejected',1),
               ('reordered-report',{'reportMutation':'reordered_ids'},'Success',1),
               ('cancel-refusal',{'applicationAction':'cancel','cancelResponse':'TaskNotCancelableError'},'TaskNotCancelable',1)]
        for name,scenario,expected,task_count in cases:
            if args.case and args.case!=name:continue
            with environment(scenario) as env:
                config=asdict(env['host'].config);mcp_token=config.pop('mcp_token');a2a_token=config.pop('a2a_token')
                config['mcp_token_env']='MEDA_DEMO_MCP_TOKEN';config['a2a_token_env']='MEDA_DEMO_A2A_TOKEN'
                for key in ('grants','allowed_documents'):config[key]=sorted(config[key])
                config_path=tmp/'config.json';config_path.write_text(json.dumps(config));config_path.chmod(0o600)
                input_path=tmp/'input.json';input_path.write_text(json.dumps(workflow_input(scenario)))
                child_env=dict(clean_env,MEDA_DEMO_MCP_TOKEN=mcp_token,MEDA_DEMO_A2A_TOKEN=a2a_token)
                command=[str(python),'-I','-m','meda_runtime','--config',str(config_path),'--input',str(input_path),'--','node',str(consumer/'dist/main.js')]
                completed=subprocess.run(command,cwd=consumer,env=child_env,text=True,capture_output=True,timeout=25)
                if completed.returncode not in (0,1):raise RuntimeError('Installed CLI failed: '+completed.stderr[:300])
                receipt=json.loads(completed.stdout)
                peers={protocol:support.read_witness(path) for protocol,path in env['witness_paths'].items()}
                created=[e for e in peers['a2a'] if e.get('event')=='created']
                worker=receipt['worker'];result=receipt['result']
                checks={'outcome':result.get('outcome')==expected,'exitCode':completed.returncode==(0 if expected=='Success' else 1),
                        'workerRetired':worker['retired'] and worker['supervisorJoined'],
                        'onePublication':sum(e['event']=='publication' for e in receipt['trace'])==1,
                        'taskCount':len(created)==task_count,'secretScan':receipt['credentialLeakDetected'] is False,
                        'referenceScan':receipt['referenceLeakDetected'] is False,
                        'rawOutputNoCredentials':all(token not in completed.stdout+completed.stderr for token in env['secrets'])}
                if expected=='Success':
                    checks['exactReport']=result.get('report')=={'documentId':'evidence-42','revision':1,'selected':[{'id':'f1','value':'blue'},{'id':'f2','value':'square'}]}
                else:checks['noReport']='report' not in result
                if name=='unknown-delivery':
                    checks['unknown']=result.get('remoteOutcome')=='Unknown'
                    checks['noResubmit']=sum(e['operation']=='submit' for e in worker['calls'])==1
                if name=='required-input':
                    continued=[e for e in peers['a2a'] if e.get('event')=='continued']
                    checks['sameTaskContinuation']=len(continued)==1 and len(created)==1 and continued[0]['taskId']==created[0]['taskId']
                if name=='cancel-refusal':
                    checks['cleanupSkipped']=len(receipt['cleanup'])==1 and receipt['cleanup'][0].get('reason')=='PriorExplicitRefusal'
                    checks['noCleanupCancel']=not any(e['event']=='dispatch' and e.get('method')=='CancelTask' and e.get('cleanup') for e in receipt['trace'])
                row={'case':name,'scenario':scenario,'expectedOutcome':expected,'receipt':receipt,'peers':peers,
                     'proxy':{p:list(v.events) for p,v in env['proxies'].items()},'checks':checks}
            row['checks']['peerProcessesRetired']=all(p.poll() is not None for p in env['peer_processes'].values())
            row['passed']=all(row['checks'].values());output['runs'].append(row)
            print(json.dumps({'case':name,'outcome':result['outcome'],'passed':row['passed']}),flush=True)
    output['sourceAfter']=snapshot();output['sourceUnchanged']=output['sourceAfter']==output['sourceBefore']
    output['finishedUnixSeconds']=time.time();output['passed']=output['sourceUnchanged'] and all(r['passed'] for r in output['runs'])
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(output,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'passed':output['passed'],'runs':len(output['runs']),'cleanExternalInstall':True}),flush=True)
    return 0 if output['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
