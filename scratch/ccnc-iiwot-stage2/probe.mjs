import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import corePkg from '@node-wot/core';
import httpPkg from '@node-wot/binding-http';
const {Servient}=corePkg;
const {HttpClientFactory}=httpPkg;

const dir=fs.mkdtempSync(path.join(os.tmpdir(),'ccnc-readonly-'));
const file=path.join(dir,'hello.txt');fs.writeFileSync(file,'CCNC_REFERENCE_CONTENT\n');
let server, client;
const result={status:'INCOMPLETE',source:'@modelcontextprotocol/server-filesystem',consumer:'@node-wot/core + @node-wot/binding-http',tool:null,tool_schema:null,td:null,cases:[],http_wire:[],mcp_results:[],versions:{}};
const respond=(res,code,body)=>{const v=Buffer.from(JSON.stringify(body));res.writeHead(code,{'content-type':'application/json','content-length':v.length});res.end(v)};
try{
  const exe=path.resolve('node_modules/.bin/mcp-server-filesystem');
  client=new Client({name:'ccnc-stage2-client',version:'1.0.0'});
  await client.connect(new StdioClientTransport({command:exe,args:['--read-only',dir]}));
  const tools=await client.listTools();
  const tool=tools.tools.find(x=>x.name==='read_text_file')||tools.tools.find(x=>x.name==='read_file');
  if(!tool)throw Error('Reference read tool not found: '+tools.tools.map(x=>x.name));
  result.tool=tool.name;result.tool_schema=tool.inputSchema;
  const call=async args=>{
    const r=await client.callTool({name:tool.name,arguments:args});
    const data={isError:!!r.isError,text:(r.content||[]).filter(c=>c.type==='text').map(c=>c.text).join('\n').slice(0,1800)};
    result.mcp_results.push({arguments:args,response:data});return data;
  };
  result.cases.push({case:'mcp_direct_described',result:await call({path:file})});
  result.cases.push({case:'mcp_direct_extra',result:await call({path:file,ccnc_undeclared_probe:'extra'})});
  server=http.createServer(async(req,res)=>{
    if(req.url==='/td')return respond(res,200,result.td);
    if(req.url!=='/action' || req.method!=='POST')return respond(res,404,{error:'unknown'});
    const parts=[];for await(const p of req)parts.push(p);
    const body=Buffer.concat(parts).toString('utf8');
    let args;try{args=JSON.parse(body)}catch{return respond(res,400,{error:'bad-json'})}
    const record={body,arguments:args};result.http_wire.push(record);
    try{const r=await call(args);record.response=r;respond(res,r.isError?422:200,r)}
    catch(e){record.error=String(e);respond(res,500,{error:String(e)})}
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const origin='http://127.0.0.1:'+server.address().port;
  const allowed=['type','description','minimum','maximum','minLength','maxLength','enum','format','default'];
  const p=Object.fromEntries(Object.entries(tool.inputSchema.properties||{}).map(([k,v])=>[k,Object.fromEntries(allowed.filter(s=>Object.hasOwn(v,s)).map(s=>[s,v[s]]))]));
  result.td={'@context':['https://www.w3.org/2022/wot/td/v1.1',{'htv':'http://www.w3.org/2011/http#'}],id:'urn:risu:stage2:filesystem',title:'Filesystem tool bridge',securityDefinitions:{nosec_sc:{scheme:'nosec'}},security:'nosec_sc',actions:{readFile:{input:{type:'object',properties:p,required:tool.inputSchema.required||[]},forms:[{href:origin+'/action',op:'invokeaction',contentType:'application/json','htv:methodName':'POST'}]}}};
  const servient=new Servient();servient.addClientFactory(new HttpClientFactory());
  const WoT=await servient.start(),td=await WoT.requestThingDescription(origin+'/td'),thing=await WoT.consume(td);
  for(const [which,args] of [['described',{path:file}],['undeclared_extra',{path:file,ccnc_undeclared_probe:'extra'}]]){
    const prior=result.http_wire.length;
    try{const interaction=await thing.invokeAction('readFile',args);result.cases.push({case:'node_wot_'+which,sent:result.http_wire.length-prior,ok:true,value:await interaction.value()})}
    catch(e){result.cases.push({case:'node_wot_'+which,sent:result.http_wire.length-prior,ok:false,error:String(e)})}
  }
  const c=result.cases.find(x=>x.case==='node_wot_undeclared_extra');
  const extraWire=result.http_wire.find(x=>Object.hasOwn(x.arguments,'ccnc_undeclared_probe'));
  result.conclusion={node_wot_behavior:c.sent===0?'BLOCKED_BEFORE_WIRE':extraWire?'FORWARDED_EXTRA':'SENT_WITHOUT_EXTRA',direct_mcp_extra_equal:result.cases[0].result.text===result.cases[1].result.text};
  result.status='COMPLETE';
}catch(e){result.status='ERROR';result.error=String(e.stack||e)}
finally{try{await client?.close()}catch{}try{if(server)await new Promise(resolve=>server.close(resolve))}catch{}fs.rmSync(dir,{recursive:true,force:true});fs.mkdirSync('results',{recursive:true});fs.writeFileSync('results/independent.json',JSON.stringify(result,null,2)+'\n');console.log('CCNC_STAGE2_RESULT '+JSON.stringify({status:result.status,tool:result.tool,cases:result.cases,conclusion:result.conclusion,error:result.error}));if(result.status!=='COMPLETE')process.exitCode=1;}
