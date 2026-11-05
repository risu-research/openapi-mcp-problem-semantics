#!/usr/bin/env python3
"""Independent stdlib legacy protocol test double, not an SDK server."""
import json,sys
for line in sys.stdin:
    ident=None
    try:
        req=json.loads(line)
        ident=req.get('id');method=req.get('method')
        if method=='notifications/initialized':continue
        if method=='initialize':
            result={'protocolVersion':'2025-11-25','serverInfo':{'name':'risu-legacy-test','version':'1'},'capabilities':{'tools':{}}}
        elif method=='tools/list':
            result={'tools':[{'name':'echo','description':'test-only read','inputSchema':{'type':'object','properties':{'value':{'type':'string'}},'required':['value']}}]}
        elif method=='tools/call':
            params=req.get('params') or {}
            if params.get('name')!='echo':raise ValueError('unknown tool')
            value=params['arguments']['value']
            if not isinstance(value,str):raise ValueError('bad type')
            result={'isError':False,'structuredContent':{'value':value},'content':[{'type':'text','text':value}]}
        else:
            if ident is not None:print(json.dumps({'jsonrpc':'2.0','id':ident,'error':{'code':-32601,'message':'Method not found'}}),flush=True)
            continue
        if ident is not None:print(json.dumps({'jsonrpc':'2.0','id':ident,'result':result}),flush=True)
    except (ValueError,TypeError,KeyError):
        if ident is not None:print(json.dumps({'jsonrpc':'2.0','id':ident,'error':{'code':-32602,'message':'Invalid params'}}),flush=True)
