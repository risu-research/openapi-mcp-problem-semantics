#!/usr/bin/env python3
"""Minimal external interop test: actual FastMCP OpenAPI and SDK 2 stdio."""
import asyncio
import hashlib
import importlib.metadata
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import urlopen

BASE = Path(__file__).resolve().parent
CANARY = 'RISU_TAIL_CANARY_9f62b7c5_END'
IDS = ['boundary-999','boundary-1000','boundary-1001','boundary-1600',
       'boundary-5000','validation-40','unicode-1600','success']

def json_text(obj):
    return json.dumps(obj, ensure_ascii=False)

def case(name):
    if name == 'success': return 200, 'application/json', {'ok': True}
    if name == 'validation-40':
        return 422, 'application/problem+json', {
            'type': 'https://example.test/problems/validation',
            'title': 'Validation failed',
            'errors': [{'pointer': f'#/items/{i}/quantity',
                        'detail': 'must be a positive integer'} for i in range(40)],
            'critical_tail': CANARY,
        }
    n = int(name.rsplit('-', 1)[1])
    d = {'type': 'https://example.test/problems/stale-version',
         'title': '버전 충돌' if name.startswith('unicode') else 'Version conflict',
         'current_version': 'v3', 'expected_version': 'v2',
         'padding': '', 'critical_tail': CANARY}
    d['padding'] = 'x' * (n - len(json_text(d)))
    assert len(json_text(d)) == n
    return 409, 'application/problem+json', d

class API(BaseHTTPRequestHandler):
    def do_GET(self):
        name = self.path.split('/cases/')[-1]
        if name not in IDS: self.send_error(404); return
        status, mime, body = case(name)
        b = json_text(body).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)
    def log_message(self, *args): pass

def source_get(base, name):
    try: r = urlopen(base+'/cases/'+name, timeout=8)
    except HTTPError as e: r = e
    with r:
        return {'status': r.status, 'body': json.loads(r.read(128000).decode('utf-8')),
                'content_type': r.headers.get('Content-Type').split(';')[0]}

def digest(obj):
    data = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(data.encode('utf-8')).hexdigest()

def observation(source, wire):
    b = source['body']
    texts = [x.get('text', '') for x in wire.get('content', []) if x.get('type') == 'text']
    t = '\n'.join(texts)
    machine = [wire.get('structuredContent')]
    for x in wire.get('content', []):
        if x.get('type') == 'resource' and x.get('resource', {}).get('mimeType') == 'application/problem+json':
            try: machine.append(json.loads(x['resource']['text']))
            except (ValueError, KeyError): pass
    m = (wire.get('_meta') or {}).get('org.risu.reference.source_http', {})
    return {'source_json_chars': len(json_text(b)),
            'source_utf8_bytes': len(json_text(b).encode('utf-8')),
            'machine_exact': any(x == b for x in machine),
            'is_error': wire.get('isError'),
            'truncation_marker': '… (truncated)' in t,
            'full_json_in_text': json_text(b) in t,
            'tail_canary_in_text': CANARY in t,
            'tail_canary_in_machine': any(isinstance(x,dict) and x.get('critical_tail') == CANARY for x in machine),
            'observed_status_in_meta': m.get('observed_http_status')}

async def target_test(which, base):
    from mcp import Client, StdioServerParameters
    name = 'server_fastmcp.py' if which == 'fastmcp4' else 'server_control.py'
    params = StdioServerParameters(command=os.sys.executable,
                                  args=['-u', str(BASE/name)], env={'RISU_TEST_URL': base})
    async with Client(params) as client:
        tools = {x.name for x in (await client.list_tools()).tools}
        assert 'get_case' in tools, f'get_case absent from {tools}'
        results=[]
        for case_id in IDS:
            upstream = source_get(base, case_id)
            raw = (await client.call_tool('get_case', {'id':case_id})).model_dump(mode='json',by_alias=True,exclude_none=True)
            results.append({'case':case_id, 'observation':observation(upstream,raw),
                            'upstream':upstream,'mcp_wire':raw,
                            'upstream_sha256':digest(upstream), 'mcp_sha256':digest(raw)})
        return {'target':which, 'protocol_version':client.protocol_version,'cases':results}

def main():
    for n in [999,1000,1001,1600,5000]: assert len(json_text(case('boundary-'+str(n))[2]))==n
    assert len(json_text(case('unicode-1600')[2]))==1600
    assert json_text(case('validation-40')[2]).index(CANARY)>1000
    from fastmcp.server.providers.openapi.components import _ERROR_BODY_LIMIT, _bounded_error_body
    assert _ERROR_BODY_LIMIT == 1000
    assert _bounded_error_body('x'*1001) == 'x'*1000 + '… (truncated)'
    versions={x:importlib.metadata.version(x) for x in ['mcp','fastmcp','fastmcp-slim']}
    assert versions == {'mcp':'2.3.0','fastmcp':'4.1.6','fastmcp-slim':'4.1.6'}, versions
    http = ThreadingHTTPServer(('127.0.0.1',0),API)
    thread=Thread(target=http.serve_forever,daemon=True); thread.start()
    base=f'http://127.0.0.1:{http.server_port}'
    try:
        targets=[asyncio.run(asyncio.wait_for(target_test(name,base), timeout=100))
                 for name in ['fastmcp4','sdk2_control']]
    finally:
        http.shutdown(); http.server_close()
    result={'status':'EXECUTED', 'versions':versions,'synthetic_localhost':True,'targets':targets}
    out=BASE/'results';out.mkdir(exist_ok=True)
    (out/'evidence.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    f={r['case']:r['observation'] for r in targets[0]['cases']}
    c={r['case']:r['observation'] for r in targets[1]['cases']}
    lines=['# Long error truncation experiment', '',
           '| Case | JSON length | FastMCP machine | FastMCP truncation | Tail visible | SDK control machine |',
           '|---|---:|---|---|---|---|']
    for n in IDS:
        a=f[n]; b=c[n]
        lines.append(f"| {n} | {a['source_json_chars']} | {a['machine_exact']} | {a['truncation_marker']} | {a['tail_canary_in_text']} | {b['machine_exact']} |")
    lines.extend(['','Synthetic localhost only. SDK control is a hand-written preservation map, not a native OpenAPI converter.'])
    (out/'SUMMARY.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))
    for n in IDS:
        if n!='success' and not c[n]['machine_exact']:
            raise AssertionError('Positive control failed: '+n)
    return 0

if __name__=='__main__':
    raise SystemExit(main())
