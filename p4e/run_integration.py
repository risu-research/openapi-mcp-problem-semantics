"""P4-E: original DeepL OpenAPI -> FastMCP 4.1.6 -> real stdio MCP -> original PydanticAI result mapper.

Only vendor source/dependencies are downloaded in the Docker build. Runtime:
--network none, one locally replayed GET /v2/usage, synthetic quota/rate-limit
code values allowed by the vendor schema, no keys, no external API or LLM.
"""
from __future__ import annotations
import argparse
import asyncio
from collections import Counter
from contextlib import AsyncExitStack
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
import json
import os
import tempfile

ROOT=Path(__file__).resolve().parent
PIN=json.loads((ROOT/'FROZEN_PROTOCOL.json').read_text())
SOURCE=Path('/opt/deepl-source/openapi.json')
PATH='/v2/usage'

def digest(value):
    if isinstance(value,bytes): payload=value
    else: payload=json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
    return sha256(payload).hexdigest()

def safe(x):
    if x is None or isinstance(x,(str,int,float,bool)): return x
    if isinstance(x,(list,tuple)): return [safe(v) for v in x]
    if isinstance(x,dict): return {str(k):safe(v) for k,v in x.items()}
    if hasattr(x,'model_dump'): return safe(x.model_dump(exclude_none=True))
    return {'unserializable_python_type':type(x).__name__}

def get_ref(original, pointer):
    assert pointer.startswith('#/components/'),pointer
    obj=original
    for part in pointer[2:].split('/'):
        part=part.replace('~1','/').replace('~0','~')
        obj=obj[part]
    return obj

def project_spec(original,base):
    assert original['info']['version']==PIN['source']['api_version']
    op=json.loads(json.dumps(original['paths'][PATH]['get']))
    assert op['operationId']=='getUsage'
    assert sorted(map(int,op['responses']))==sorted(PIN['source']['declared_statuses'])
    assert op['responses']['456']['$ref']=='#/components/responses/QuotaExceeded'
    assert op['responses']['429']['$ref']=='#/components/responses/TooManyRequests'
    assert original['components']['schemas']['ErrorResponse']['required']==['message']
    assert original['components']['schemas']['ErrorResponse']['properties']['code']['type']=='string'
    success=(op['responses']['200']['content']['application/json']['examples']['free']['value'])
    assert success=={'character_count':180118,'character_limit':1250000}
    refs={}
    seen=set()
    def collect(obj):
        if isinstance(obj,dict):
            ptr=obj.get('$ref')
            if isinstance(ptr,str) and ptr.startswith('#/components/'):
                if ptr not in seen:
                    seen.add(ptr)
                    parts=ptr[2:].split('/')
                    assert len(parts)>=3
                    node=refs.setdefault(parts[0],{})
                    for part in parts[1:-1]:node=node.setdefault(part,{})
                    target=json.loads(json.dumps(get_ref(original,ptr)))
                    node[parts[-1]]=target
                    collect(target)
            for val in obj.values():collect(val)
        elif isinstance(obj,list):
            for val in obj:collect(val)
    collect(op)
    op.pop('security',None)  # only in local test projection; production schema untouched
    derived={
       'openapi':original['openapi'],
       'info':{'title':original['info']['title'],'version':original['info']['version']},
       'servers':[{'url':base}],
       'paths':{PATH:{'get':op}},
       'components':refs}
    return derived,success

def local_replay(success):
    fixture=[]
    for case in PIN['cases']:
        payload=json.loads(json.dumps(success if case['id']=='S200' else case['body']))
        fixture.append({'id':case['id'],'status':case['status'],'body':payload})
    state={'index':0,'trace':[],'unexpected':[]}
    class Handler(BaseHTTPRequestHandler):
        def _reject(self,method):
            state['unexpected'].append({'method':method,'path':self.path})
            self.send_response(405);self.send_header('Content-Length','0');self.end_headers()
        def do_GET(self):
            if self.path!=PATH or state['index']>=len(fixture):
                state['unexpected'].append({'method':'GET','path':self.path})
                self.send_response(404);self.send_header('Content-Length','0');self.end_headers()
                return
            item=fixture[state['index']];state['index']+=1
            blob=json.dumps(item['body'],separators=(',',':'),ensure_ascii=False).encode()
            state['trace'].append({'id':item['id'],'method':'GET','path':self.path,
                                   'status':item['status'],'body':item['body'],
                                   'raw_sha256':digest(blob)})
            self.send_response(item['status'])
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(blob)))
            self.end_headers();self.wfile.write(blob)
        def do_POST(self):self._reject('POST')
        def do_PUT(self):self._reject('PUT')
        def do_PATCH(self):self._reject('PATCH')
        def do_DELETE(self):self._reject('DELETE')
        def log_message(self,*a):pass
    srv=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    return srv,state

