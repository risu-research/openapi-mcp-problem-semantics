#!/usr/bin/env python3
"""Actual v0.9 RISU MCPClient against three real distinct server implementations.

Real SDK2 and FastMCP4 are installed in a pinned *separate* virtualenv during
Docker image build. The runtime has no network access or credentials.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys

PRODUCT=Path('/opt/risu/product')
sys.path.insert(0,str(PRODUCT))
from risu_probe import MCPClient, ProbeError, VERSION
assert VERSION=='0.9.0-experimental',VERSION

SERVER_ROOT=Path('/opt/risu/ci/servers')
OUT=Path('/results/MULTI_SERVER_TRANSPORT.json')
PYTHON=Path('/opt/modern/bin/python')

def main():
    assert PYTHON.is_file(), 'modern SDK/FastMCP runtime not installed'
    versions=json.loads(subprocess.check_output([str(PYTHON),'-c',
        "import importlib.metadata,json; print(json.dumps({x:importlib.metadata.version(x) for x in ('mcp','fastmcp','fastmcp-slim')}))"],text=True,timeout=20))
    assert versions=={'mcp':'2.3.0','fastmcp':'4.1.6','fastmcp-slim':'4.1.6'},versions
    assert PYTHON.absolute()!=PYTHON.resolve(), 'venv launcher unexpectedly dereferenced'
    targets=[('official-sdk2',str(PYTHON),str(SERVER_ROOT/'sdk2_echo_server.py'),'modern'),
             ('fastmcp-4.1.6',str(PYTHON),str(SERVER_ROOT/'fastmcp4_echo_server.py'),'modern'),
             ('stdlib-legacy',sys.executable,str(SERVER_ROOT/'legacy_echo_server.py'),'legacy')]
    cases=[]
    for target,exe,source,expected in targets:
        for mode in (expected,'auto'):
            with MCPClient([exe,'-u',source],protocol=mode) as client:
                assert client.protocol==expected,(target,mode,client.protocol)
                catalog=client.list_tools_catalog()
                assert 'echo' in catalog and isinstance(catalog['echo'].get('inputSchema'),dict),(target,catalog)
                value='RISU_SYNTHETIC_ECHO_'+target.replace('-','_')+'_'+mode
                raw=client.call('echo',{'value':value})
                assert raw.get('isError') is False,(target,raw)
                assert raw.get('structuredContent')=={'value':value},(target,raw)
                cases.append({'target':target,'requested_mode':mode,
                              'negotiated_mode':client.protocol,'result':'PRESERVED',
                              'tool':'echo','synthetic_value':value})
    rejected=False
    try:
        with MCPClient([sys.executable,'-u',str(SERVER_ROOT/'legacy_echo_server.py')],protocol='modern'):
            pass
    except ProbeError:
        rejected=True
    assert rejected,'modern mode unexpectedly downgraded to legacy'
    result={'status':'PASS','product_version':VERSION,'pinned_versions':versions,'targets':3,'cases_passed':len(cases),
            'cases':cases,'explicit_modern_to_legacy_rejected':rejected,
            'virtualenv_symlink_preserved':True,'network':'disabled by Docker',
            'claim_boundary':'Actual MCPClient, real SDK 2.3.0 and FastMCP 4.1.6. Only echo tool; not a whole protocol conformance claim.'}
    OUT.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    OUT.chmod(0o644)
    print('REAL MULTI-SERVER REGRESSION PASS',len(cases),'calls',versions,flush=True)
if __name__=='__main__':main()
