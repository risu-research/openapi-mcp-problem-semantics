import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import Ajv2020 from 'ajv/dist/2020.js';
import corePkg from '@node-wot/core';
import httpPkg from '@node-wot/binding-http';
const {Servient}=corePkg;
const {HttpClientFactory}=httpPkg;

const result = {
  status:'INCOMPLETE',
  title:'External claude-mem 12.0.0 unknown-key functional forwarding',
  external_server:'claude-mem@12.0.0 (UNMODIFIED published MCP executable)',
  downstream:'controlled mock HTTP worker with three synthetic memory rows',
  inference_limit:'Proves actual external MCP tool forwards undeclared keys and controlled worker response differs; not evidence of production claude-mem database behavior.',
  worker_wire:[],bridge_wire:[],mcp_calls:[],cases:[],source_schema:null,td_before:null,td_after:null
};
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'ccnc-clmem-'));
fs.writeFileSync(path.join(tmp,'settings.json'),JSON.stringify({CLAUDE_MEM_WORKER_PORT:'37777',CLAUDE_MEM_WORKER_HOST:'127.0.0.1'}));
const rows=[
  {id:1,project:'example',body:'amber-signal alpha document'},
  {id:2,project:'example',body:'blue-signal beta document'},
  {id:3,project:'example',body:'amber-signal gamma document'}
];
let worker,bridge,client,servient;
const respond=(res,status,obj)=>{
  const buf=Buffer.from(JSON.stringify(obj));
  res.writeHead(status,{'content-type':'application/json','content-length':buf.length});
  res.end(buf);
};
const awaitListen=srv=>new Promise((ok,err)=>srv.once('error',err).listen(0,'127.0.0.1',ok));
const ajv=new Ajv2020({strict:false,allErrors:true});
function validate(td,extra){
  const s=structuredClone(td.actions.searchMemory.input);
  const open=extra && s['ccnc:additionalProperties'] === true;
  delete s['ccnc:additionalProperties'];
  s.additionalProperties=open;
  const fn=ajv.compile(s);
  return {valid:fn(extra===null?{}:extra),errors:fn.errors||[]};
}
async function mcpCall(args){
  const response=await client.callTool({name:'search',arguments:args});
  const entry={args,response:{isError:!!response.isError,content:(response.content||[]).filter(x=>x.type==='text').map(x=>x.text)}};
  result.mcp_calls.push(entry);
  return entry;
}
async function consumerCall(thing,td,args,repair,label){
  const schema=structuredClone(td.actions.searchMemory.input);
  const enabled=repair && schema['ccnc:additionalProperties']===true;
  delete schema['ccnc:additionalProperties'];
  schema.additionalProperties=enabled;
  const predicate=ajv.compile(schema);
  const accepted=!!predicate(args),n=result.bridge_wire.length;
  let answer=null,error=null;
  if(accepted)try{const r=await thing.invokeAction('searchMemory',args);answer=await r.value()}
  catch(e){error=String(e)}
  const rec={label,accepted,http_sent:result.bridge_wire.length-n,answer,error};
  result.cases.push(rec);return rec;
}
try{
  worker=http.createServer((req,res)=>{
    const url=new URL(req.url,'http://localhost');
    const params=Object.fromEntries(url.searchParams);
    result.worker_wire.push({method:req.method,path:url.pathname,params});
    if(url.pathname==='/api/health')return respond(res,200,{status:'ok'});
    if(url.pathname!=='/api/search')return respond(res,404,{message:'Unknown endpoint'});
    const q=(params.query||'').trim().toLowerCase();
    const matching=rows.filter(x=>!q||x.body.includes(q));
    const cap=params.limit?Math.max(0,Math.min(20,Number(params.limit))):20;
    const selected=matching.slice(0,cap);
    return respond(res,200,{content:[{type:'text',text:JSON.stringify({query:q,returned: selected.map(x=>x.id),count:selected.length})}]});
  });
  await new Promise((ok,err)=>worker.once('error',err).listen(37777,'127.0.0.1',ok));
  const root=path.resolve('node_modules/claude-mem');
  const candidates=['plugin/scripts/mcp-server.cjs','scripts/mcp-server.cjs'];
  const serverPath=candidates.map(x=>path.join(root,x)).find(x=>fs.existsSync(x));
  assert(serverPath,'Published claude-mem MCP executable not present');
  result.installed_server_path=path.relative(path.resolve('.'),serverPath);
  client=new Client({name:'ccnc-independent-boundary-probe',version:'1.0.0'});
  const transport=new StdioClientTransport({command:'bun',args:[serverPath],stderr:'pipe',env:{...process.env,CLAUDE_MEM_DATA_DIR:tmp,CLAUDE_MEM_WORKER_PORT:'37777',CLAUDE_MEM_WORKER_HOST:'127.0.0.1'}});
  result.server_stderr='';
  transport.stderr?.on('data',x=>{result.server_stderr=(result.server_stderr+String(x)).slice(-12000)});
  await Promise.race([client.connect(transport),new Promise((_,reject)=>setTimeout(()=>reject(new Error('MCP handshake timeout after 12 seconds')),12000))]);
  const listed=await client.listTools();
  const tool=listed.tools.find(x=>x.name==='search');
  assert(tool,'Expected search tool missing');
  result.source_schema=tool.inputSchema;
  assert.equal(tool.inputSchema.type,'object');
  assert.deepEqual(tool.inputSchema.properties,{},'Version v12 expected empty advertised properties');
  assert.equal(tool.inputSchema.additionalProperties,true);
  const q=(text)=>({query:text});
  const zero=await mcpCall({});
  const amber=await mcpCall(q('amber'));
  const blue=await mcpCall(q('blue'));
  const limited=await mcpCall({query:'amber',limit:1});
  assert(!zero.response.isError&&!amber.response.isError&&!blue.response.isError&&!limited.response.isError,'MCP call failed');
  assert(amber.response.content.join('')!==blue.response.content.join(''),'Undeclared query did not change MCP result');
  assert(amber.response.content.join('')!==limited.response.content.join(''),'Undeclared limit did not change MCP result');
  assert(result.worker_wire.some(x=>x.path==='/api/search'&&x.params.query==='amber'));
  assert(result.worker_wire.some(x=>x.path==='/api/search'&&x.params.limit==='1'));
  bridge=http.createServer(async(req,res)=>{
    if(req.method!=='POST'||req.url!=='/action')return respond(res,404,{message:'missing'});
    const body=[];for await(const x of req)body.push(x);
    const raw=Buffer.concat(body).toString();
    let args;try{args=JSON.parse(raw)}catch{return respond(res,400,{message:'JSON expected'})}
    const record={raw,args};result.bridge_wire.push(record);
    try{
      const r=await mcpCall(args);
      record.result=r.response;
      const first=r.response.content[0]||'';
      respond(res,r.response.isError?422:200,{isError:r.response.isError,text:first});
    }catch(e){record.error=String(e);respond(res,500,{error:String(e)})}
  });
  await awaitListen(bridge);
  const origin='http://127.0.0.1:'+bridge.address().port;
  const makeTd=repair=>({
    '@context':['https://www.w3.org/2022/wot/td/v1.1',{htv:'http://www.w3.org/2011/http#',ccnc:'urn:risu:iiwot:experimental-open-field:'}],
    id:'urn:risu:iiwot:claude-mem-v12-search',
    title:'Historical Claude-mem search bridge (controlled worker)',
    securityDefinitions:{nosec_sc:{scheme:'nosec'}},security:'nosec_sc',
    actions:{searchMemory:{
      input:{type:'object',properties:{},...(repair?{'ccnc:additionalProperties':true}:{})},
      output:{type:'object',properties:{isError:{type:'boolean'},text:{type:'string'}},required:['isError','text']},
      forms:[{href:origin+'/action',op:'invokeaction',contentType:'application/json','htv:methodName':'POST'}]
    }}
  });
  result.td_before=makeTd(false);result.td_after=makeTd(true);
  servient=new Servient();servient.addClientFactory(new HttpClientFactory());
  const WoT=await servient.start();
  const before=await WoT.consume(result.td_before),after=await WoT.consume(result.td_after);
  const c1=await consumerCall(before,result.td_before,{query:'amber'},false,'strict_before_unknown_query');
  const c2=await consumerCall(after,result.td_after,{query:'amber'},true,'strict_after_amber');
  const c3=await consumerCall(after,result.td_after,{query:'blue'},true,'strict_after_blue');
  const c4=await consumerCall(after,result.td_after,{query:'amber',limit:1},true,'strict_after_limit_1');
  assert(!c1.accepted&&c1.http_sent===0);
  assert(c2.accepted&&c2.http_sent===1&&!c2.error);
  assert(c3.accepted&&c3.http_sent===1&&!c3.error);
  assert(c4.accepted&&c4.http_sent===1&&!c4.error);
  assert(c2.answer.text!==c3.answer.text);
  assert(c2.answer.text!==c4.answer.text);
  const closedSource={type:'object',properties:{path:{type:'string'}},required:['path'],additionalProperties:false};
  const closedProbe=ajv.compile(closedSource);
  result.closed_control={valid:closedProbe({path:'/test'}),rejects_extra:!closedProbe({path:'/test',query:'amber'})};
  assert(result.closed_control.valid&&result.closed_control.rejects_extra);
  result.observed={
    real_external_mcp_package:true,
    package_unmodified:true,
    search_query_not_declared:true,
    unknown_query_affects_worker_request:true,
    unknown_limit_affects_worker_request:true,
    controlled_worker_output_changes:true,
    strict_unrepaired_blocks:true,
    repaired_opt_in_transmits:true,
    actual_claude_mem_worker_tested:false,
    actual_external_service_business_effect_tested:false
  };
  result.status='PASS';
}catch(e){result.status='FAIL';result.error=String(e.stack||e)}
finally{
  try{await Promise.race([client?.close(),new Promise(ok=>setTimeout(ok,2000))])}catch{}
  if(bridge)try{await new Promise(r=>bridge.close(r))}catch{}
  if(worker)try{await new Promise(r=>worker.close(r))}catch{}
  try {
  const dirs=[path.join(tmp,'logs'),path.join(os.homedir(),'.claude-mem','logs')];
  result.server_log_tails=[];
  for(const d of dirs)if(fs.existsSync(d)){for(const fn of fs.readdirSync(d).slice(-8)){
    const fp=path.join(d,fn);if(fs.statSync(fp).isFile())result.server_log_tails.push({file:fp,content:fs.readFileSync(fp,'utf8').slice(-11000)});
  }}
}catch(e){result.log_read_error=String(e)}
fs.rmSync(tmp,{recursive:true,force:true});
  fs.mkdirSync('results-stage4',{recursive:true});
  fs.writeFileSync('results-stage4/observations.json',JSON.stringify(result,null,2)+'\n');
  console.log('CCNC_STAGE4_RESULT '+JSON.stringify({status:result.status,cases:result.cases,observed:result.observed,source_schema:result.source_schema,error:result.error,server_stderr:result.server_stderr,server_log_tails:result.server_log_tails}).slice(0,12000));
  if(result.status!=='PASS')process.exitCode=1;
}
