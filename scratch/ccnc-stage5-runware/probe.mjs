import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import http from 'node:http';
import assert from 'node:assert/strict';
import Ajv2020 from 'ajv/dist/2020.js';
import {Client} from '@modelcontextprotocol/sdk/client/index.js';
import {StdioClientTransport} from '@modelcontextprotocol/sdk/client/stdio.js';
import corePkg from '@node-wot/core';
import httpPkg from '@node-wot/binding-http';
const {Servient}=corePkg,{HttpClientFactory}=httpPkg;
const cloned=x=>JSON.parse(JSON.stringify(x));
const outdir='evidence';
fs.mkdirSync(outdir,{recursive:true});
const mocklog=path.resolve(outdir,'sdk_mock_wire.ndjson');
fs.writeFileSync(mocklog,'');
let mcp,bridge,transport,servient;
const result={status:'INCOMPLETE',externalServer:'@runware/mcp@1.4.0 (published, unmodified)',backend:'test-only fake @runware/sdk injected via ESM resolve hook',calls:[],http_wire:[],cases:[],limitations:['The real Runware network API was not called','The output difference is produced by a controlled SDK substitute, not a production model','Stock node-wot input validation is not assumed']};
const ajv=new Ajv2020({allErrors:true,strict:false});
const reply=(res,code,obj)=>{const b=Buffer.from(JSON.stringify(obj));res.writeHead(code,{'content-type':'application/json','content-length':b.length});res.end(b)};
const getText=r=>(r.content||[]).filter(x=>x.type==='text').map(x=>x.text).join('\n');
const asJSON=r=>JSON.parse(getText(r));
async function sourceCall(args){
  const r=await mcp.callTool({name:'run',arguments:args});
  const record={args:cloned(args),isError:!!r.isError,text:getText(r)};
  result.calls.push(record);
  return record;
}
function policy(input,mode){
  const sc=cloned(input),extension=sc['ccnc:additionalPropertiesSchema'];
  delete sc['ccnc:additionalPropertiesSchema'];
  sc.additionalProperties=mode==='repaired'?extension:false;
  return sc;
}
async function strictCase(thing,td,args,mode,name){
  const fn=ajv.compile(policy(td.actions.run.input,mode));
  const valid=!!fn(args),before=result.http_wire.length;
  let value=null,error=null;
  if(valid){try{const response=await thing.invokeAction('run',args);value=await response.value()}catch(e){error=String(e)}}
  const rec={name,mode,args:cloned(args),valid,errors:(fn.errors||[]).map(e=>({keyword:e.keyword,instancePath:e.instancePath})),http_sent:result.http_wire.length-before,value,error};
  result.cases.push(rec);return rec;
}
try{
  const exe=path.resolve('node_modules/@runware/mcp/dist/index.js');
  assert(fs.existsSync(exe),'Published @runware/mcp executable missing');
  const childArgs=['--no-warnings','--loader',path.resolve('mock-loader.mjs'),exe];
  transport=new StdioClientTransport({command:process.execPath,args:childArgs,stderr:'pipe',env:{...process.env,RUNWARE_API_KEY:'ISOLATED_TEST_KEY_NOT_REAL',RUNWARE_MOCK_LOG:mocklog}});
  result.server_stderr='';
  transport.stderr?.on('data',v=>{result.server_stderr=(result.server_stderr+String(v)).slice(-9000)});
  mcp=new Client({name:'ccnc-stage5-test',version:'1.0.0'});
  await Promise.race([mcp.connect(transport),new Promise((_,reject)=>setTimeout(()=>reject(new Error('MCP connect timeout')),20000))]);
  const list=await mcp.listTools();
  const tool=list.tools.find(t=>t.name==='run');
  assert(tool,'run tool missing');
  result.advertised_schema=tool.inputSchema;
  assert.deepEqual(Object.keys(tool.inputSchema.properties),['model'],'Only model must be an individual property');
  assert(tool.inputSchema.additionalProperties&&typeof tool.inputSchema.additionalProperties==='object');
  const normal={model:'runware:400@1'};
  const amber={model:'runware:400@1',positivePrompt:'amber',width:'256'};
  const blue={model:'runware:400@1',positivePrompt:'blue',width:'512'};
  const d1=await sourceCall(amber),d2=await sourceCall(blue);
  assert(!d1.isError&&!d2.isError,'Mocked direct source call failed');
  const one=asJSON({content:[{type:'text',text:d1.text}]}),two=asJSON({content:[{type:'text',text:d2.text}]});
  assert(one.received.width===256&&two.received.width===512,'Unmodified tool did not coerce extra width to number');
  assert(one.received.positivePrompt==='amber'&&two.received.positivePrompt==='blue','Unlisted prompt did not reach mock SDK');
  assert(one.summary!==two.summary,'Controlled downstream result did not change');
  bridge=http.createServer(async(req,res)=>{
    if(req.method!=='POST'||req.url!=='/run')return reply(res,404,{error:'not-found'});
    const arr=[];for await (const v of req)arr.push(v);
    const raw=Buffer.concat(arr).toString();
    let args;try{args=JSON.parse(raw)}catch{return reply(res,400,{error:'invalid-json'})}
    const entry={raw,args};result.http_wire.push(entry);
    try{const r=await sourceCall(args);entry.result=r;reply(res,r.isError?422:200,{isError:r.isError,text:r.text})}
    catch(e){entry.error=String(e);reply(res,500,{error:entry.error})}
  });
  await new Promise(resolve=>bridge.listen(0,'127.0.0.1',resolve));
  const href='http://127.0.0.1:'+bridge.address().port+'/run';
  const coreInput={type:'object',properties:cloned(tool.inputSchema.properties),required:cloned(tool.inputSchema.required||[])};
  const repairInput={...cloned(coreInput),'ccnc:additionalPropertiesSchema':cloned(tool.inputSchema.additionalProperties)};
  function makeTd(input){return {'@context':['https://www.w3.org/2022/wot/td/v1.1',{htv:'http://www.w3.org/2011/http#',ccnc:'urn:risu:iiwot:experimental:'}],id:'urn:risu:ccnc:runware-mcp-controlled',title:'Published Runware MCP with controlled SDK',securityDefinitions:{nosec_sc:{scheme:'nosec'}},security:'nosec_sc',actions:{run:{input,output:{type:'object',properties:{isError:{type:'boolean'},text:{type:'string'}},required:['isError','text']},forms:[{href,op:'invokeaction',contentType:'application/json','htv:methodName':'POST'}]}}}}
  result.before_td=makeTd(coreInput);result.after_td=makeTd(repairInput);
  servient=new Servient();servient.addClientFactory(new HttpClientFactory());
  const WoT=await servient.start();
  const before=await WoT.consume(result.before_td),after=await WoT.consume(result.after_td);
  const c0=await strictCase(before,result.before_td,normal,'baseline','baseline_model_only');
  const c1=await strictCase(before,result.before_td,amber,'baseline','baseline_unlisted_prompt');
  const c2=await strictCase(after,result.after_td,amber,'repaired','repaired_amber');
  const c3=await strictCase(after,result.after_td,blue,'repaired','repaired_blue');
  const c4=await strictCase(after,result.after_td,{model:'runware:400@1',positivePrompt:null},'repaired','repaired_null_extra_rejected');
  const c5=await strictCase(after,result.after_td,{positivePrompt:'amber',width:256},'repaired','repaired_missing_model_rejected');
  assert(c0.valid&&c0.http_sent===1&&!c0.error);
  assert(!c1.valid&&c1.http_sent===0);
  assert(c2.valid&&c2.http_sent===1&&!c2.error);
  assert(c3.valid&&c3.http_sent===1&&!c3.error);
  assert(c2.value.text!==c3.value.text);
  assert(!c4.valid&&c4.http_sent===0);
  assert(!c5.valid&&c5.http_sent===0);
  const mockRows=fs.readFileSync(mocklog,'utf8').trim().split('\n').filter(Boolean).map(JSON.parse);
  result.backend_calls=mockRows.filter(x=>x.kind==='run');
  assert(result.backend_calls.length===5,'Expected 2 direct + 3 bridged downstream calls');
  result.conclusion={external_real_server_executed:true,extra_fields_sent_through_external_server:true,extra_width_coercion_observed:true,controlled_downstream_results_changed:true,strict_before_rejects:true,auto_repair_restores_wot_transport:true,repair_preserves_typed_additionalProperties:true,production_Runware_API_confirmed:false};
  result.status='PASS';
}catch(e){result.status='FAIL';result.error=String(e.stack||e)}
finally{
  try{await Promise.race([mcp?.close(),new Promise(ok=>setTimeout(ok,3000))])}catch{}
  if(bridge)try{await new Promise(resolve=>bridge.close(resolve))}catch{}
  fs.writeFileSync(path.join(outdir,'result.json'),JSON.stringify(result,null,2)+'\n');
  fs.writeFileSync(path.join(outdir,'td_before.json'),JSON.stringify(result.before_td||{},null,2)+'\n');
  fs.writeFileSync(path.join(outdir,'td_after.json'),JSON.stringify(result.after_td||{},null,2)+'\n');
  console.log('CCNC_STAGE5_RESULT '+JSON.stringify({status:result.status,cases:result.cases.map(x=>({name:x.name,valid:x.valid,http_sent:x.http_sent,error:x.error,summary:x.value?.text?.slice(0,180)})),conclusion:result.conclusion,error:result.error,server_stderr:result.server_stderr}).slice(0,13000));
  if(result.status!=='PASS')process.exitCode=1;
}
