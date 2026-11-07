"""One-shot P5-B: third-party HTTP example -> real CNOE MCP -> two real consumer libraries.

No vendor/SDK source mutation, no remote API calls. Publisher/source evidence and
an explicit boundary-only test repair are contrasted through actual MCP stdio.
"""
from __future__ import annotations
import argparse
import asyncio
from collections import Counter
from contextlib import AsyncExitStack
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from threading import Thread
from types import SimpleNamespace

sys.path.insert(0,'/opt/risu/p4d')
from run_integration import ORIGINAL, TARGET, derive, exec_codegen, upstream_server
from consumer import (SourceErrorContractFailure,external_sdk_then_contract,
                      extract_consumer_text,verify_vendor_sdk_source)

ROOT=Path(__file__).resolve().parent
ORIGIN_PIN='0b0b0fdbb9d5821ec018a3db2777986a231eec37'
CODEGEN_PIN='8c2b065497cf32ecbb7cf7e28dad3a99c6706c3f'
LANGCHAIN_PIN='bb6a25a878527136dcb1a20507d5c20049427f96'
MEILI_SDK_PIN='6a6cc2596779a06f121ebb6d88dfa6943ee18d91'

def sha(data):return hashlib.sha256(data).hexdigest()
def jsonsafe(obj):return json.loads(json.dumps(obj,default=str,ensure_ascii=False))

async def run_through_pinned_consumers(server_py,base,mode,source_error,result_dir):
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    from langchain.mcp.tools import as_langchain_tool

    env={k:v for k,v in os.environ.items() if k in ('HOME','PATH','TMPDIR','LANG','LC_ALL','SYSTEMROOT')}
    env.update({'HOME':'/tmp','TMPDIR':'/tmp','API_BASE_URL':base,
                'MEILISEARCH_API_URL':base,'MEILISEARCH_TOKEN':'RISU_LOCAL_REPLAY_DUMMY',
                'PYTHONDONTWRITEBYTECODE':'1','PYTHONUNBUFFERED':'1',
                'PYTHONPATH':str(server_py.parent.parent),'PYTHON_DOTENV_DISABLED':'1',
                'P5B_ORIGINAL_HTTP_404':json.dumps(source_error,separators=(',',':'),ensure_ascii=False)})
    args=['-u','/opt/risu/p5b/proxy.py','--backend-python','/opt/cnoe/bin/python',
          '--server',str(server_py),'--mode',mode,'--wire-out',str(result_dir/(mode+'_wire.jsonl'))]
    class ActualMCPClient:
        server_info=None
        protocol_version=None
        def __init__(self):self.depth=0;self.session=None;self.stack=None
        async def __aenter__(self):
            if self.depth:
                self.depth+=1
                return self
            self.stack=AsyncExitStack()
            params=StdioServerParameters(command='/opt/langchain-venv/bin/python',args=args,env=env)
            streams=await self.stack.enter_async_context(stdio_client(params))
            self.session=await self.stack.enter_async_context(ClientSession(*streams))
            await self.session.initialize()
            self.depth=1
            self.protocol_version=getattr(self.session,'_protocol_version',None)
            return self
        async def __aexit__(self,*exc):
            self.depth-=1
            if self.depth==0:return await self.stack.__aexit__(*exc)
            return False
        async def call_tool(self,name,arguments,raise_on_error=False):
            raw=await self.session.call_tool(name,arguments)
            return SimpleNamespace(
                content=raw.content,
                is_error=bool(getattr(raw,'isError',getattr(raw,'is_error',False))),
                structured_content=getattr(raw,'structuredContent',getattr(raw,'structured_content',None)))
        async def list_tools(self):return await self.session.list_tools()
    async with ActualMCPClient() as client:
        listing=await client.list_tools()
        matches=[t for t in listing.tools if t.name=='get_index']
        if len(matches)!=1:raise RuntimeError('Original generated tool absent')
        schema=matches[0].inputSchema
        if 'path_indexUid' not in schema.get('required',[]):raise RuntimeError('Pinned generated input contract changed')
        tool=await as_langchain_tool(matches[0],client)
        observations=[]
        for label,value in [('success','movies'),('error','does-not-exist')]:
            args={'path_indexUid':value}
            raw=await client.call_tool('get_index',args,raise_on_error=False)
            msg=await tool.ainvoke({'type':'tool_call','name':'get_index','args':args,
                                   'id':f'risu-p5b-{mode}-{label}'})
            if type(msg).__name__!='ToolMessage':raise RuntimeError('Expected original LangChain ToolMessage')
            observations.append({'case':label,'arguments':args,
                 'raw_mcp':{'isError':raw.is_error,'structuredContent':jsonsafe(raw.structured_content),
                     'content':jsonsafe(raw.content)},
                 'langchain':{'type':type(msg).__name__,'status':getattr(msg,'status',None),
                     'content':jsonsafe(getattr(msg,'content',None)),
                     'artifact':jsonsafe(getattr(msg,'artifact',None))}})
        return observations,sorted(t.name for t in listing.tools)

