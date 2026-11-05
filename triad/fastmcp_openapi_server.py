"""Actual FastMCP 4.1.6 from_openapi server. Synthetic local-only API."""
import json
import sys
from fastmcp import FastMCP
import httpx2

assert len(sys.argv)==3
spec=json.loads(open(sys.argv[1],encoding='utf-8').read())
base=sys.argv[2]
assert base.startswith('http://127.0.0.1:')
client=httpx2.AsyncClient(base_url=base,follow_redirects=False,timeout=4)
server=FastMCP.from_openapi(openapi_spec=spec,client=client,
                            name='RISU independent synthetic OpenAPI test')
if __name__=='__main__':
    server.run(transport='stdio')