def normalized(actual):
    # Name translation only: still the original SDK object's data, untouched.
    return SimpleNamespace(
       content=actual.content,
       is_error=bool(getattr(actual,'isError',getattr(actual,'is_error',False))),
       structured_content=getattr(actual,'structuredContent',
                                  getattr(actual,'structured_content',None)))

def raw_record(actual):
    d=normalized(actual)
    return {'isError':d.is_error,'structuredContent':safe(d.structured_content),
            'content':safe(d.content)}

def server_env(base):
    keep=('PATH','HOME','TMPDIR','LANG','LC_ALL','SYSTEMROOT')
    env={k:os.environ[k] for k in keep if k in os.environ}
    env.update({'HOME':'/tmp','TMPDIR':'/tmp','XDG_CACHE_HOME':'/tmp/cache',
                'PYTHONDONTWRITEBYTECODE':'1','PYTHONUNBUFFERED':'1',
                'PYTHON_DOTENV_DISABLED':'1'})
    assert base.startswith('http://127.0.0.1:')
    return env

async def real_mcp_calls(specpath,base):
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.types import CallToolResult
    from pydantic_ai.mcp import _map_mcp_call_tool_result
    params=StdioServerParameters(command='/opt/fastmcp-venv/bin/python',
        args=['-u',str(ROOT/'server.py'),str(specpath),base],env=server_env(base))
    rows=[]
    async with stdio_client(params) as (reader,writer):
      async with ClientSession(reader,writer) as session:
        await session.initialize()
        listing=await session.list_tools()
        names=[t.name for t in listing.tools]
        assert 'getUsage' in names,('TOOL_NOT_LISTED',names)
        target=next(t for t in listing.tools if t.name=='getUsage')
        assert not target.inputSchema.get('required',[]),target.inputSchema
        for case in PIN['cases']:
            actual=await session.call_tool('getUsage',{})
            record=raw_record(actual)
            mapped=_map_mcp_call_tool_result(normalized(actual),prefer_structured=True)
            mapped_safe=safe(mapped)
            expected=case['body']
            if expected is not None:
                from mcp.types import TextContent
                # Explicit consumer preservation negative control. No producer code
                # modification; instantiate an authentic SDK result with structured error.
                ctrl=CallToolResult(content=[TextContent(type='text',text='local synthetic error')],
                                    isError=True,structuredContent=expected)
                ctrl_mapped=_map_mcp_call_tool_result(normalized(ctrl),prefer_structured=True)
                control={'mapped':safe(ctrl_mapped),'typed_code_preserved':
                    isinstance(ctrl_mapped,dict) and ctrl_mapped.get('code')==expected['code']}
            else:control=None
            rows.append({'case':case['id'],'expected_http_status':case['status'],
                'mcp':record,'consumer':{'python_type':type(mapped).__name__,'mapped':mapped_safe},
                'structured_control':control})
    return names,rows

