#!/usr/bin/env python3
"""Independent masking & generic-error policy controls with real FastMCP stdio."""
import asyncio, json, os, sys
from pathlib import Path
from threading import Thread
from http.server import ThreadingHTTPServer
from experiment import API, CANARY

BASE=Path(__file__).resolve().parent

class ExtendedAPI(API):
    def do_GET(self):
        name=self.path.rsplit('/',1)[-1]
        if name=='nonproblem-1600':
            mime='application/json'
            body=json.dumps({'kind':'generic-error','padding':'x'*1600,
                             'critical_tail':CANARY})
            status=400
        elif name=='html-1600':
            mime='text/html'
            body='<html><body>' + ('x'*1600) + CANARY + '</body></html>'
            status=500
        else:
            return super().do_GET()
        b=body.encode('utf-8')
        self.send_response(status);self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(b)))
        self.end_headers();self.wfile.write(b)

async def invoke(base, masked):
    from mcp import Client, StdioServerParameters
    params=StdioServerParameters(command=sys.executable,
        args=['-u',str(BASE/'server_fastmcp.py')],
        env={'RISU_TEST_URL':base,'RISU_MASK_ERRORS': '1' if masked else '0'})
    cases=['boundary-999','boundary-5000','validation-40','nonproblem-1600','html-1600','success']
    out=[]
    async with Client(params) as client:
        names={x.name for x in (await client.list_tools()).tools}
        assert 'get_case' in names
        for name in cases:
            m=(await client.call_tool('get_case',{'id':name})).model_dump(mode='json',by_alias=True,exclude_none=True)
            text='\n'.join(x.get('text','') for x in m.get('content',[]) if x.get('type')=='text')
            row={'case':name,'masked':masked,'is_error':m.get('isError'),
                 'text':text,'contains_canary':CANARY in text,
                 'truncated':'… (truncated)' in text,
                 'contains_api_detail':'stale-version' in text or 'generic-error' in text,
                 'structured':m.get('structuredContent') is not None}
            out.append(row)
    return out

def validate(rows):
    by={(x['masked'],x['case']):x for x in rows}
    for masked in [False,True]:
        for name in ['boundary-999','boundary-5000','validation-40','nonproblem-1600','html-1600']:
            assert by[(masked,name)]['is_error'] is True,(masked,name)
        assert by[(masked,'success')]['is_error'] is False
        assert by[(masked,'success')]['structured'] is True
    assert by[(False,'boundary-999')]['contains_canary'] is True
    assert by[(False,'boundary-5000')]['truncated'] is True
    assert by[(False,'boundary-5000')]['contains_canary'] is False
    assert by[(False,'nonproblem-1600')]['truncated'] is True
    assert by[(False,'nonproblem-1600')]['contains_canary'] is False
    assert by[(False,'html-1600')]['contains_canary'] is False
    assert by[(False,'html-1600')]['truncated'] is False
    # mask_error_details=True should conceal ordinary upstream JSON body details.
    assert by[(True,'boundary-999')]['contains_canary'] is False
    assert by[(True,'boundary-999')]['contains_api_detail'] is False
    assert by[(True,'nonproblem-1600')]['contains_api_detail'] is False
    return True

def main():
    server=ThreadingHTTPServer(('127.0.0.1',0),ExtendedAPI)
    t=Thread(target=server.serve_forever,daemon=True);t.start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        rows=asyncio.run(asyncio.wait_for(invoke(base,False),timeout=100))
        rows+=asyncio.run(asyncio.wait_for(invoke(base,True),timeout=100))
    finally:
        server.shutdown();server.server_close()
    validate(rows)
    out=BASE/'results';out.mkdir(exist_ok=True)
    (out/'POLICY.json').write_text(json.dumps({'status':'PASS','cases':rows},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':'PASS','observations':[
        {k:x[k] for k in ('case','masked','is_error','contains_canary','truncated','structured')}
        for x in rows]},indent=2))
if __name__=='__main__':main()
