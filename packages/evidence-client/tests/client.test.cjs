const assert = require('node:assert/strict');
const {test} = require('node:test');
const {spawn, spawnSync} = require('node:child_process');
const {mkdtempSync, writeFileSync, rmSync} = require('node:fs');
const path = require('node:path');
const api = require('../dist');
const packageRoot = path.resolve(__dirname, '..');
const modulePath = path.join(packageRoot, 'dist');
const evidence = {documentId:'evidence-42', revision:1, facts:[{id:'f1',value:'blue'}]};

async function worker(source, options={}) {
  const directory = mkdtempSync(path.join(packageRoot, '.worker-test-'));
  const file = path.join(directory, 'main.cjs');
  writeFileSync(file, `const {runWorker}=require(${JSON.stringify(modulePath)});\n${source}`);
  const child = spawn(process.execPath, [file], {stdio:['pipe','pipe','pipe']});
  let stdout='', stderr='', pending='';
  const frames=[];
  child.stdin.on('error', () => {});
  child.stdout.on('data', chunk => {
    stdout+=chunk; pending+=chunk;
    while (pending.includes('\n')) {
      const index=pending.indexOf('\n'), line=pending.slice(0,index);pending=pending.slice(index+1);
      const frame=JSON.parse(line);frames.push(frame);
      if (frame.kind==='call' && options.respond) {
        const response=options.respond(frame);
        if (response !== undefined) child.stdin.write(typeof response==='string' ? response : JSON.stringify(response)+'\n');
      }
      if (frame.kind==='finish') child.stdin.end();
    }
  });
  child.stderr.on('data', chunk => { stderr+=chunk; });
  const closed = new Promise((resolve,reject)=> {
    const timer=setTimeout(()=>{child.kill();reject(new Error('worker timeout'));},4000);
    child.once('error',reject);
    child.once('close',(code,signal)=>{clearTimeout(timer);resolve({code,signal,frames,stdout,stderr});});
  });
  try {
    if (options.initialChunks) for (const chunk of options.initialChunks) child.stdin.write(chunk);
    else child.stdin.write(options.initial ?? JSON.stringify({kind:'start',input:{}})+'\n');
    if(options.endInput)child.stdin.end();
    return await closed;
  } finally {
    if(child.exitCode===null)child.kill();
    rmSync(directory,{recursive:true,force:true});
  }
}

function failure(result, calls=0) {
  const finishes=result.frames.filter(x=>x.kind==='finish');
  assert.equal(finishes.length,1);
  assert.deepEqual(finishes[0].result,{outcome:'ProtocolRejected',remoteOutcome:calls ? 'Unknown':'NotStarted',fatal:true});
  assert.equal(result.frames.filter(x=>x.kind==='call').length,calls);
  assert.equal(result.code,1);
  assert.equal(result.stderr,'');
}

test('public package exports contain bindings and worker, not an application validator',()=>{
  const exported=require('@meda/evidence-client');
  assert.equal(exported.runWorker,api.runWorker);
  assert.equal(typeof exported.createBindings,'function');
  assert.equal(exported.validateReport,undefined);
});

test('evidence profile decoders match nonempty host bounds and reject malformed values',()=>{
  const value=api.decodeEvidence(evidence,'evidence-42');
  assert.deepEqual(value,evidence);assert.equal(Object.isFrozen(value.facts[0]),true);
  for(const bad of [null,{...evidence,revision:2},{...evidence,facts:[]},
    {...evidence,facts:[{id:'f1',value:''}]},{...evidence,facts:[{id:'f1',value:'\ud800'}]},
    {...evidence,facts:[...evidence.facts,...evidence.facts]},{...evidence,extra:true}]) {
    assert.equal(api.decodeEvidence(bad,'evidence-42'),null);
  }
  for(const ids of [[],['f1','f1'],[''],['x'.repeat(257)],['\ud800']])assert.equal(api.decodeIds(ids),null);
  assert.deepEqual(api.decodeIds(['😀']),['😀']);
});

test('forged, restored, foreign and retired references cannot dispatch',async()=>{
  const calls=[];
  const first=api.createBindings(async(op,args)=>{calls.push([op,args]);return {kind:'Task',ref:'private-token',state:'Working'};});
  const other=api.createBindings(async()=>{throw Error('unexpected dispatch');});
  const result=await first.host.submit(evidence,['f1']);
  assert.equal(result.kind,'Task');assert.equal(JSON.stringify(result.ref),'{}');
  assert.deepEqual(Object.keys(result.ref),[]);
  for(const ref of [{},'private-token',JSON.parse(JSON.stringify(result.ref))])assert.equal((await first.host.observe(ref)).code,'InvalidReference');
  assert.equal((await other.host.observe(result.ref)).code,'InvalidReference');
  const observed=await first.host.observe(result.ref);assert.equal(observed.ref,result.ref);
  first.close();assert.equal((await first.host.observe(result.ref)).code,'InvalidReference');
  assert.equal(calls.length,2);assert.deepEqual(calls[1],['observe',{ref:'private-token'}]);
});

