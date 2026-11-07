"""Bounded test-only stdio MCP producer adapter. Real CNOE backend remains untouched.

Pass-through for all traffic except an allowlisted 404 response. The adapter
requires the original HTTP error body from a separately recorded local replay;
it cannot reconstruct fields from the already lossy MCP response alone.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import select
import subprocess
import sys

SOURCE_FIELDS={'message','code','type','link'}

def restore_source_404(request:dict, response:dict, source:dict) -> tuple[dict,bool]:
    """Rewrite exactly one declared error with source proof; fail closed otherwise."""
    if request.get('method')!='tools/call':return response,False
    args=request.get('params',{})
    if args.get('name')!='get_index' or args.get('arguments')!={'path_indexUid':'does-not-exist'}:
        return response,False
    if not isinstance(source,dict) or set(source)!=SOURCE_FIELDS or any(not isinstance(v,str) or not v or len(v)>4096 for v in source.values()):
        raise ValueError('Source error is not complete allowlisted four-field record')
    if source['code']!='index_not_found' or source['type']!='invalid_request':
        raise ValueError('Source error is not the pinned local 404 fixture')
    result=response.get('result')
    if not isinstance(result,dict) or result.get('isError') not in (None,False):
        raise ValueError('Unexpected actual generated MCP result kind')
    structured=result.get('structuredContent')
    if not isinstance(structured,dict) or set(structured)!={'error'} or not isinstance(structured['error'],str):
        raise ValueError('Unexpected original CNOE structured error shape')
    if '404' not in structured['error'] or source['code'] in json.dumps(result,sort_keys=True):
        raise ValueError('Loss precondition not supported by actual CNOE response')
    copy={**response, 'result':{**result, 'content':[{'type':'text','text':json.dumps(source,ensure_ascii=False,sort_keys=True)}],
       'structuredContent':dict(source),'isError':True}}
    return copy,True

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--backend-python',required=True)
    p.add_argument('--server',required=True)
    p.add_argument('--mode',required=True,choices=('passthrough','repair'))
    p.add_argument('--wire-out',required=True,type=Path)
    args=p.parse_args()
    source=json.loads(os.environ['P5B_ORIGINAL_HTTP_404'])
    env={k:v for k,v in os.environ.items() if k in ('HOME','PATH','TMPDIR','LANG','LC_ALL','SYSTEMROOT','API_BASE_URL','MEILISEARCH_API_URL','MEILISEARCH_TOKEN','PYTHONPATH','PYTHONDONTWRITEBYTECODE','PYTHONUNBUFFERED','PYTHON_DOTENV_DISABLED')}
    child=subprocess.Popen([args.backend_python,'-u',args.server],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env=env,bufsize=0)
    changed=0
    args.wire_out.parent.mkdir(parents=True,exist_ok=True)
    with args.wire_out.open('w',encoding='utf-8') as log:
        def event(direction,frame):
            log.write(json.dumps({'direction':direction,'frame':frame},sort_keys=True,ensure_ascii=False)+'\n')
            log.flush()
        try:
            for line in sys.stdin.buffer:
                if len(line)>2_000_000:raise ValueError('Oversized client MCP frame')
                req=json.loads(line)
                if not isinstance(req,dict) or req.get('jsonrpc')!='2.0':raise ValueError('Malformed request')
                event('client_to_proxy',req)
                child.stdin.write(line);child.stdin.flush()
                if 'id' not in req:continue
                for _ in range(8):
                    ready,_,_=select.select([child.stdout],[],[],45)
                    if not ready:raise TimeoutError('Backend MCP response timed out')
                    raw=child.stdout.readline()
                    if not raw or len(raw)>2_000_000:raise ValueError('Backend closed/oversized frame')
                    resp=json.loads(raw)
                    event('backend_to_proxy',resp)
                    if resp.get('id')==req['id']:break
                    if 'id' in resp:raise ValueError('Mismatched backend response ID')
                    sys.stdout.buffer.write(raw);sys.stdout.buffer.flush()
                    event('proxy_to_client',resp)
                else:raise ValueError('No corresponding MCP JSONRPC response')
                changed_this=False
                if args.mode=='repair':
                    resp,changed_this=restore_source_404(req,resp,source)
                    changed+=int(changed_this)
                    if changed>2:raise ValueError('More repair rewrites than qualified scope')
                event('repair_event',{'changed':changed_this,'mode':args.mode,'id':req['id']})
                event('proxy_to_client',resp)
                wire=(json.dumps(resp,ensure_ascii=False,separators=(',',':'))+'\n').encode()
                sys.stdout.buffer.write(wire);sys.stdout.buffer.flush()
        finally:
            try:child.stdin.close()
            except Exception:pass
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:child.kill();child.wait()
    if child.returncode!=0:raise RuntimeError(f'CNOE backend exit {child.returncode}')
    if args.mode=='repair' and changed!=2:raise RuntimeError(f'Expected exactly two source-backed 404 repairs, got {changed}')
    if args.mode=='passthrough' and changed:raise RuntimeError('Unexpected passthrough rewrite')

if __name__=='__main__':main()