def verify_wire(path,mode,src):
    frames=[json.loads(line) for line in path.read_text().splitlines()]
    expected_dirs={'client_to_proxy','backend_to_proxy','proxy_to_client','repair_event'}
    if not frames or {f['direction'] for f in frames}!=expected_dirs:raise RuntimeError('Incomplete actual wire evidence')
    requests=[x['frame'] for x in frames if x['direction']=='client_to_proxy' and x['frame'].get('method')=='tools/call']
    backend=[x['frame'] for x in frames if x['direction']=='backend_to_proxy' and x['frame'].get('id') in {r['id'] for r in requests}]
    emitted=[x['frame'] for x in frames if x['direction']=='proxy_to_client' and x['frame'].get('id') in {r['id'] for r in requests}]
    if len(requests)!=4 or len(backend)!=4 or len(emitted)!=4:raise RuntimeError('Expected four original MCP calls and matched frames')
    before={x['id']:x for x in backend};after={x['id']:x for x in emitted}
    error_ids={x['id'] for x in requests if x['params']['arguments']=={'path_indexUid':'does-not-exist'}}
    success_ids=set(before)-error_ids
    if len(error_ids)!=2 or len(success_ids)!=2:raise RuntimeError('Bad case coverage')
    for i in success_ids:
        if before[i]!=after[i]:raise RuntimeError('Repair unexpectedly mutated successful result')
    for i in error_ids:
        if src['code'] in json.dumps(before[i],sort_keys=True):raise RuntimeError('Original CNOE did not lose source code')
        if before[i].get('result',{}).get('isError',False):raise RuntimeError('Original CNOE status unexpectedly error')
        if mode=='passthrough':
            if before[i]!=after[i]:raise RuntimeError('Passthrough mutated original MCP wire')
        else:
            if not after[i]['result']['isError']:raise RuntimeError('Repair did not restore error flag')
            if after[i]['result']['structuredContent']!=src:raise RuntimeError('Repair did not preserve exact original body')
    flags=[x['frame']['changed'] for x in frames if x['direction']=='repair_event' and x['frame'].get('id') in before]
    if sum(flags)!=(2 if mode=='repair' else 0):raise RuntimeError('Unexpected source-backed repair count')
    return {'client_tool_calls':4,'source_lost_before_repair':2,'repair_events':sum(flags),
            'success_calls_unmodified':2,'wire_sha256':sha(path.read_bytes()),
            'recorded_frames':len(frames)}

