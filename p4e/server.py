"""Original FastMCP OpenAPI conversion path; no vendor endpoint is contacted."""
import json
import sys
import httpx2
from fastmcp import FastMCP
assert len(sys.argv)==3
specpath,base=sys.argv[1:]
assert base.startswith('http://127.0.0.1:') and base.count('/')==2,base
spec=json.loads(open(specpath,encoding='utf-8').read())
assert list(spec['paths'])==['/v2/usage']
assert set(spec['paths']['/v2/usage'])=={'get'}
client=httpx2.AsyncClient(base_url=base,follow_redirects=False,timeout=8)
mcp=FastMCP.from_openapi(openapi_spec=spec,client=client,name='RISU P4E bounded local DeepL replay')
if __name__=='__main__':mcp.run(transport='stdio')
