#!/usr/bin/env python3
"""Real FastMCP 4.1.6 server. Synthetic read-only test."""
from fastmcp import FastMCP

server=FastMCP('RISU v0.9 real FastMCP4 regression')
@server.tool()
def echo(value: str) -> dict:
    """Read-only echo of an inert synthetic string."""
    return {'value':value}
if __name__=='__main__':server.run(transport='stdio')
