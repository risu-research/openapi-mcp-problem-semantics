#!/usr/bin/env python3
"""Unmodified FastMCP 4.1.6 OpenAPI provider through real stdio."""
import os
import httpx2
from fastmcp import FastMCP
from fastmcp.server.providers.openapi import RouteMap, MCPType

base=os.environ['RISU_TEST_URL']
spec={
  'openapi':'3.1.0',
  'info':{'title':'RISU localhost truncation fixture','version':'1.0.0'},
  'servers':[{'url':base}],
  'paths':{'/cases/{id}':{'get':{
    'operationId':'get_case',
    'parameters':[{'name':'id','in':'path','required':True,'schema':{'type':'string'}}],
    'responses':{
      '200':{'description':'Success','content':{'application/json':{'schema':{'type':'object','additionalProperties':True}}}},
      '409':{'description':'Conflict','content':{'application/problem+json':{'schema':{'type':'object','additionalProperties':True}}}},
      '422':{'description':'Validation','content':{'application/problem+json':{'schema':{'type':'object','additionalProperties':True}}}}
    }
  }}}
}
client=httpx2.AsyncClient(base_url=base,timeout=7,follow_redirects=False)
mcp=FastMCP.from_openapi(openapi_spec=spec,client=client,
    name='RISU Real FastMCP 4.1.6 Error Truncation Test',
    route_maps=[RouteMap(methods=['GET'],mcp_type=MCPType.TOOL)])
if __name__=='__main__': mcp.run(transport='stdio')
