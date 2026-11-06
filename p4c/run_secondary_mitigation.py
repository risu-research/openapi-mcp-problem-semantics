"""Post-hoc narrow consumer compatibility mitigation, verified in original SDKs.

NOT part of frozen four-scenario discovery result. In a *synthetic test* of
error-only structuredContent (with empty text), add a minimal, explicitly
allowlisted JSON text block containing only 'code' and 'retry_after' fields.

This is NOT a universal repair; LangChain's machine artifact still remains
None on the known error path, and exposing sensitive error bodies to models
would require additional user review. No vendor code modifications.
"""
from __future__ import annotations
import argparse
import asyncio
import json
from pathlib import Path

from run_external_consumers import (
    as_json_safe, assert_source, mcp_message, normalized,
)

def safe_summary(payload):
    if not isinstance(payload,dict):raise ValueError('UNKNOWN_ERROR_BODY')
    # Only fields with known non-sensitive synthetic meaning may reach model.
    code=payload.get('code')
    retry=payload.get('retry_after')
    if code is not None and (not isinstance(code,str) or
                             len(code)>64 or code not in ('RATE_LIMITED',)):
        raise ValueError('CODE_NOT_ALLOWLISTED')
    if retry is not None and (type(retry) is not int or retry<0 or retry>86400):
        raise ValueError('INVALID_RETRY_DELAY')
    summary={}
    if code is not None:summary['code']=code
    if retry is not None:summary['retry_after']=retry
    if not summary:raise ValueError('NO_ALLOWLISTED_ERROR_FIELDS')
    return summary

def propose_local_error_text(original):
    """Return cloned synthetic message, never mutate producer's original."""
    import copy
    result=copy.deepcopy(original)
    if (result.get('isError') is not True or result.get('content')
        or 'structuredContent' not in result):
        return result
    data=safe_summary(result['structuredContent'])
    result['content']=[{'type':'text','text':json.dumps(
        data,sort_keys=True,separators=(',',':'),allow_nan=False)}]
    return result

CASES={
 'minimal_no_text':{'content':[],
                   'structuredContent':{'retry_after':30},'isError':True},
 'minimal_safe_text':{'content':[{'type':'text','text':'{"retry_after":30}'}],
                   'structuredContent':{'retry_after':30},'isError':True},
 'success_control':{'content':[{'type':'text','text':'ok'}],
                   'structuredContent':{'retry_after':30},'isError':False},
 'existing_text_control':{'content':[{'type':'text','text':'rate limited'}],
                   'structuredContent':{'retry_after':30},'isError':True}
}
assert propose_local_error_text(CASES['minimal_no_text'])==CASES['minimal_safe_text']
assert propose_local_error_text(CASES['success_control'])==CASES['success_control']
assert propose_local_error_text(CASES['existing_text_control'])==CASES['existing_text_control']
assert CASES['minimal_no_text']['content']==[]

def has_hint(value):
    text=json.dumps(value,ensure_ascii=False)
    return 'retry_after' in text and '30' in text

async def run_langchain():
    from langchain.mcp.tools import as_langchain_tool
    from mcp.types import Tool
    records=[]
    for name,result in CASES.items():
        actual=normalized(mcp_message({'mcp':result}))
        class LocalClient:
            server_info=None
            async def __aenter__(self):return self
            async def __aexit__(self,*args):return False
            async def call_tool(self,name,args,raise_on_error=False):
                assert not args and raise_on_error is False
                return actual
        tool=await as_langchain_tool(
            Tool(name='local_synthetic',description='synthetic',
                 inputSchema={'type':'object','properties':{}}),
            LocalClient())
        message=await tool.ainvoke(
            {'type':'tool_call','id':'synthetic','name':'local_synthetic','args':{}})
        model_text=as_json_safe(message.content)
        artifact=as_json_safe(message.artifact)
        records.append({
          'case':name,'tool_status':message.status,
          'model_visible_safe_hint':has_hint(model_text),
          'artifact_safe_hint':has_hint(artifact),
          'machine_artifact_exists':artifact is not None})
    return records

async def run_openai():
    from agents.mcp.util import MCPUtil
    from agents.run_context import RunContextWrapper
    from mcp.types import Tool
    records=[]
    tool=Tool(name='local_synthetic',description='synthetic',
              inputSchema={'type':'object','properties':{}})
    ctx=RunContextWrapper(context={})
    for name,result in CASES.items():
        raw=mcp_message({'mcp':result})
        class LocalServer:
            name='safe-synthetic-only'
            use_structured_content=True
            tool_meta_resolver=None
            custom_data_extractor=None
            async def call_tool(self,name,args):
                assert not args
                return raw
        out=as_json_safe(await MCPUtil.invoke_mcp_tool(LocalServer(),tool,ctx,'{}'))
        records.append({'case':name,
                        'model_visible_safe_hint':has_hint(out),
                        'model_visible_result_is_empty':out==[]})
    return records

async def run_pydantic():
    from pydantic_ai.mcp import _map_mcp_call_tool_result
    records=[]
    for name,result in CASES.items():
        original=normalized(mcp_message({'mcp':result}))
        out=as_json_safe(_map_mcp_call_tool_result(original,prefer_structured=True))
        records.append({'case':name,'mapped_safe_hint':has_hint(out),
                        'mapped_equals_structured':out==result['structuredContent']})
    return records

async def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--framework',choices=['langchain','openai','pydanticai'],required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    pin=assert_source(args.framework)
    data=await {'langchain':run_langchain,'openai':run_openai,
                'pydanticai':run_pydantic}[args.framework]()
    rows={i['case']:i for i in data}
    assert set(rows)==set(CASES)
    if args.framework=='langchain':
        assert rows['minimal_no_text']['tool_status']=='error'
        assert not rows['minimal_no_text']['model_visible_safe_hint']
        assert not rows['minimal_no_text']['machine_artifact_exists']
        assert rows['minimal_safe_text']['model_visible_safe_hint']
        assert not rows['minimal_safe_text']['machine_artifact_exists']
        assert rows['success_control']['machine_artifact_exists']
        assert rows['success_control']['artifact_safe_hint']
        assert not rows['existing_text_control']['model_visible_safe_hint']
    elif args.framework=='openai':
        assert rows['minimal_no_text']['model_visible_result_is_empty']
        assert not rows['minimal_no_text']['model_visible_safe_hint']
        assert rows['minimal_safe_text']['model_visible_safe_hint']
        assert not rows['minimal_safe_text']['model_visible_result_is_empty']
        assert rows['success_control']['model_visible_safe_hint']
        assert not rows['existing_text_control']['model_visible_safe_hint']
    else:
        assert all(x['mapped_safe_hint'] and x['mapped_equals_structured']
                   for x in rows.values())
    report={'schema':'risu-p4c-posthoc-mitigation-v1',
            'status':'PASS','framework':args.framework,'pinned':pin,
            'method':'Original external consumer function; synthetic local MCP result; deliberately added allowlisted text on structured-only errors',
            'result':data,
            'known_limitation':'Preserves model-visible safe hint in LangChain and OpenAI; does not restore LangChain machine artifact; SDK code unchanged',
            'not_part_of_preregistered_discovery':True}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+'\n')
    print('RISU_P4C_POSTHOC_SAFE_TEXT_MITIGATION_PASS',args.framework,flush=True)

if __name__=='__main__':
    asyncio.run(main())
