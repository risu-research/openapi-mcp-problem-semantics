"""Independent synthetic developer's MCP server using original MCP SDK APIs.

It calls a *local* HTTP API; its faulty 404 mapping is deliberately scripted
for testing capture ingestion, not an alleged bug in any third-party project.
"""
import json, sys
from urllib.request import urlopen
from urllib.error import HTTPError
from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult,TextContent

assert len(sys.argv)==2
base=sys.argv[1]
assert base.startswith('http://127.0.0.1:')
app=FastMCP('Independent simulated developer native capture server')

@app.tool(name='fetch_record')
def fetch_record(record_id:str)->CallToolResult:
    if record_id not in ('valid','missing'):
        raise ValueError('unsupported fixture identifier')
    try:
        with urlopen(base+'/records/'+record_id,timeout=4) as response:
            status=response.status
            payload=json.loads(response.read())
    except HTTPError as exc:
        status=exc.code
        payload=json.loads(exc.read())
    if status==200:
        return CallToolResult(content=[TextContent(type='text',text=json.dumps(payload,separators=(',',':')))],
            isError=False,structuredContent=payload)
    # Intentional *fixture* defect, unrelated to any third-party SDK bug.
    return CallToolResult(content=[TextContent(type='text',text=json.dumps(payload,separators=(',',':')))],isError=False)

if __name__=='__main__':app.run(transport='stdio')