"""P4-J bounded synthetic local server; unchanged third-party MCP SDK transport."""
import json,sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult,TextContent

assert len(sys.argv)==2
base=sys.argv[1]
assert base.startswith('http://127.0.0.1:')
app=MCPServer('P4J causal witness synthetic local server')

@app.tool(name='fetch_record')
def fetch_record(record_id:str,risu_trace_token:str)->CallToolResult:
    if record_id not in ('valid','missing') or not 16<=len(risu_trace_token)<=128:
        raise ValueError('invalid bounded witness fixture')
    req=Request(base+'/records/'+record_id,headers={'X-RISU-Trace-Token':risu_trace_token})
    try:
        with urlopen(req,timeout=4) as response:
            status=response.status; payload=json.loads(response.read())
    except HTTPError as exc:
        status=exc.code;payload=json.loads(exc.read())
    if status==200:
        return CallToolResult(content=[TextContent(type='text',text=json.dumps(payload,separators=(',',':')))],
            isError=False,structuredContent=payload)
    # Deliberate error-flag defect for controlled local test, not third-party SDK defect.
    return CallToolResult(content=[TextContent(type='text',text=json.dumps(payload,separators=(',',':')))],isError=False)

if __name__=='__main__':app.run(transport='stdio')