test('close during exchange rejects late response without issuing another reference',async()=>{
  let resolve;
  const bindings=api.createBindings(()=>new Promise(r=>{resolve=r;}));
  const pending=bindings.host.submit(evidence,['f1']);bindings.close();
  resolve({kind:'Task',ref:'late-private-token',state:'Working'});
  assert.deepEqual(await pending,{kind:'Error',code:'RootTerminated',remoteOutcome:'Unknown',fatal:true});
});

test('bindings reject unknown host states and preserve typed delivery errors',async()=>{
  const bindings=api.createBindings(async()=>({kind:'Task',ref:'token',state:'Future'}));
  assert.equal((await bindings.host.submit(evidence)).code,'ProtocolRejected');
  const error={kind:'Error',code:'TransportFailure',remoteOutcome:'Unknown',fatal:false};
  assert.deepEqual(await api.createBindings(async()=>error).host.readEvidence('evidence-42'),error);
});

test('worker success uses correlated protocol and emits exactly one finish',async()=>{
  const result=await worker(`void runWorker(x=>x,async host=>{const r=await host.readEvidence('evidence-42');return {outcome:r.kind==='Evidence'?'Success':'Failed'};});`,{
    respond: frame=>({kind:'response',id:frame.id,value:{kind:'Evidence',value:evidence}})
  });
  assert.equal(result.code,0);assert.equal(result.stderr,'');
  assert.deepEqual(result.frames.map(x=>x.kind),['call','finish']);
  assert.deepEqual(result.frames[1],{kind:'finish',result:{outcome:'Success'}});
});

test('wrong response correlation fails without leaking exceptions',async()=>{
  failure(await worker(`void runWorker(x=>x,async host=>{await host.readEvidence('evidence-42');throw Error('SECRET');});`,{
    respond:frame=>({kind:'response',id:frame.id+1,value:{kind:'Evidence',value:evidence}})
  }),1);
});

test('concurrent host calls are rejected',async()=>{
  failure(await worker(`void runWorker(x=>x,async host=>{await Promise.all([host.readEvidence('evidence-42'),host.readEvidence('evidence-42')]);return {outcome:'Wrong'};});`),1);
});

test('unawaited host call cannot publish application success',async()=>{
  failure(await worker(`void runWorker(x=>x,async host=>{void host.readEvidence('evidence-42').catch(()=>{});return {outcome:'Wrong'};});`),1);
});

test('multiple initial frames and unsolicited response are rejected',async()=>{
  const start=JSON.stringify({kind:'start',input:{}})+'\n';
  failure(await worker(`void runWorker(x=>x,async()=>({outcome:'Wrong'}));`,{initial:start+start}));
  failure(await worker(`void runWorker(x=>x,async()=>({outcome:'Wrong'}));`,{initial:start+JSON.stringify({kind:'response',id:1,value:{}})+'\n'}));
});

test('oversized incomplete frame is rejected before a newline arrives',async()=>{
  failure(await worker(`void runWorker(x=>x,async()=>({outcome:'Wrong'}));`,{initialChunks:[Buffer.alloc(65536,32),Buffer.from('x')]}));
});

test('invalid UTF-8, malformed JSON and partial EOF reject',async()=>{
  for(const options of [{initial:Buffer.from([0xff,10])},{initial:'{oops}\n'}, {initial:'{',endInput:true}]) {
    failure(await worker(`void runWorker(x=>x,async()=>({outcome:'Wrong'}));`,options));
  }
});

test('oversized outgoing result and exception text produce only bounded generic failure',async()=>{
  failure(await worker(`void runWorker(x=>x,async()=>({outcome:'Wrong',large:'x'.repeat(65536)}));`));
  failure(await worker(`void runWorker(x=>x,async()=>{throw Error('SECRET');});`));
});

test('published declaration types accept a real consumer and reject forged authority',()=>{
  const directory=mkdtempSync(path.join(packageRoot,'.type-test-'));
  try {
    const file=path.join(directory,'consumer.ts');
    const prefix=`import {createBindings, runWorker, type TaskRef, type HostApi, type Evidence} from '../dist';\n`;
    const command=['node_modules/typescript/bin/tsc','--strict','--noEmit','--target','ES2022','--module','commonjs','--moduleResolution','node','--lib','ES2022','--skipLibCheck','--types','node',file];
    for(const [code,accepted] of [
      [`const e: Evidence={documentId:'x',revision:1,facts:[{id:'f',value:'v'}]}; void runWorker(x=>x,async(host:HostApi)=>({outcome:(await host.readEvidence('x')).kind}));`,true],
      ['const forged: TaskRef={};',false],
      [`void runWorker(x=>x,async(host:HostApi)=>{await host.readEvidence(3);return {outcome:'x'};});`,false],
    ]) {
      writeFileSync(file,prefix+code);
      const result=spawnSync(process.execPath,command,{cwd:packageRoot,encoding:'utf8',timeout:10000});
      assert.equal(result.status===0,accepted,result.stdout+result.stderr);
    }
  } finally {rmSync(directory,{recursive:true,force:true});}
});
