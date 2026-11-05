#!/usr/bin/env python3
"""Fresh CNOE OpenAPI generator -> real MCP stdio -> official SDK capture.
Synthetic loopback GET only; no production endpoints or credentials.
"""
from __future__ import annotations
import asyncio, hashlib, json, os, shutil, subprocess, sys, tempfile
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.request import Request, urlopen
from urllib.error import HTTPError

CASES=('normal','conflict','validation','generic')
CANARY='RISU_CURRENT_CODEGEN_TAIL_7c6ab16f'
COUNT=Counter()
def serial(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def digest(x):return hashlib.sha256(serial(x).encode('utf-8')).hexdigest()
def response(n):
    if n=='normal':return 200,'application/json',{'id':'normal','state':'open'}
    if n=='conflict':return 409,'application/problem+json',{
       'type':'https://example.test/problems/version-conflict','title':'Version conflict',
       'expected_version':'v2','current_version':'v3'}
    if n=='validation':return 422,'application/problem+json',{
       'type':'https://example.test/problems/validation','title':'Invalid items',
       'errors':[{'pointer':f'#/items/{i}/quantity','detail':'must be a positive integer'} for i in range(30)],
       'critical_tail':CANARY}
    if n=='generic':return 400,'application/json',{'error':'bad request','invalid_field':'id'}
    raise KeyError(n)

class API(BaseHTTPRequestHandler):
    def do_GET(self):
        name=self.path.removeprefix('/orders/')
        if name not in CASES:self.send_error(404);return
        COUNT[name]+=1
        code,mime,obj=response(name)
        raw=json.dumps(obj,ensure_ascii=False).encode('utf-8')
        self.send_response(code);self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def log_message(self,*args):pass

def get_http(base,n):
    try:r=urlopen(Request(base+'/orders/'+n,method='GET'),timeout=6)
    except HTTPError as e:r=e
    with r:return {'status':r.status,'content_type':r.headers.get('Content-Type',''),
                   'body':json.loads(r.read(128000).decode('utf-8'))}

def prepare(folder,base):
    folder.mkdir(parents=True,exist_ok=True)
    spec={'openapi':'3.1.0','info':{'title':'Risucheck API','version':'1.0.0'},
          'servers':[{'url':base}],
          'paths':{'/orders/{id}':{'get':{
              'operationId':'get_order','description':'Read a synthetic order by ID.',
              'parameters':[{'name':'id','in':'path','required':True,'schema':{'type':'string'}}],
              'responses':{
                 '200':{'description':'Success','content':{'application/json':{'schema':{'type':'object'}}}},
                 '409':{'description':'Conflict','content':{'application/problem+json':{'schema':{'type':'object'}}}},
                 '422':{'description':'Validation','content':{'application/problem+json':{'schema':{'type':'object'}}}},
                 '400':{'description':'Generic error','content':{'application/json':{'schema':{'type':'object'}}}}
              }}}}}
    (folder/'openapi.json').write_text(json.dumps(spec,indent=2)+'\n')
    (folder/'config.yaml').write_text("""title: risucheck
description: Synthetic read-only localhost API
author: RISU Institute
version: 0.0.0
license: Apache-2.0
python_version: 3.13
headers:
  Accept: application/json
poetry_dependencies: |
  python = ">=3.13,<4.0"
  httpx = ">=0.24.0"
  python-dotenv = ">=1.0.0"
  pydantic = ">=2.0.0"
  mcp = ">=2.0.0"
""")

async def invoke(base,server):
    from mcp import Client,StdioServerParameters
    env=dict(os.environ)
    env.update({'RISUCHECK_API_URL':base,'RISUCHECK_TOKEN':'synthetic-no-secret',
                'MCP_MODE':'stdio',
                'PYTHONPATH':str(server.parent.parent)+os.pathsep+env.get('PYTHONPATH','')})
    p=StdioServerParameters(command=os.environ.get('RISU_CNOE_GENERATOR_PYTHON',sys.executable),args=['-u',str(server)],env=env)
    async with Client(p) as client:
        listing=await client.list_tools()
        catalog={t.name:t for t in listing.tools}
        if 'get_order' not in catalog:
            raise RuntimeError('Missing generated get_order, catalog='+str(sorted(catalog)))
        schema=catalog['get_order'].input_schema
        print('Generated tool schema:',json.dumps(schema))
        if 'path_id' in schema.get('properties',{}):key='path_id'
        elif 'id' in schema.get('properties',{}):key='id'
        else:raise RuntimeError('Unknown input schema: '+str(schema))
        rows=[]
        for name in CASES:
            before=get_http(base,name)
            count=COUNT[name]
            raw=(await asyncio.wait_for(client.call_tool('get_order',{key:name}),timeout=25)
                ).model_dump(mode='json',by_alias=True,exclude_none=True)
            delta=COUNT[name]-count
            after=get_http(base,name)
            if before!=after:raise RuntimeError('Changing upstream source: '+name)
            if delta!=1:raise RuntimeError(f'No actual API call from generated MCP for {name}; delta={delta}')
            rows.append({'check':{'id':name,'tool':'get_order','http_path':'/orders/'+name,
                                   'mediated_http_requests':delta},
                         'source_sample':before,'mcp_sample':raw,
                         'source_sha256':digest(before),'mcp_sha256':digest(raw)})
        return rows,{'tool_names':sorted(catalog),'get_order_input_schema':schema}

def main():
    repo=Path(os.environ['RISU_CNOE_REPO']).resolve()
    sha=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
    out=Path(os.environ.get('RISU_CNOE_OUTPUT','cnoe-results')).resolve()
    out.mkdir(parents=True,exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),API)
    worker=Thread(target=server.serve_forever,daemon=True);worker.start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        with tempfile.TemporaryDirectory(prefix='risu-new-cnoe-') as tmp:
            root=Path(tmp); inp=root/'input';prepare(inp,base)
            generated=root/'output'
            command=[os.environ.get('RISU_CNOE_GENERATOR_PYTHON',sys.executable),'-m','openapi_mcp_codegen',
                     '--spec-file',str(inp/'openapi.json'),'--output-dir',str(generated),
                     '--log-level','warning']
            generator_env=dict(os.environ)
            generator_env['PATH']=str(Path(command[0]).parent)+os.pathsep+generator_env.get('PATH','')
            subprocess.run(command,check=True,timeout=180,cwd=root,env=generator_env)
            servers=[p for p in generated.rglob('server.py') if p.parent.name.startswith('mcp_')]
            if len(servers)!=1:raise RuntimeError('Unexpected generated servers: '+str(servers))
            # Archive the exact generated files and input spec for reproducibility.
            import hashlib as _hashlib
            import json as _json
            shutil.copy2(inp/'openapi.json', out/'SOURCE_OPENAPI.json')
            shutil.copy2(inp/'config.yaml', out/'GENERATOR_CONFIG.yaml')
            generated_hashes={str(p.relative_to(generated)):_hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in generated.rglob('*') if p.is_file()}
            (out/'GENERATED_SHA256.json').write_text(_json.dumps(generated_hashes,indent=2)+'\n')
            shutil.make_archive(str(out/'generated-code'),'zip',root_dir=generated)
            rows,catalog=asyncio.run(invoke(base,servers[0]))
    finally:server.shutdown();server.server_close()
    result={'status':'EXECUTED','generator':'cnoe-io/openapi-mcp-codegen',
            'generator_commit':sha,'generator_ref':'fresh main on run',
            'transport':'official MCP SDK stdio client -> generated server',
            'source':'synthetic localhost GET','api_request_counts':dict(COUNT),
            'catalog':catalog,'targets':[{'target':'cnoe-fresh-'+sha[:12],'checks':rows}]}
    (out/'cnoe-current-matrix.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('FRESH CNOE execution, commit',sha,'captures',len(rows))
    for row in rows:print(row['check']['id'],'HTTP',row['source_sample']['status'],'isError',row['mcp_sample'].get('isError'))

if __name__=='__main__':main()
