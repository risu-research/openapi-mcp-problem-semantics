#!/usr/bin/env python3
"""Real official MCP Python SDK 2.3.0 server. Synthetic read-only test."""
from mcp.server import MCPServer
from mcp.types import CallToolResult,TextContent

server=MCPServer('RISU v0.9 real SDK2 regression')
@server.tool()
def echo(value: str):
    """Read-only echo of an inert synthetic string."""
    return CallToolResult(content=[TextContent(text=value)],structured_content={'value':value},is_error=False)
if __name__=='__main__':server.run()
