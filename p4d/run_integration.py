"""Pinned Meilisearch OpenAPI -> unchanged CNOE generator -> real stdio MCP -> real LangChain consumer.

Runtime is offline; local 127.0.0.1 only; GET only. This does not connect to a
production Meilisearch instance. Unknown results are recorded as inconclusive.
"""
from __future__ import annotations
import argparse
import asyncio
from contextlib import AsyncExitStack
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import tempfile
from threading import Thread
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent
PROTOCOL = json.loads((ROOT/'FROZEN_PROTOCOL.json').read_text())
ORIGINAL = Path('/opt/meili-source/open-api.json')
TARGET = '/indexes/{indexUid}'


def sha(b): return sha256(b).hexdigest()


def ref_closure(value, schemas, into, visited=None):
    if visited is None: visited=set()
    if isinstance(value, dict):
        if '$ref' in value and value['$ref'].startswith('#/components/schemas/'):
            key=value['$ref'].split('/')[-1]
            if key not in visited:
                assert key in schemas, ('missing-source-schema',key)
                visited.add(key)
                into[key]=schemas[key]
                ref_closure(schemas[key],schemas,into,visited)
        for v in value.values(): ref_closure(v,schemas,into,visited)
    elif isinstance(value,list):
        for v in value: ref_closure(v,schemas,into,visited)


def derive(original, root, base):
    original_operation = original['paths'][TARGET]['get']
    assert original_operation['operationId']=='get_index'
    assert {200,401,404}==set(map(int,original_operation['responses']))
    good=original_operation['responses']['200']['content']['application/json']['example']
    missing=original_operation['responses']['404']['content']['application/json']['example']
    assert good['uid']=='movies'
    assert missing['code']=='index_not_found' and missing['type']=='invalid_request'
    assert 'link' in missing and 'message' in missing
    schemas={}
    ref_closure(original_operation,original['components']['schemas'],schemas)
    # Vendor authentication stays untouched in the original; local example-only copy
    # removes security because the replay server is loopback and has no API credentials.
    op=json.loads(json.dumps(original_operation))
    op.pop('security',None)
    bounded={
      'openapi': original['openapi'],
      'info': {'title':'meilisearch','version':original['info']['version']},
      'servers':[{'url':base}],
      'paths': {TARGET:{'get':op}},
      'components': {'schemas':schemas},
    }
    folder=root/'input';folder.mkdir()
    (folder/'openapi.json').write_text(json.dumps(bounded,indent=2)+'\n')
    (folder/'config.yaml').write_text(
       'title: meilisearch\n'
       'description: Read-only local replay of one public Meilisearch operation\n'
       'author: RISU bounded independent qualification\nversion: 0.0.0\nlicense: MIT\n'
       'python_version: 3.13\nheaders:\n  Accept: application/json\n'
       'poetry_dependencies: |\n'
       '  python = ">=3.13,<4.0"\n'
       '  httpx = ">=0.24.0"\n'
       '  python-dotenv = ">=1.0.0"\n'
       '  pydantic = ">=2.0.0"\n'
       '  mcp = ">=1.9.0"\n')
    return folder,good,missing,bounded


def upstream_server(good,missing):
    counts=Counter();invalid=[]
    # Build exact deterministic local response contracts from vendor examples.
    error=json.loads(json.dumps(missing));error['message']='Index `does-not-exist` not found.'
    good=json.loads(json.dumps(good))
    def normal(path):
        if path=='/indexes/movies': return 200,good
        if path=='/indexes/does-not-exist': return 404,error
        return None,None
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            status,body=normal(self.path)
            if status is None:
                invalid.append({'method':'GET','path':self.path})
                self.send_error(404);return
            counts[self.path]+=1
            blob=json.dumps(body,separators=(',',':')).encode()
            self.send_response(status)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(blob)))
            self.end_headers();self.wfile.write(blob)
        def do_POST(self):invalid.append({'method':'POST','path':self.path});self.send_error(405)
        def do_PUT(self):invalid.append({'method':'PUT','path':self.path});self.send_error(405)
        def do_DELETE(self):invalid.append({'method':'DELETE','path':self.path});self.send_error(405)
        def log_message(self,*args): pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    return server,counts,invalid,error


