#!/usr/bin/env python3
"""Hand-written SDK 2 preserving reference: NOT a native OpenAPI converter."""
import json
import os
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen
from mcp.server import MCPServer
from mcp.types import CallToolResult, TextContent, TextResourceContents, EmbeddedResource

server=MCPServer('RISU SDK 2 Preservation Control')
base=os.environ['RISU_TEST_URL']
valid={'boundary-999','boundary-1000','boundary-1001','boundary-1600',
       'boundary-5000','validation-40','unicode-1600','success'}

@server.tool()
def get_case(id:str):
    """Read an explicitly whitelisted localhost test case."""
    if id not in valid: raise ValueError('Unexpected case ID')
    req=Request(base+'/cases/'+quote(id,safe=''),method='GET',
                headers={'Accept':'application/problem+json, application/json'})
    try: r=urlopen(req,timeout=7)
    except HTTPError as exc: r=exc
    with r:
        status=r.status
        mime=r.headers.get('Content-Type','').split(';')[0].strip().lower()
        body=json.loads(r.read(128000).decode('utf-8'))
    text=json.dumps(body,ensure_ascii=False,separators=(',',':'))
    meta={'org.risu.reference.source_http':{'observed_http_status':status,'content_type':mime}}
    if mime=='application/problem+json':
        resource=TextResourceContents(uri='data:application/problem+json,'+
            quote(text,safe=''),mime_type=mime,text=text)
        return CallToolResult(content=[EmbeddedResource(resource=resource)],is_error=True,_meta=meta)
    return CallToolResult(content=[TextContent(text=text)],structured_content=body,is_error=False,_meta=meta)

if __name__=='__main__': server.run()
