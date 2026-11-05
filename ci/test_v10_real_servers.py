"""Actual v0.9.1 MCPClient regression against pinned third-party MCP libraries.
No remote API, credentials, writes, or unsafe tool calls.
"""
import importlib.metadata
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'dist'/'risu_v09_source'))
from risu_probe import MCPClient, ProbeError, VERSION

assert VERSION=='0.9.1-experimental',VERSION
versions={name:importlib.metadata.version(name) for name in ('mcp','fastmcp','fastmcp-slim')}
assert versions=={'mcp':'2.3.0','fastmcp':'4.1.6','fastmcp-slim':'4.1.6'},versions

cases=[]
for name,script,protocol in (
    ('official-python-sdk','sdk2_echo_server.py','modern'),
    ('fastmcp','fastmcp4_echo_server.py','modern'),
    ('stdlib-legacy','legacy_echo_server.py','legacy')):
    for mode in (protocol,'auto'):
        path=ROOT/'ci'/'servers'/script
        with MCPClient([sys.executable,'-u',str(path)],protocol=mode) as client:
            assert client.protocol==protocol,(name,client.protocol)
            catalog=client.list_tools_catalog()
            assert 'echo' in catalog
            value='risu-091-'+name+'-'+mode
            got=client.call('echo',{'value':value})
            assert got.get('isError') is False,(name,mode,got)
            assert got.get('structuredContent')=={'value':value},(name,mode,got)
            cases.append({'server':name,'mode':mode,'status':'PASS'})
try:
    with MCPClient([sys.executable,'-u',str(ROOT/'ci'/'servers'/'legacy_echo_server.py')],protocol='modern'):
        raise AssertionError('modern mode must not downgrade')
except ProbeError:
    pass
print('REAL_SDK_AND_FASTMCP_PASS',json.dumps({'version':VERSION,'versions':versions,'cases':cases}))