async def run(output):
    if not ORIGINAL.is_file():raise RuntimeError('Pinned original Meilisearch OpenAPI absent')
    source=json.loads(ORIGINAL.read_text())
    op=source['paths'][TARGET]['get']
    examples={status:op['responses'][status]['content']['application/json']['example'] for status in ('200','404')}
    server,counts,invalid,original_404=upstream_server(examples['200'],examples['404'])
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    output.mkdir(parents=True,exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix='risu-p5b-',dir='/tmp') as temp:
            base=f'http://127.0.0.1:{server.server_port}'
            source_dir,_,_,bounded=derive(source,Path(temp),base)
            generated=exec_codegen(source_dir,Path(temp)/'generated')
            if counts or invalid:raise RuntimeError('Codegen unexpectedly contacted fixture')
            sdk_pin=verify_vendor_sdk_source()
            source_result=external_sdk_then_contract(json.dumps(original_404,ensure_ascii=False),'original_http_404')
            phase={}
            listed={}
            for mode in ('passthrough','repair'):
                phase[mode],listed[mode]=await run_through_pinned_consumers(generated,base,mode,original_404,output)
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
    if invalid:raise RuntimeError('Unexpected HTTP endpoint/method hit: '+repr(invalid))
    if dict(counts)!={'/indexes/movies':4,'/indexes/does-not-exist':4}:
        raise RuntimeError('Unexpected number of true HTTP GET calls: '+repr(counts))
    by={mode:{x['case']:x for x in items} for mode,items in phase.items()}
    baseline=by['passthrough']['error'];repaired=by['repair']['error']
    if baseline['langchain']['status']!='success' or baseline['raw_mcp']['isError']:
        raise RuntimeError('Original generated 404 status unexpected')
    if repaired['langchain']['status']!='error' or not repaired['raw_mcp']['isError']:
        raise RuntimeError('Repaired 404 status unexpected')
    if by['passthrough']['success']['raw_mcp']!=by['repair']['success']['raw_mcp']:
        raise RuntimeError('Success result mutated by adapter')
    if by['passthrough']['success']['langchain']['artifact']!=by['repair']['success']['langchain']['artifact']:
        raise RuntimeError('Success LangChain result mutated')
    failed=False;failure_detail=''
    try:
        external_sdk_then_contract(extract_consumer_text(baseline['langchain']['content']),'converted_mcp_langchain')
    except SourceErrorContractFailure as e:
        failed=True;failure_detail=str(e)
    if not failed:raise RuntimeError('Required broken consumer contract did not fail')
    fix_result=external_sdk_then_contract(extract_consumer_text(repaired['langchain']['content']),'producer_repaired_mcp_langchain')
    if fix_result['code']!='index_not_found':raise RuntimeError('Official original consumer still missing code')
    audits={mode:verify_wire(output/(mode+'_wire.jsonl'),mode,original_404) for mode in ('passthrough','repair')}
    report={'schema':'risu-p5b-original-converted-consumer-failure-repair-v1',
        'scope':'local replay of original Meilisearch official OpenAPI 404 example; CNOE generated server and LangChain & Meilisearch Python SDK real pinned code',
        'pins':{'meilisearch_openapi_git':ORIGIN_PIN,'cnoe_codegen_git':CODEGEN_PIN,
                'langchain_git':LANGCHAIN_PIN,'meilisearch_python_git':MEILI_SDK_PIN,
                'sdk_errors_blob_git_sha1':sdk_pin['git_blob']},
        'execution':{'original_source_mutated':False,'external_libraries_patched':False,
                'actual_cnoe_generated_mcp_stdio':True,'actual_langchain_as_langchain_tool':True,
                'original_official_meilisearch_sdk_parser':True,
                'test_adapter_modifies_mcp_wire_before_consumer':True,
                'repair_requires_original_http_source_body':True,
                'original_http_response_sha256':sha(json.dumps(original_404,sort_keys=True).encode()),
                'http_get_counts':dict(counts),'unexpected_http':invalid,
                'no_vendor_production_requests':True,'no_llm_run':True,'no_provider_security_claim':True},
        'original_consumer':{'status':'PASS','result':source_result},
        'converted_consumer':{'status':'EXPECTED_APPLICATION_CONTRACT_FAILURE','exception_type':'SourceErrorContractFailure',
            'reason':failure_detail},
        'repaired_consumer':{'status':'PASS','result':fix_result},
        'phase_results':phase,'tool_names':listed,'wire_audits':audits,
        'claim_boundary':('The official SDK parser alone does not raise an exception on missing code; '
            'the explicit fixed application contract raises SourceErrorContractFailure. '
            'The repair is a source-backed test-only MCP producer-boundary adapter, not a patch to CNOE. '
            'This is local replay of public examples, not a new production incident or upstream defect.')}
    (output/'full_chain.json').write_text(json.dumps(report,sort_keys=True,indent=2,ensure_ascii=False)+'\n')
    print('P5B_FULL_ORIGINAL_CONVERTED_FAILURE_REPAIR_PASS',json.dumps({
        'original':report['original_consumer']['status'],
        'converted':report['converted_consumer']['status'],
        'repaired':report['repaired_consumer']['status'],
        'wire':audits,'http_get_counts':dict(counts)},sort_keys=True),flush=True)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();asyncio.run(run(args.out))