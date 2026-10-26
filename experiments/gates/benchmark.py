#!/usr/bin/env python3
"""Preregisterable maintenance screen; smoke evidence is separate from model trials.

An external agent driver receives JSON on stdin and returns JSON containing body
and optional measured usage on stdout. It never receives solutions/acceptance data.
No provider credentials, model selection, or paid calls are implicit.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import random
import signal
import subprocess
import sys
import tempfile
import time

from meda_core import Diagnostic, Evaluator, Program, digest
from edit_protocol import Host, acceptance, same_value
import python_control

ROOT = Path(__file__).resolve().parent


def apply_control(source, symbol, body):
    return python_control.replace_body(source, symbol, body)


def check_cases(source, language, cases):
    if language == "meda":
        return acceptance(Program(source), cases)
    python_control.checked_tree(source)
    results = []
    for case in cases:
        try:
            value = python_control.evaluate(source, case["operation"], case["arguments"])
            results.append({"id":case["id"],"status":"pass" if same_value(value, case["expected"]) else "fail"})
        except Diagnostic as error:
            results.append({"id":case["id"],"status":"fail","code":error.code})
    return results


def setup_host(root, task):
    source = task["languages"]["meda"]["source"]
    (root/"app.meda").write_text(source)
    checks = json.dumps(task["acceptance"])
    (root/"checks.json").write_text(checks)
    grant = {"version":1,"grantId":task["id"],"baseRevision":digest(source),
             "allowedTargets":[task["operation"]],"allowSpecificationRoots":[],
             "checkFile":"checks.json","checkDigest":digest(checks),"testIds":[],"expiresAt":None}
    (root/"grant.json").write_text(json.dumps(grant))
    host = Host(root/"app.meda",root/"grant.json")
    return host, host.begin_edit(digest(source))["transaction"]


def smoke(tasks):
    rows = []
    for task in tasks:
        for language in ("meda","python"):
            start = time.monotonic()
            source = task["languages"][language]["source"]
            broken = check_cases(source, language, task["acceptance"])
            if all(row["status"] == "pass" for row in broken):
                raise RuntimeError(task["id"] + " lacks an effective acceptance oracle")
            solution = task["languages"][language]["solution"]
            if language == "meda":
                with tempfile.TemporaryDirectory() as tmp:
                    host, tx = setup_host(Path(tmp),task)
                    host.replace_body(tx, task["operation"], solution)
                    receipt = host.validate_edit(tx)
                    if receipt["status"] != "validated":
                        raise RuntimeError(str(receipt))
                    host.commit_edit(tx,receipt["receiptId"],digest(source))
                    final = host.path.read_text()
            else:
                final = apply_control(source,task["operation"],solution)
            results = check_cases(final,language,task["acceptance"])
            if not all(row["status"] == "pass" for row in results):
                raise RuntimeError(f"Reference repair failed: {task['id']} {language} {results}")
            rows.append({"task":task["id"],"language":language,"initialRejected":True,
                         "referenceAccepted":True,"acceptanceCases":len(results),"elapsedSeconds":time.monotonic()-start})
    return {"kind":"oracle_smoke", "modelTrials":0, "gateBDecision":"not_evaluated",
            "interpretation":"Checks the corpus and harness only; reference repairs are not independent AI trials.","rows":rows}


def driver_call(command, request, timeout, cwd):
    p = subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                         text=True,cwd=cwd,start_new_session=True)
    try:
        stdout, stderr = p.communicate(json.dumps(request),timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid,signal.SIGKILL)
        p.communicate()
        raise Diagnostic("AgentTimeout","Agent driver exceeded the trial time budget.",phase="experiment") from None
    if p.returncode:
        raise Diagnostic("AgentDriverFailure","Agent driver returned a failure status.",phase="experiment")
    if len(stdout) > 256_000:
        raise Diagnostic("AgentResponseLimit","Agent response too large.",phase="experiment")
    response = json.loads(stdout)
    if not isinstance(response,dict) or not isinstance(response.get("body"),str):
        raise Diagnostic("AgentProtocol","Agent response must include a body string.",phase="experiment")
    return response


def trials(tasks,args):
    command = json.loads(args.agent_command)
    if not isinstance(command,list) or not command or not all(isinstance(x,str) for x in command):
        raise ValueError('--agent-command must be a JSON argv array')
    schedule = [(task,lang,repeat) for task in tasks for lang in ('meda','python') for repeat in range(args.repeats)]
    random.Random(args.seed).shuffle(schedule)
    rows = []
    docs = (ROOT/'PROFILE.md').read_text()
    for task,language,repeat in schedule:
        source = task['languages'][language]['source']
        prompt = {'taskId':task['id'],'language':language,'objective':task['summary'],
                  'source':source,'operation':task['operation'],'editKind':'replace_body',
                  'visibleExamples':task['visible'],'documentation':docs,
                  'responseSchema':{'body':'complete Meda braced block or indented Python suite',
                                    'usage':{'inputTokens':'measured integer or null','outputTokens':'measured integer or null'}}}
        history, usage, correct = [], [], False
        started = time.monotonic()
        row = {'task':task['id'],'language':language,'repeat':repeat,'model':args.model_id,'trialKind':'independent_driver',
               'attempts':0,'requestBytes':0,'responseBytes':0,'validationSeconds':0}
        with tempfile.TemporaryDirectory() as work, tempfile.TemporaryDirectory() as driver_work:
            host, tx = setup_host(Path(work),task) if language == 'meda' else (None,None)
            for attempt in range(args.attempts):
                request = {'trial':{'repeat':repeat,'seed':args.seed,'model':args.model_id},'prompt':prompt,'history':history}
                remaining = args.timeout - (time.monotonic()-started)
                if remaining <= 0:
                    row['terminal']='budget_exhausted'
                    break
                row['attempts'] += 1
                row['requestBytes'] += len(json.dumps(request).encode())
                try:
                    response = driver_call(command,request,remaining,driver_work)
                    row['responseBytes'] += len(json.dumps(response).encode())
                    usage.append(response.get('usage'))
                    validation_start = time.monotonic()
                    if language == 'meda':
                        # Each proposal replaces the same original target, preventing
                        # failed staging from contaminating later repair attempts.
                        host,tx = setup_host(Path(work),task)
                        host.replace_body(tx,task['operation'],response['body'])
                        receipt=host.validate_edit(tx)
                        correct=receipt['status']=='validated'
                        if correct:
                            host.commit_edit(tx,receipt['receiptId'],digest(source))
                    else:
                        final=apply_control(source,task['operation'],response['body'])
                        correct=all(c['status']=='pass' for c in check_cases(final,language,task['acceptance']))
                    feedback={'accepted':correct}
                    row['validationSeconds'] += time.monotonic()-validation_start
                    # Acceptance values and fixtures never enter the agent transcript.
                    history.append({'body':response['body'],'feedback':feedback})
                    if correct:
                        break
                except (Diagnostic,ValueError,SyntaxError,RecursionError) as error:
                    feedback={'accepted':False,'code':getattr(error,'code',type(error).__name__),
                              'message':str(error)}
                    history.append({'feedback':feedback})
                    if getattr(error,'code','').startswith('Agent'):
                        row['terminal']=feedback['code']
                        break
        row.update(correct=correct,elapsedSeconds=time.monotonic()-started,usage=usage,
                   tokenAccountingComplete=bool(usage) and all(isinstance(u,dict) and all(type(u.get(k)) is int for k in ('inputTokens','outputTokens')) for u in usage))
        rows.append(row)
        Path(args.output).write_text(json.dumps({'kind':'model_screen','model':args.model_id,'seed':args.seed,
                                               'tasksDigest':digest(tasks),'status':'in_progress','rows':rows},indent=2)+'\n')
    return {'kind':'model_screen','model':args.model_id,'seed':args.seed,'tasksDigest':digest(tasks),'status':'complete',
            'gateBDecision':'inconclusive_screen','limitations':['Python control has no third-party static type checker.',
            'Only body repairs are supported; no syntax/opaque/refactoring comparison.',
            'Multiple named models and a powered follow-up are required for a language-advantage claim.'],'rows':rows}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--smoke',action='store_true')
    p.add_argument('--agent-command')
    p.add_argument('--model-id')
    p.add_argument('--repeats',type=int,default=3)
    p.add_argument('--attempts',type=int,default=4)
    p.add_argument('--timeout',type=int,default=120)
    p.add_argument('--seed',type=int,default=1729)
    p.add_argument('--output',required=True)
    args=p.parse_args()
    if args.repeats < 1 or args.attempts < 1 or args.timeout < 1:
        p.error('Budgets and repeats must be positive.')
    if not args.smoke and not (args.agent_command and args.model_id):
        p.error('Use --smoke or provide an explicit --agent-command and --model-id.')
    tasks=json.loads((ROOT/'benchmark/tasks.json').read_text())['tasks']
    report=smoke(tasks) if args.smoke else trials(tasks,args)
    report['tasksDigest']=digest(tasks)
    Path(args.output).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'kind':report['kind'],'rows':len(report['rows']),'gateBDecision':report['gateBDecision']}))


if __name__=='__main__':
    main()
