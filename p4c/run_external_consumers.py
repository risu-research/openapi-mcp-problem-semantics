"""Real, pinned third-party MCP consumer implementations, synthetic data only.

No remote network/server/API/LLM invoked. Each scenario is selected BEFORE
execution in FROZEN_EXTERNAL_CONSUMER_PROTOCOL.json. The actual installed
consumer library's function is called, not a copied approximation.

Analysis boundaries:
* LangChain artifact visibility on errors has already been publicly reported
  (langchain-ai/langchain#40471). Do not call this a new defect.
* OpenAI Agents uses a documented error-text precedence policy. A loss to
  model-visible text is observable, but isn't automatically a protocol bug.
* PydanticAI result mapper is a preservation comparator, not a full agent run.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

HERE=Path(__file__).resolve().parent
PROTOCOL=json.loads((HERE/'FROZEN_EXTERNAL_CONSUMER_PROTOCOL.json').read_text(encoding='utf-8'))
SCENARIOS=PROTOCOL['scenarios']
PUBLIC_FIELDS={'retry_after','code'}

def sha_source(path:Path)->str:
    blob=path.read_bytes()
    return hashlib.sha1(b'blob '+str(len(blob)).encode()+b'\0'+blob).hexdigest()

def assert_source(framework:str):
    ref=next(x for x in PROTOCOL['products_under_test'] if
             x['name'].lower().startswith(framework.replace('_',' ').lower().split()[0]))
    root={
        'langchain':Path('/opt/langchain-source'),
        'openai':Path('/opt/agents-source'),
        'pydanticai':Path('/opt/pydantic-source'),
    }[framework]
    src=root/ref['source']
    if not src.is_file():raise RuntimeError('EXACT_PINNED_LIBRARY_SOURCE_NOT_FOUND')
    if sha_source(src)!=ref['git_blob']:
        raise RuntimeError('EXACT_PINNED_LIBRARY_BLOB_MISMATCH')
    return ref

def mcp_message(case:dict):
    """Instantiate an authentic installed MCP SDK result where available."""
    from mcp.types import CallToolResult, TextContent
    obj=case['mcp']
    blocks=[TextContent(type='text',text=c['text']) for c in obj.get('content',[])]
    data={'content':blocks,'isError':obj['isError']}
    if 'structuredContent' in obj:data['structuredContent']=obj['structuredContent']
    try:
        return CallToolResult(**data)
    except (TypeError,ValueError):
        # Some FastMCP 4/MCP SDK 2 releases use snake-case attribute names.
        return CallToolResult(content=blocks,is_error=obj['isError'],
                              structured_content=obj.get('structuredContent'))

def normalized(result):
    from mcp.types import CallToolResult
    return SimpleNamespace(
        content=result.content,
        structured_content=getattr(result,'structured_content',
                                   getattr(result,'structuredContent',None)),
        is_error=getattr(result,'is_error',
                         getattr(result,'isError',False)))

def as_json_safe(value):
    if isinstance(value,(str,int,float,bool)) or value is None:return value
    if isinstance(value,(list,tuple)):return [as_json_safe(x) for x in value]
    if isinstance(value,dict):
        return {str(k):as_json_safe(v) for k,v in value.items()}
    if hasattr(value,'model_dump'):
        return as_json_safe(value.model_dump(exclude_none=True))
    return {'type':type(value).__name__}

async def langchain_run():
    ref=assert_source('langchain')
    from langchain.mcp.tools import as_langchain_tool
    from mcp.types import Tool
    results=[]
    for case in SCENARIOS:
        raw=mcp_message(case)
        observed=normalized(raw)
        class SyntheticFastMCPClient:
            server_info=None
            protocol_version=None
            async def __aenter__(self):return self
            async def __aexit__(self,*args):return False
            async def call_tool(self,name,arguments,raise_on_error=False):
                assert name=='synthetic_error_tool' and arguments=={}
                assert raise_on_error is False
                return observed
        tool=Tool(name='synthetic_error_tool',
                  description='Read local synthetic error only',
                  inputSchema={'type':'object','properties':{}})
        converted=await as_langchain_tool(tool,SyntheticFastMCPClient())
        out=await converted.ainvoke({
            'type':'tool_call','name':'synthetic_error_tool','args':{},
            'id':'synthetic-call-1'})
        artifact=getattr(out,'artifact',None)
        status=getattr(out,'status',None)
        if status is None:
            raise RuntimeError('LANGCHAIN_TOOLMESSAGE_STATUS_NOT_VISIBLE')
        results.append({'id':case['id'],
                        'response_type':type(out).__name__,
                        'tool_message_status':status,
                        'tool_message_artifact':as_json_safe(artifact),
                        'content':as_json_safe(getattr(out,'content',None)),
                        'machine_error_field_visible':bool(
                            isinstance(artifact,dict) and
                            artifact.get('structured_content',{}).get('retry_after')==30
                        )})
    assert len(results)==4
    return {'framework':'LangChain current MCP','pinned':ref,'results':results}

async def openai_run():
    ref=assert_source('openai')
    from agents.mcp.util import MCPUtil
    from agents.run_context import RunContextWrapper
    from mcp.types import Tool
    tool=Tool(name='synthetic_error_tool',description='synthetic test',
              inputSchema={'type':'object','properties':{}})
    context=RunContextWrapper(context={})
    results=[]
    for case in SCENARIOS:
        actual=mcp_message(case)
        class LocalSyntheticServer:
            name='risu-local-test'
            use_structured_content=True
            tool_meta_resolver=None
            custom_data_extractor=None
            async def call_tool(self,name,arguments):
                assert name=='synthetic_error_tool' and arguments=={}
                return actual
        value=await MCPUtil.invoke_mcp_tool(LocalSyntheticServer(),tool,context,'{}')
        # Model-visible output from the real official SDK. Do not infer
        # this to mean raw SDK result data was lost.
        safe=as_json_safe(value)
        results.append({'id':case['id'],'model_visible_tool_output':safe,
                        'machine_error_field_visible':('retry_after' in json.dumps(safe))})
    assert len(results)==4
    return {'framework':'OpenAI Agents Python MCP','pinned':ref,'results':results}

async def pydanticai_run():
    ref=assert_source('pydanticai')
    from pydantic_ai.mcp import _map_mcp_call_tool_result
    results=[]
    for case in SCENARIOS:
        actual=normalized(mcp_message(case))
        mapped=_map_mcp_call_tool_result(actual,prefer_structured=True)
        safe=as_json_safe(mapped)
        results.append({'id':case['id'],'mapped_value':safe,
                        'machine_error_field_visible':(
                           isinstance(mapped,dict) and mapped.get('retry_after')==30)})
    assert len(results)==4
    return {'framework':'PydanticAI MCP','pinned':ref,'results':results}

def verify(framework,report):
    by={r['id']:r for r in report['results']}
    assert set(by)=={'E1','E2','S1','T1'}
    if framework=='langchain':
        assert by['E1']['tool_message_status']=='error'
        assert by['E2']['tool_message_status']=='error'
        assert by['S1']['tool_message_status']=='success'
        assert by['E1']['tool_message_artifact'] is None
        assert by['E2']['tool_message_artifact'] is None
        assert by['S1']['tool_message_artifact']=={
              'structured_content':{'code':'RATE_LIMITED','retry_after':30}}
        assert by['T1']['tool_message_status']=='error'
        assert not by['T1']['machine_error_field_visible']
    elif framework=='openai':
        assert by['E1']['model_visible_tool_output']==[]
        assert by['E2']['model_visible_tool_output']=={'type':'text','text':'rate limited'}
        assert by['T1']['model_visible_tool_output']=={'type':'text','text':'rate limited'}
        assert by['S1']['machine_error_field_visible']
        assert not by['E1']['machine_error_field_visible']
        assert not by['E2']['machine_error_field_visible']
    elif framework=='pydanticai':
        for label in ('E1','E2','S1'):
            assert by[label]['mapped_value']=={
               'code':'RATE_LIMITED','retry_after':30}
            assert by[label]['machine_error_field_visible']
        assert by['T1']['mapped_value']=='rate limited'
    else:raise ValueError('unknown framework')
    report['status']='PASS'
    report['claim_boundary']={
        'langchain':'KNOWN_PUBLIC_ISSUE_ALREADY_REPORTED_NOT_NEW_DISCOVERY',
        'openai':'EXPLICIT_SDK_ERROR_TEXT_PRECEDENCE_POLICY_NOT_A_CONFIRMED_VENDOR_BUG',
        'pydanticai':'REAL_ERROR_MAPPING_NEGATIVE_CONTROL_ONLY',
    }[framework]
    return report

async def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--framework',required=True,choices=('langchain','openai','pydanticai'))
    p.add_argument('--out',required=True,type=Path)
    args=p.parse_args(argv)
    run={'langchain':langchain_run,'openai':openai_run,'pydanticai':pydanticai_run}[args.framework]
    result=verify(args.framework,await run())
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('RISU_P4C_REAL_CONSUMER_PASS',args.framework,
          {k:v for k,v in [(r['id'],r.get('machine_error_field_visible')) for r in result['results']]},
          flush=True)

if __name__=='__main__':
    asyncio.run(main())
