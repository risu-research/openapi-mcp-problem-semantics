"""Create an explicitly TEST-ONLY, trust-rooted cross-boundary witness.

The private key is generated for this test and never stored inside the capture
or distributed in the artifact. This is not an independently trusted customer
capture; it proves the P4-J witness verification mechanism with real MCP SDK I/O.
"""
import argparse,asyncio,base64,hashlib,json,os,secrets,sys,time
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from threading import Thread
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
HERE=Path(__file__).resolve().parent
SRC=HERE.parent/'src'
sys.path.insert(0,str(SRC))
from risu_causality import canonical,digest,sha_bytes,SCHEMA,TRUST,CALL_KIND

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        stamped=time.monotonic_ns()
        token=self.headers.get('X-RISU-Trace-Token')
        if self.path=='/records/valid':status=200;body={'id':'valid','state':'ready','count':7}
        elif self.path=='/records/missing':status=404;body={'code':'record_missing','message':'No such record'}
        else:status=400;body={'code':'invalid_path'}
        data=json.dumps(body,separators=(',',':')).encode()
        req={'method':'GET','url':'http://127.0.0.1:'+str(self.server.server_port)+self.path,
             'headers':[{'name':'X-RISU-Trace-Token','value':token}]}
        resp={'status':status,'headers':[{'name':'Content-Type','value':'application/json'}],
             'content':{'mimeType':'application/json','text':data.decode()},'bodySize':len(data)}
        self.send_response(status);self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        self.server.captures.append({'request':req,'response':resp})
        self.server.times.append({'token':token,'request_ns':stamped,'response_ns':time.monotonic_ns()})
    def log_message(self,*args):pass

async def generate(out,trust_out):
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    out.mkdir(exist_ok=True,parents=True)
    assert trust_out.resolve().parent!=out.resolve(), 'test trust store must be OUTSIDE capture directory'
    proxy_log=out/'mcp.jsonl'
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    server.captures=[];server.times=[]
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    base='http://127.0.0.1:'+str(server.server_port)
    tokens=[secrets.token_urlsafe(24) for _ in range(2)]
    try:
        params=StdioServerParameters(command=sys.executable,
          args=['-B',str(HERE/'recording_proxy.py'),str(proxy_log),str(HERE/'developer_server.py'),base],
          env={k:v for k,v in os.environ.items() if k in ('PATH','HOME','TMPDIR','LANG','LC_ALL')})
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                listing=await session.list_tools()
                assert 'fetch_record' in [x.name for x in listing.tools]
                for val,token in zip(('valid','missing'),tokens):
                    result=await session.call_tool('fetch_record',{'record_id':val,'risu_trace_token':token})
                    assert len(result.content)==1
        wire=[json.loads(x) for x in proxy_log.read_text().splitlines() if x.strip()]
        calls=[x for x in wire if x.get('method')=='tools/call']
        results=[x for x in wire if 'result' in x and x.get('id') in [c['id'] for c in calls]]
        assert len(calls)==len(results)==len(server.captures)==len(server.times)==2
        assert [x['params']['arguments']['risu_trace_token'] for x in calls]==tokens
        pairfile={'schema':'risu-explicit-capture-pairing-v1','pairs':[
            {'case_id':f'SDK_WITNESSED_{200 if i==0 else 404}',
             'target':'bounded-trusted-observer-demo','http_entry':i,
             'mcp_call_id':call['id'],'tool':'fetch_record'} for i,call in enumerate(calls)]}
        har={'log':{'version':'1.2','creator':{'name':'P4J bounded independent local test','version':'1'},
             'entries':server.captures}}
        (out/'capture.har').write_text(json.dumps(har,indent=2)+'\n')
        (out/'pairs.json').write_text(json.dumps(pairfile,indent=2)+'\n')
        events=[json.loads(x) for x in Path(str(proxy_log)+'.observed_events.jsonl').read_text().splitlines()]
        assert len([x for x in events if x['kind']=='MCP_REQUEST'])==2
        assert len([x for x in events if x['kind']=='MCP_RESPONSE'])==2
        links=[]
        for i,(call,token) in enumerate(zip(calls,tokens)):
            rid=call['id'];response=next(x for x in results if x['id']==rid)
            e0=next(x for x in events if x['kind']=='MCP_REQUEST' and x['id']==rid)
            e3=next(x for x in events if x['kind']=='MCP_RESPONSE' and x['id']==rid)
            e1={'kind':'HTTP_REQUEST','t_ns':server.times[i]['request_ns'],
                'sha256':digest(server.captures[i]['request'])}
            e2={'kind':'HTTP_RESPONSE','t_ns':server.times[i]['response_ns'],
                'sha256':digest(server.captures[i]['response'])}
            order=[e0,e1,e2,e3]
            assert all(order[j]['t_ns']<order[j+1]['t_ns'] for j in range(3)),('NONCAUSAL_ACTUAL_CLOCK_ORDER',order)
            assert e0['sha256']==digest(call) and e3['sha256']==digest(response)
            assert server.times[i]['token']==token
            links.append({'case_id':pairfile['pairs'][i]['case_id'],'http_entry':i,
              'mcp_call_id':rid,'tool':'fetch_record',
              'trace_token_sha256':sha_bytes(token.encode()),
              'events':[{'kind':kind,'sequence':event['t_ns'],'sha256':event['sha256']}
                        for kind,event in zip(CALL_KIND,order)]})
        statement={'schema':SCHEMA,'observer_kind':'BOUNDARY_RECORDER_V1',
          'issuer':'risu-p4j-ephemeral-test-recorder','session_id':secrets.token_hex(16),
          'file_sha256':{n:sha_bytes((out/n).read_bytes()) for n in ('capture.har','mcp.jsonl','pairs.json')},
          'links':links}
        key=Ed25519PrivateKey.generate()
        rawpub=key.public_key().public_bytes(encoding=serialization.Encoding.Raw,format=serialization.PublicFormat.Raw)
        signed=key.sign(canonical(statement))
        witness={**statement,'signature':{'algorithm':'Ed25519','key_id':'p4j-local-demo-ephemeral',
             'value_base64':base64.b64encode(signed).decode()}}
        (out/'causal_witness.json').write_text(json.dumps(witness,indent=2)+'\n')
        trust={'schema':TRUST,'trusted_recorders':[
           {'key_id':'p4j-local-demo-ephemeral','issuer':statement['issuer'],
            'observer_kind':'BOUNDARY_RECORDER_V1',
            'ed25519_public_key_base64':base64.b64encode(rawpub).decode()}]}
        trust_out.parent.mkdir(exist_ok=True,parents=True)
        trust_out.write_text(json.dumps(trust,indent=2)+'\n')
        print('P4J_REAL_SDK_WITNESSED',len(calls),'tools calls',len(server.captures),'local HTTP requests,',len(wire),'frames')
    finally:
        server.shutdown();server.server_close();thread.join(timeout=4)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--trust-out',type=Path,required=True)
    a=p.parse_args()
    asyncio.run(asyncio.wait_for(generate(a.out,a.trust_out),timeout=45))