def exec_codegen(inp,out):
    command=['/opt/cnoe/bin/python','-m','openapi_mcp_codegen','--spec-file',str(inp/'openapi.json'),
              '--output-dir',str(out),'--log-level','warning']
    # Keep only basic process environment in runtime; no secrets passed to generator.
    env={k:v for k,v in os.environ.items() if k in ('HOME','PATH','TMPDIR','LANG','LC_ALL','SYSTEMROOT')}
    env['HOME']='/tmp';env['TMPDIR']='/tmp';env['PYTHON_DOTENV_DISABLED']='1'
    env['PATH']='/opt/cnoe/bin:'+env.get('PATH','')
    result=subprocess.run(command,cwd=inp,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=180)
    if result.returncode: raise RuntimeError('CNOE_GENERATION_FAILED:'+result.stderr[-1400:])
    generated=list(out.glob('mcp_*/server.py'))
    assert len(generated)==1,('GENERATED_SERVER_ENTRYPOINT_UNEXPECTED',[str(p) for p in generated])
    return generated[0]


def error_obj(actual):
    """Never synthesize response; just summarize authentic installed SDK object."""
    return {'isError':bool(getattr(actual,'isError',getattr(actual,'is_error',False))),
            'structuredContent':getattr(actual,'structuredContent',getattr(actual,'structured_content',None)),
            'content':[{'type':getattr(x,'type',None),'text':getattr(x,'text',None)} for x in actual.content]}


def text_or_none(value):
    if isinstance(value,str):return value
    return json.dumps(value,default=str,ensure_ascii=False)


async def one_chain(server_py,base):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from langchain.mcp.tools import as_langchain_tool
    from types import SimpleNamespace
    server_env={k:v for k,v in os.environ.items() if k in ('HOME','PATH','TMPDIR','LANG','LC_ALL','SYSTEMROOT')}
    server_env.update({'HOME':'/tmp','TMPDIR':'/tmp','API_BASE_URL':base,'MEILISEARCH_API_URL':base,
                       'PYTHONDONTWRITEBYTECODE':'1','PYTHONUNBUFFERED':'1',
                       'PYTHONPATH':str(server_py.parent.parent),'PYTHON_DOTENV_DISABLED':'1'})
    class ActualMCPClient:
        server_info=None
        protocol_version=None
        def __init__(self):self.session=None;self.stack=None;self.depth=0
        async def __aenter__(self):
            if self.depth:
                self.depth+=1
                return self
            self.stack=AsyncExitStack()
            params=StdioServerParameters(command='/opt/cnoe/bin/python',args=['-u',str(server_py)],env=server_env)
            streams=await self.stack.enter_async_context(stdio_client(params))
            self.session=await self.stack.enter_async_context(ClientSession(*streams))
            await self.session.initialize()
            self.protocol_version=getattr(self.session,'_protocol_version',None)
            self.depth=1
            return self
        async def __aexit__(self,*args):
            self.depth-=1
            if self.depth==0:
                return await self.stack.__aexit__(*args)
            return False
        async def list_tools(self):return await self.session.list_tools()
        async def call_tool(self,name,arguments,raise_on_error=False):
            result=await self.session.call_tool(name,arguments)
            # LangChain consumes FastMCP's snake-case fields; original result is
            # otherwise passed through unchanged from actual on-wire SDK session.
            return SimpleNamespace(content=result.content,
                is_error=bool(getattr(result,'isError',getattr(result,'is_error',False))),
                structured_content=getattr(result,'structuredContent',getattr(result,'structured_content',None)))
    async with ActualMCPClient() as client:
        listed=await client.list_tools()
        matches=[t for t in listed.tools if t.name=='get_index']
        assert len(matches)==1, ('GENERATED_TOOL_ABSENT',[t.name for t in listed.tools])
        tool=await as_langchain_tool(matches[0],client)
        out=[]
        for label,identifier in [('success','movies'),('error','does-not-exist')]:
            arguments={'indexUid':identifier}
            raw=await client.call_tool('get_index',arguments,raise_on_error=False)
            raw_record={'isError':raw.is_error,'structuredContent':raw.structured_content,
                        'content':[{'type':getattr(x,'type',None),'text':getattr(x,'text',None)} for x in raw.content]}
            result=await tool.ainvoke({'type':'tool_call','id':f'p4d-{label}',
                    'name':'get_index','args':arguments})
            record={'case':label,'arguments':arguments,'raw_mcp':raw_record,
                    'consumer':{'type':type(result).__name__,'status':getattr(result,'status',None),
                                'artifact':getattr(result,'artifact',None),
                                'content':getattr(result,'content',None)}}
            out.append(record)
        return out, [t.name for t in listed.tools]


