"""Capture exact MCP stdio wire from an installed, released external MCP server.

Never calls network-facing tools. Runs mcp-server-time from the current Python venv,
and validates the installed distribution identity before invoking the server.
"""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys

MAX_FRAME = 2_000_000

def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()

async def capture(version: str, folder: Path):
    installed = importlib.metadata.version('mcp-server-time')
    if installed != version:
        raise RuntimeError(f'Wrong installed external distribution: {installed}, expected {version}')
    env = {key: os.environ[key] for key in ('PATH','HOME','LANG','LC_ALL','SYSTEMROOT') if key in os.environ}
    env.update({'TZ':'UTC','PYTHONDONTWRITEBYTECODE':'1','PYTHONUNBUFFERED':'1'})
    proc = await asyncio.create_subprocess_exec(sys.executable, '-m', 'mcp_server_time', '--local-timezone', 'UTC',
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env)
    frames=[]
    async def send(obj):
        raw=canonical(obj)+b'\n'
        proc.stdin.write(raw)
        await asyncio.wait_for(proc.stdin.drain(), 15)
        frames.append({'direction':'client_to_server','wire_utf8':raw.decode()})
        if 'id' not in obj:
            return None
        while True:
            line=await asyncio.wait_for(proc.stdout.readline(),45)
            if not line:
                raise RuntimeError(f'External server exited early before response for {obj["id"]}')
            if len(line)>MAX_FRAME:raise RuntimeError('Oversized stdio frame')
            response=json.loads(line)
            if response.get('jsonrpc')!='2.0':raise RuntimeError('Unexpected JSONRPC response')
            frames.append({'direction':'server_to_client','wire_utf8':line.decode()})
            if response.get('id')!=obj['id']:
                if 'id' in response:raise RuntimeError('Mismatched MCP response ID')
                continue
            if 'error' in response:raise RuntimeError(f'External MCP error: {response["error"]}')
            return response
    try:
        initialization=await send({'jsonrpc':'2.0','id':1,'method':'initialize','params':{
            'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'RISU-P4U-external-version-audit','version':'0'}}})
        server_version=initialization.get('result',{}).get('serverInfo',{}).get('version')
        if server_version != version:raise RuntimeError(f'Server-reported version mismatch: {server_version} vs {version}')
        await send({'jsonrpc':'2.0','method':'notifications/initialized','params':{}})
        listing=await send({'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}})
        tool_map={t['name']:t for t in listing['result'].get('tools',[])}
        for name in ('get_current_time','convert_time'):
            if name not in tool_map:raise RuntimeError('Missing expected tool: '+name)
            if not isinstance(tool_map[name].get('outputSchema'),dict):raise RuntimeError('Missing actual outputSchema: '+name)
        calls={
            'convert_time': {'source_timezone':'America/New_York','time':'12:34','target_timezone':'Europe/London'},
            'get_current_time':{'timezone':'UTC'},
        }
        if 'get_time_ago' in tool_map:
            calls['get_time_ago']={'timezone':'UTC','seconds_ago':5}
        results={}
        for n,(name,args) in enumerate(calls.items(),3):
            reply=await send({'jsonrpc':'2.0','id':n,'method':'tools/call','params':{'name':name,'arguments':args}})
            result=reply['result']
            if result.get('isError',False):raise RuntimeError(f'Unexpected tool error for {name}: {result}')
            if not isinstance(result.get('structuredContent'),dict):raise RuntimeError('Expected actual structuredContent: '+name)
            results[name]={'arguments':args,'response':reply}
    finally:
        proc.stdin.close()
        try:await asyncio.wait_for(proc.wait(),15)
        except asyncio.TimeoutError:
            proc.kill();await proc.wait()
        stderr=(await proc.stderr.read()).decode('utf-8','replace')
        if proc.returncode!=0:raise RuntimeError(f'MCP subprocess returned {proc.returncode}: {stderr[-2000:]}')
    folder.mkdir(parents=True,exist_ok=True)
    wire=''.join(f['wire_utf8'] for f in frames)
    (folder/'mcp_stdio_wire.jsonl').write_text(wire)
    (folder/'tools_list.json').write_text(json.dumps(listing,sort_keys=True,indent=2)+'\n')
    (folder/'tool_calls.json').write_text(json.dumps(results,sort_keys=True,indent=2)+'\n')
    info={'source':'official published mcp-server-time PyPI wheel (installed in isolated venv)',
        'version':version,'server_reported_version':server_version,'protocol_request':'2025-11-25',
        'actual_mcp_stdio_wire':True,'tools':sorted(tool_map),
        'wire_sha256':hashlib.sha256(wire.encode()).hexdigest(),
        'tools_list_sha256':hashlib.sha256((folder/'tools_list.json').read_bytes()).hexdigest(),
        'tool_calls_sha256':hashlib.sha256((folder/'tool_calls.json').read_bytes()).hexdigest(),
        'tool_count':len(tool_map),'real_tool_calls':len(results),
        'same_runtime_call_captures':True,'live_upstream_http':False,
        'original_source_commit':{'2026.10.19':'51b6382a3e827aceb6bce430b1208d69b93d95ea',
                                  '2026.11.4':'36380287ed3b15d115b55f546617d723072b1296'}[version]}
    (folder/'capture_manifest.json').write_text(json.dumps(info,sort_keys=True,indent=2)+'\n')
    print('P4U_REAL_EXTERNAL_MCP_VERSION_CAPTURE_PASS',json.dumps(info,sort_keys=True),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--version',required=True,choices=['2026.10.19','2026.11.4']);p.add_argument('--out',required=True,type=Path)
    a=p.parse_args();asyncio.run(capture(a.version,a.out))
