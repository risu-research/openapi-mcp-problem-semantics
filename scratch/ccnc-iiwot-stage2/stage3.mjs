import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import assert from 'node:assert/strict';
import Ajv2020 from 'ajv/dist/2020.js';
import {Client} from '@modelcontextprotocol/sdk/client/index.js';
import {StdioClientTransport} from '@modelcontextprotocol/sdk/client/stdio.js';
import corePkg from '@node-wot/core';
import bindingPkg from '@node-wot/binding-http';
const {Servient}=corePkg,{HttpClientFactory}=bindingPkg;
const PREFIX='ccnc:additionalProperties', NS='urn:risu:iiwot:experimental-extension:';
const H=['type','title','description','default','minimum','maximum','minLength','maxLength','minItems','maxItems','pattern','enum','const','format'];
const has=(x,k)=>Object.prototype.hasOwnProperty.call(x||{},k);
const clone=x=>JSON.parse(JSON.stringify(x));
const result={status:'INCOMPLETE',method:'experimental opt-in TD Context Extension plus independent Ajv 2020 validator and node-wot HTTP Consumer',source:'@modelcontextprotocol/server-filesystem@1.0.0',cases:[],http_wire:[],direct_mcp:[],nested_controls:[],security:'read-only temporary directory',limits:['No claim that stock node-wot enforces TD input rules','No claim of W3C certification of experimental extension','No real-world functional impact from filesystem extra arguments']};
let client,bridge,servient;
const dir=fs.mkdtempSync(path.join(os.tmpdir(),'ccnc-stage3-'));
const file=path.join(dir,'readme.txt');fs.writeFileSync(file,'CCNC_STAGE3_READONLY_REFERENCE\n');
function tdCore(s){
  if(!s||typeof s!=='object'||Array.isArray(s))throw Error('unsupported schema form');
  for(const k of Object.keys(s))if(!new Set([...H,'properties','required','items','additionalProperties','$schema']).has(k))throw Error('unsupported source rule '+k);
  const o={};
  for(const k of H)if(has(s,k))o[k]=clone(s[k]);
  if(has(s,'required'))o.required=clone(s.required);
  if(has(s,'properties'))o.properties=Object.fromEntries(Object.entries(s.properties).map(([k,v])=>[k,tdCore(v)]));
  if(has(s,'items'))o.items=tdCore(s.items);
  return o;
}
function autoRepair(tdInput, source){
  const out=clone(tdInput);let count=0;
  function go(target,origin,at){
    if(origin.type==='object'){
      if(!has(origin,'additionalProperties')||origin.additionalProperties===true){target[PREFIX]=true;count++;}
      else if(origin.additionalProperties===false){} // remains closed
      else throw Error('schema-valued additionalProperties not supported in this stage: '+at);
      for(const [k,v] of Object.entries(origin.properties||{}))go(target.properties[k],v,at+'.'+k);
    }
    if(origin.type==='array'&&origin.items)go(target.items,origin.items,at+'[]');
  }
  go(out,source,'$');
  return {input:out,count};
}
function policyFromTD(t,respectExtension){
  const s={};for(const k of H)if(has(t,k))s[k]=clone(t[k]);
  if(has(t,'required'))s.required=clone(t.required);
  if(has(t,'properties'))s.properties=Object.fromEntries(Object.entries(t.properties).map(([k,v])=>[k,policyFromTD(v,respectExtension)]));
  if(has(t,'items'))s.items=policyFromTD(t.items,respectExtension);
  if(t.type==='object')s.additionalProperties=respectExtension&&t[PREFIX]===true;
  return s;
}
const ajv=new Ajv2020({allErrors:true,strict:false});
const check=(schema,args)=>{const fn=ajv.compile(schema);return {valid:!!fn(args),errors:fn.errors||[]}};
const reply=(res,code,obj)=>{const raw=Buffer.from(JSON.stringify(obj));res.writeHead(code,{'content-type':'application/json','content-length':raw.length});res.end(raw)};
function buildTD(origin,input,port){
  return {'@context':['https://www.w3.org/2022/wot/td/v1.1',{htv:'http://www.w3.org/2011/http#',ccnc:NS}],id:'urn:risu:ccnc:stage3',title:'CCNC read-only MCP filesystem bridge',securityDefinitions:{nosec_sc:{scheme:'nosec'}},security:'nosec_sc',actions:{readFile:{input,output:{type:'object',properties:{isError:{type:'boolean'},text:{type:'string'}},required:['isError','text']},forms:[{href:origin+'/action',op:'invokeaction',contentType:'application/json','htv:methodName':'POST'}]}}};
}
async function callSource(args){
 const response=await client.callTool({name:result.tool,arguments:args});
 const r={isError:!!response.isError,text:response.content.filter(c=>c.type==='text').map(c=>c.text).join('\n')};
 result.direct_mcp.push({args:clone(args),response:r});return r;
}
async function consumerCase(thing,name,td,args,mode){
  const policy=policyFromTD(td.actions.readFile.input,mode==='repaired');
  const validation=check(policy,args);
  const before=result.http_wire.length;
  let response=null,error=null;
  if(validation.valid){
    try{const out=await thing.invokeAction('readFile',args);response=await out.value()}
    catch(e){error=String(e)}
  }
  const row={name,mode,valid:validation.valid,errors:validation.errors.map(e=>({keyword:e.keyword,instancePath:e.instancePath,params:e.params})),http_sent:result.http_wire.length-before,response,error};
  result.cases.push(row);return row;
}
try{
  client=new Client({name:'ccnc-stage3-independent-client',version:'1.0.0'});
  await client.connect(new StdioClientTransport({command:path.resolve('node_modules/.bin/mcp-server-filesystem'),args:['--read-only',dir]}));
  const list=await client.listTools();
  const tool=list.tools.find(t=>t.name==='read_text_file');assert(tool,'Official read_text_file missing');
  result.tool=tool.name;result.source_schema=tool.inputSchema;
  assert(!has(tool.inputSchema,'additionalProperties'),'Expected open root source schema for this frozen server');
  const normal={path:file};const extra={path:file,ccnc_extra:'not-declared'};
  result.source_schema_normal=check(tool.inputSchema,normal);
  result.source_schema_extra=check(tool.inputSchema,extra);
  assert(result.source_schema_normal.valid&&result.source_schema_extra.valid,'Source schema does not accept tested inputs');
  result.direct_normal=await callSource(normal);result.direct_extra=await callSource(extra);
  assert(!result.direct_extra.isError,'Reference server rejected unknown field');
  bridge=http.createServer(async(req,res)=>{
    if(req.method!=='POST'||req.url!=='/action')return reply(res,404,{error:'missing'});
    const buffers=[];for await(const buf of req)buffers.push(buf);
    const wire=Buffer.concat(buffers).toString('utf8');
    let args;try{args=JSON.parse(wire)}catch{return reply(res,400,{error:'bad JSON'})}
    const rec={raw_json:wire,args};
    result.http_wire.push(rec);
    try{rec.response=await callSource(args);reply(res,rec.response.isError?422:200,rec.response)}
    catch(e){rec.error=String(e);reply(res,500,{error:rec.error})}
  });
  await new Promise(resolve=>bridge.listen(0,'127.0.0.1',resolve));
  const origin='http://127.0.0.1:'+bridge.address().port;
  const baseInput=tdCore(tool.inputSchema),repair=autoRepair(baseInput,tool.inputSchema);
  result.repair_count=repair.count;
  result.before_td=buildTD(origin,baseInput);
  result.after_td=buildTD(origin,repair.input);
  servient=new Servient();servient.addClientFactory(new HttpClientFactory());
  const WoT=await servient.start();
  const before=await WoT.consume(result.before_td),after=await WoT.consume(result.after_td);
  const cases=[];
  cases.push(await consumerCase(before,'strict_before_normal',result.before_td,normal,'baseline'));
  cases.push(await consumerCase(before,'strict_before_extra',result.before_td,extra,'baseline'));
  cases.push(await consumerCase(after,'strict_after_extra',result.after_td,extra,'repaired'));
  cases.push(await consumerCase(after,'strict_after_normal',result.after_td,normal,'repaired'));
  cases.push(await consumerCase(after,'strict_after_bad_type',result.after_td,{path:42,ccnc_extra:'not-declared'},'repaired'));
  cases.push(await consumerCase(after,'strict_after_missing_required',result.after_td,{ccnc_extra:'not-declared'},'repaired'));
  // Stock node-wot baseline is intentionally independent of the strict validator.
  const c=result.http_wire.length;
  const raw=await before.invokeAction('readFile',extra);
  result.raw_nodewot={http_sent:result.http_wire.length-c,response:await raw.value()};
  const nested={type:'object',additionalProperties:false,properties:{options:{type:'object',properties:{base:{type:'number'}},required:['base']}},required:['options']};
  const nb=tdCore(nested),nr=autoRepair(nb,nested);
  const scenarios=[
   {name:'nested_before_open_child',args:{options:{base:2,boost:3}},expectedBefore:false,expectedAfter:true},
   {name:'nested_closed_root',args:{options:{base:2},outside:1},expectedBefore:false,expectedAfter:false},
   {name:'nested_invalid_type',args:{options:{base:'x',boost:3}},expectedBefore:false,expectedAfter:false},
   {name:'nested_normal',args:{options:{base:2}},expectedBefore:true,expectedAfter:true}
  ];
  for(const row of scenarios){
    const lhs=check(policyFromTD(nb,false),row.args).valid, rhs=check(policyFromTD(nr.input,true),row.args).valid;
    const src=check(nested,row.args).valid;
    assert(lhs===row.expectedBefore&&rhs===row.expectedAfter&&rhs===src,row.name+' mismatch');
    result.nested_controls.push({name:row.name,before:lhs,after:rhs,source:src});
  }
  result.nested_extension_count=nr.count;
  assert(cases[0].http_sent===1&&!cases[0].error);
  assert(!cases[1].valid&&cases[1].http_sent===0);
  assert(cases[2].valid&&cases[2].http_sent===1&&!cases[2].error);
  assert(cases[3].valid&&cases[3].http_sent===1);
  assert(!cases[4].valid&&cases[4].http_sent===0);
  assert(!cases[5].valid&&cases[5].http_sent===0);
  assert(result.raw_nodewot.http_sent===1);
  assert(result.http_wire.some(r=>r.args.ccnc_extra==='not-declared'));
  result.conclusion={
    original_source_accepts_extra:true,
    baseline_strict_blocks_before_http:true,
    auto_repaired_strict_sends_extra:true,
    repaired_type_required_guards_remain:true,
    stock_nodewot_forwards_extra:true,
    external_server_extra_changes_result:result.direct_normal.text!==result.direct_extra.text,
    experimental_extension_supported_by_opt_in_client_only:true
  };
  result.status='PASS';
}catch(e){result.status='FAIL';result.error=String(e?.stack||e)}
finally{
  try{await client?.close()}catch{}
  if(bridge)try{await new Promise(resolve=>bridge.close(resolve))}catch{}
  fs.rmSync(dir,{recursive:true,force:true});
  fs.mkdirSync('results-stage3',{recursive:true});
  fs.writeFileSync('results-stage3/stage3.json',JSON.stringify(result,null,2)+'\n');
  console.log('CCNC_STAGE3_RESULT '+JSON.stringify({status:result.status,tool:result.tool,cases:result.cases?.map(x=>({name:x.name,valid:x.valid,http_sent:x.http_sent,response:x.response,error:x.error})),conclusion:result.conclusion,nested_controls:result.nested_controls,error:result.error}));
  if(result.status!=='PASS')process.exitCode=1;
}
