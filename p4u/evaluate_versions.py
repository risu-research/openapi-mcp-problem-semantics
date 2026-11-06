"""Compare REAL published MCP output schemas without inventing policy or loss."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'p4t'))
from risu_contract_history import create_snapshot, diff_snapshots, timeline, _write

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())

def evaluate(root:Path):
    versions=['2026.10.19','2026.11.4']
    captures={v:root/v for v in versions}
    for version,where in captures.items():
        info=read(where/'capture_manifest.json')
        assert info['version']==version and info['server_reported_version']==version
        assert info['actual_mcp_stdio_wire'] is True and info['real_tool_calls']>=2
        for key,file in [('wire_sha256','mcp_stdio_wire.jsonl'),('tools_list_sha256','tools_list.json'),('tool_calls_sha256','tool_calls.json')]:
            assert info[key]==sha(where/file),(version,key)
        listing=read(where/'tools_list.json')
        assert listing['id']==2 and listing['jsonrpc']=='2.0'
        assert any(t['name']=='convert_time' for t in listing['result']['tools'])
    comparisons={}
    for tool in ('convert_time','get_current_time'):
        old=create_snapshot(str(captures[versions[0]]/'tools_list.json'),None,versions[0],tool)
        tmp=root/f'{tool}_old.snapshot.json';_write(str(tmp),old)
        new=create_snapshot(str(captures[versions[1]]/'tools_list.json'),None,versions[1],tool,str(tmp))
        later=root/f'{tool}_new.snapshot.json';_write(str(later),new)
        diff=diff_snapshots(old,new)
        _write(str(root/f'{tool}.diff.json'),diff)
        t=timeline([str(tmp),str(later)])
        assert t['verified_hash_links']==1
        assert old['source_kind']==new['source_kind']=='recorded-tools-list'
        assert old['operator_policy'] is None and new['operator_policy'] is None
        assert diff['operator_policy_events']==[]
        comparisons[tool]={'diff':diff['summary'],'events':diff['publisher_schema_events'],
            'timeline_hash_links':t['verified_hash_links']}
    current=comparisons['convert_time']['events']
    later=[x for x in current if x['path']=='/later_occurrence' and x['kind']=='NEW_OPTIONAL_FIELD']
    if len(later)!=1:raise RuntimeError('Expected actual optional later_occurrence schema addition: '+repr(current))
    prev=read(captures[versions[0]]/'tools_list.json')['result']['tools']
    nxt=read(captures[versions[1]]/'tools_list.json')['result']['tools']
    pmap={x['name']:x for x in prev};nmap={x['name']:x for x in nxt}
    new_tools=sorted(nmap.keys()-pmap.keys());removed_tools=sorted(pmap.keys()-nmap.keys())
    if 'get_time_ago' not in new_tools:raise RuntimeError('Expected actual newly published get_time_ago tool')
    inputs=[]
    for tool in sorted(pmap.keys()&nmap.keys()):
        a=pmap[tool].get('inputSchema',{});b=nmap[tool].get('inputSchema',{})
        ra=set(a.get('required',[]));rb=set(b.get('required',[]))
        for field in sorted(ra-rb):inputs.append({'tool':tool,'kind':'INPUT_REQUIRED_TO_OPTIONAL','field':field})
        for field in sorted(rb-ra):inputs.append({'tool':tool,'kind':'INPUT_OPTIONAL_TO_REQUIRED','field':field})
    assert {'get_current_time::timezone','convert_time::source_timezone','convert_time::target_timezone'} <= {x['tool']+'::'+x['field'] for x in inputs if x['kind']=='INPUT_REQUIRED_TO_OPTIONAL'}
    call_changes={}
    for tool in ('get_current_time','convert_time'):
        old=read(captures[versions[0]]/'tool_calls.json')[tool]['response']['result']['structuredContent']
        new=read(captures[versions[1]]/'tool_calls.json')[tool]['response']['result']['structuredContent']
        call_changes[tool]={'old_keys':sorted(old),'new_keys':sorted(new),
                            'added_runtime_keys':sorted(new.keys()-old.keys()),
                            'removed_runtime_keys':sorted(old.keys()-new.keys())}
    assert call_changes['convert_time']['added_runtime_keys']==['later_occurrence']
    assert read(captures[versions[1]]/'tool_calls.json')['convert_time']['response']['result']['structuredContent']['later_occurrence'] is None
    report={
     'schema':'risu-p4u-external-real-release-drift-v1',
     'external_project':'modelcontextprotocol/servers / mcp-server-time',
     'pypi_published_versions':versions,
     'external_source_commits':{v:read(captures[v]/'capture_manifest.json')['original_source_commit'] for v in versions},
     'evidence_type':'actual separately installed published wheels, real MCP stdio JSON-RPC tools/list and safe tools/call',
     'captured_tools_list_directly':True,'fabricated_upgrade_schema':False,
     'operator_policies_supplied':False,'versioned_output_schema':comparisons,
     'tool_surface':{'added':new_tools,'removed':removed_tools},
     'input_requiredness_changes':inputs,'actual_call_structuredContent_keys':call_changes,
     'is_new_output_obligation':False,
     'interpretation':'later_occurrence is a new optional advertised output and a real runtime key, not a required duty; input requiredness and tool exposure changes are observed separately.',
     'cannot_conclude':['live upstream API behavior','provider contract breach','actual output loss in either release','operator policy change without operator policies','real-world developer breakage'],
    }
    _write(str(root/'p4u_real_release_report.json'),report)
    print('P4U_REAL_EXTERNAL_RELEASE_DRIFT_PASS',json.dumps({
     'output_schema_changes':comparisons['convert_time']['diff'],
     'added_tools':new_tools,'input_changes':inputs,'runtime_extra_key':call_changes['convert_time']['added_runtime_keys']},sort_keys=True),flush=True)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--captures',type=Path,required=True);a=p.parse_args();evaluate(a.captures)