def make_report(original,good,missing,bounded,results,tools,counts,invalid,observed_error):
    by={v['case']:v for v in results}
    assert set(by)=={'success','error'}
    assert not invalid, ('UNEXPECTED_HTTP_REQUESTS',invalid)
    assert counts['/indexes/movies']==2 and counts['/indexes/does-not-exist']==2, counts
    # Contrasts intentionally do not assume a defect or absence of defect.
    mcp=by['error']['raw_mcp'];consumer=by['error']['consumer']
    upstream_error_code=observed_error['code']
    raw_json=json.dumps(mcp,ensure_ascii=False,default=str)
    model_json=json.dumps({'artifact':consumer['artifact'],'content':consumer['content']},ensure_ascii=False,default=str)
    raw_code=upstream_error_code in raw_json
    model_code=upstream_error_code in model_json
    if not isinstance(consumer['content'],(list,str)) and not isinstance(consumer['artifact'],(dict,type(None))):
        outcome='INCONCLUSIVE_DIAGNOSTIC'
    elif model_code:outcome='EXTERNAL_FULL_CHAIN_CONFIRMED_NO_LOSS'
    else:outcome='EXTERNAL_FULL_CHAIN_CONFIRMED_WITH_LOSS'
    report={
      'schema':'risu-p4d-independent-full-chain-v1',
      'outcome':outcome,
      'pins':PROTOCOL,
      'execution':{'source_kind':'ORIGINAL_PUBLIC_VENDOR_OPENAPI_WITH_LOCAL_OPERATION_DERIVATION',
       'converter_kind':'ORIGINAL_CNOE_SOURCE_CODE_GENERATION',
       'transport':'ACTUAL_STDIO_MCP_CLIENT_SESSION',
       'consumer_kind':'ACTUAL_LANGCHAIN_MCP_AS_LANGCHAIN_TOOL_AND_TOOLMESSAGE',
       'production_service_touched':False,'external_llm_touched':False,
       'local_http_gets':dict(counts),'unexpected_http':invalid,'listed_tools':tools},
      'checks':{'source_error_code':upstream_error_code,
        'mcp_contains_error_code':raw_code,
        'langchain_model_or_artifact_contains_error_code':model_code,
        'http_error_was_recognized_by_mcp':mcp['isError'],
        'langchain_classified_error':consumer['status']=='error',
        'source_original_sha256':sha(ORIGINAL.read_bytes()),
        'bounded_spec_sha256':sha(json.dumps(bounded,sort_keys=True).encode())},
      'case_results':results,
      'claim_boundary':'Original Meilisearch public spec version 1.15.2 and local response-example replay; no live vendor traffic, no undisclosed bug allegation, no production user impact estimate'
    }
    return report


async def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    original=json.loads(ORIGINAL.read_text())
    operation=original['paths'][TARGET]['get']
    examples={name:operation['responses'][name]['content']['application/json']['example'] for name in ('200','404')}
    server,counts,invalid,observed_error=upstream_server(examples['200'],examples['404'])
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
      with tempfile.TemporaryDirectory(prefix='risu-p4d-',dir='/tmp') as t:
        inp,good,missing,bounded=derive(original,Path(t),base)
        generated=exec_codegen(inp,Path(t)/'generated')
        assert not counts and not invalid,'Generation unexpectedly accessed API'
        results,tools=await one_chain(generated,base)
        report=make_report(original,good,missing,bounded,results,tools,counts,invalid,observed_error)
    finally:
      server.shutdown();server.server_close();thread.join(timeout=5)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2,sort_keys=True,default=str)+'\n')
    print('RISU_P4D_RESULT',report['outcome'],json.dumps(report['checks'],sort_keys=True),flush=True)

if __name__=='__main__':
    asyncio.run(main())
