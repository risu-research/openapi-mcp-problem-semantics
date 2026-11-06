"""Generate genuinely on-wire MCP SDK JSONRPC + actual loopback HTTP HAR.

Not an externally supplied user's recording: independent test capture, from
unmodified upstream MCP SDK, with a deliberately scripted faulty demo tool.
"""
import argparse,asyncio,json,os,sys
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from threading import Thread

HERE=Path(__file__).resolve().parent

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path=='/records/valid':status=200;body={'id':'valid','state':'ready','count':7}
        elif self.path=='/records/missing':status=404;body={'code':'record_missing','message':'No such record'}
        else:status=400;body={'code':'invalid_path'}
        data=json.dumps(body,separators=(',',':')).encode()
        self.server.captures.append({'request':{'method':'GET','url':'http://127.0.0.1:'+str(self.server.server_port)+self.path,'headers':[]},
          'response':{'status':status,'headers':[{'name':'Content-Type','value':'application/json'}],
             'content':{'mimeType':'application/json','text':data.decode()},'bodySize':len(data)}})
        self.send_response(status);self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def log_message(self,*args):pass

def reject_dupes(pairs):
    obj={}
    for k,v in pairs:
        if k in obj:raise ValueError('duplicate JSON key')
        obj[k]=v
    return obj

async def generate(out):
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    out.mkdir(exist_ok=True,parents=True)
    proxy_log=out/'mcp.jsonl'
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    server.captures=[]
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    base='http://127.0.0.1:'+str(server.server_port)
    try:
        params=StdioServerParameters(command=sys.executable,args=['-B',str(HERE/'recording_proxy.py'),str(proxy_log),str(HERE/'developer_server.py'),base],
            env={k:v for k,v in os.environ.items() if k in ('PATH','HOME','TMPDIR','LANG','LC_ALL')})
        async with stdio_client(params) as (read,write):
          async with ClientSession(read,write) as session:
            await session.initialize()
            tools=await session.list_tools()
            assert 'fetch_record' in [x.name for x in tools.tools]
            for case in ('valid','missing'):
                result=await session.call_tool('fetch_record',{'record_id':case})
                assert len(result.content)==1
        wire=[json.loads(l,object_pairs_hook=reject_dupes) for l in proxy_log.read_text().splitlines() if l.strip()]
        calls=[x for x in wire if x.get('method')=='tools/call']
        assert len(calls)==2,calls
        assert [x['params']['arguments']['record_id'] for x in calls]==['valid','missing']
        assert len(server.captures)==2,server.captures
        pairing={'schema':'risu-explicit-capture-pairing-v1','pairs':[
          {'case_id':'SDK_NATIVE_200' if i==0 else 'SDK_NATIVE_404',
           'target':'external-sdk-testserver',
           'http_entry':i,'mcp_call_id':row['id'],'tool':'fetch_record'} for i,row in enumerate(calls)]}
        (out/'capture.har').write_text(json.dumps({'log':{'version':'1.2','creator':{'name':'RISU independent SDK capture test','version':'1'},'entries':server.captures}},indent=2)+'\n')
        (out/'pairs.json').write_text(json.dumps(pairing,indent=2)+'\n')
        print('REAL_SDK_NATIVE_RECORDING',len(calls),'tool calls,',len(server.captures),'HTTP requests,',len(wire),'raw MCP frames')
    except BaseException:
        stderr_file=out/'mcp.jsonl.server_stderr'
        if stderr_file.exists():
            print('NATIVE_CAPTURE_SERVER_STDERR',stderr_file.read_text(errors='replace')[-5000:],file=sys.stderr)
        raise
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);args=p.parse_args()
    asyncio.run(asyncio.wait_for(generate(args.out),timeout=30))