def classify(state,rows,source_sha,derived):
    assert state['index']==len(PIN['cases'])==3,state
    assert not state['unexpected'],state['unexpected']
    assert [x['status'] for x in state['trace']]==[200,456,429],state['trace']
    assert all(x['path']==PATH for x in state['trace'])
    by={row['case']:row for row in rows}
    assert set(by)=={'S200','E456','E429'}
    assert all(by[x]['structured_control']['typed_code_preserved'] for x in ('E456','E429'))
    records=[]
    for request in state['trace']:
        row=by[request['id']]
        expected=request['body']
        structured=row['mcp']['structuredContent']
        mapped=row['consumer']['mapped']
        machine=bool(isinstance(structured,dict) and
             structured.get('code')==expected.get('code')) if request['status']!=200 else None
        consumer=bool(isinstance(mapped,dict) and
             mapped.get('code')==expected.get('code')) if request['status']!=200 else None
        code=expected.get('code')
        content_text=json.dumps(row['mcp']['content'],ensure_ascii=False,sort_keys=True)
        consumer_text=json.dumps(mapped,ensure_ascii=False,sort_keys=True)
        records.append({'case':request['id'],'status':request['status'],
             'original_body':expected,'original_sha256':digest(expected),
             'mcp':row['mcp'],'consumer':row['consumer'],
             'structured_control':row['structured_control'],
             'mcp_typed_code_accessible':machine,
             'consumer_typed_code_accessible':consumer,
             'mcp_any_text_mentions_code':code in content_text if code else None,
             'consumer_any_text_mentions_code':code in consumer_text if code else None})
    errors=[x for x in records if x['status']!=200]
    lost=[x for x in errors if x['consumer_typed_code_accessible'] is False]
    preserved=[x for x in errors if x['consumer_typed_code_accessible'] is True]
    outcome=('TYPED_ERROR_LOSS_ACROSS_CHAIN' if len(lost)==2 else
             'TYPED_ERROR_PRESERVED_ACROSS_CHAIN' if len(preserved)==2 else
             'MIXED_OR_INCONCLUSIVE')
    return {'schema':'risu-p4e-second-independent-full-chain-v1',
      'outcome':outcome,'pins':PIN,
      'execution':{'source':'ORIGINAL_DEEPL_OPENAPI_SINGLE_OPERATION_LOCAL_PROJECTION',
          'converter':'REAL_FASTMCP_4_1_6_FROM_OPENAPI_STDIO_SERVER',
          'transport':'REAL_MCP_SDK_STDIO_SESSION_AND_LOCALHOST_HTTP',
          'consumer':'ORIGINAL_PYDANTICAI_MCP_RESULT_MAPPER_NOT_FULL_AGENT',
          'vendor_api_called':False,'external_llm_called':False,'credentials_used':False,
          'tool_list':names_cache[0],
          'http_trace':state['trace'],'unexpected_http_requests':state['unexpected']},
      'checks':{'source_sha256':source_sha,'derived_spec_sha256':digest(derived),
          'positive_success_case_observed':by['S200']['case']=='S200',
          'preservation_controls':all(x['structured_control']['typed_code_preserved'] for x in errors),
          'synthetic_error_codes':True,'error_flags':[x['mcp']['isError'] for x in errors],
          'typed_codes_consumer':[x['consumer_typed_code_accessible'] for x in errors]},
      'results':records,
      'limitations':'DeepL original published schema plus local example/synthetic-schema-valid response replay; no live vendor traffic, no live user impact or novel upstream bug allegation.'}

names_cache=[]

async def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    original=json.loads(SOURCE.read_text(encoding='utf-8'))
    assert SOURCE.is_file()
    with tempfile.TemporaryDirectory(dir='/tmp',prefix='risu-p4e-') as t:
        # Success fixture comes from real vendor spec; error code values are declared synthetic.
        derived_preview,good=project_spec(original,'http://127.0.0.1:1')
        server,state=local_replay(good)
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port)
        try:
            derived,success=project_spec(original,base)
            assert success==good
            target=Path(t)/'single-operation.json'
            target.write_text(json.dumps(derived,ensure_ascii=False))
            assert not state['trace']
            names,rows=await real_mcp_calls(target,base)
            names_cache.clear();names_cache.append(names)
            report=classify(state,rows,digest(SOURCE.read_bytes()),derived)
        finally:
            server.shutdown();server.server_close();thread.join(timeout=5)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
    print('RISU_P4E_RESULT',report['outcome'],
          'HTTP',[(x['case'],x['status']) for x in report['results']],
          'ERROR_FLAGS',report['checks']['error_flags'],
          'CONSUMER_TYPED',report['checks']['typed_codes_consumer'],flush=True)

if __name__=='__main__':asyncio.run(main())
