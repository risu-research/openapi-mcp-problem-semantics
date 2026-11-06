"""Strict paired v0.9.6-v0.9.7 source-compatibility experiment.

Identical exact pinned 10 inputs, unchanged v0.9.6 source and v0.9.7
scanner-only patched source, identical first-check/scan/inventory harness.
The frozen P4-A 1/10 and post-hoc 5/10 observations remain untouched.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
from p4a import run_offline

ROOT=Path(__file__).resolve().parents[1]

def _read(path):
    return json.loads(path.read_text(encoding='utf-8'))
def _write(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def run(inputs:Path,output:Path):
    output.mkdir(parents=True,exist_ok=True)
    results={}
    for label,source,version in (
        ('baseline_v096',ROOT/'dist'/'risu_v096_baseline','0.9.6-experimental'),
        ('patched_v097',ROOT/'dist'/'risu_v09_source','0.9.7-experimental'),
    ):
        assert (source/'risu_probe.py').is_file(),source
        run_offline.PRODUCT=source
        dest=output/label
        print('RISU_P4B_PAIRED_START',label,flush=True)
        run_offline.qualified(inputs,dest)
        report=dest/'P4A_10_PROJECT_RESULTS.json'
        value=_read(report)
        assert len(value['projects'])==10
        for item in value['projects']:
            if item.get('first_check'):
                assert item['first_check']['version']==version,(label,item['id'],item['first_check'])
        # The pre-existing measurement harness reports its original v0.9.6
        # identifier literally. Amend metadata only after asserting all 10
        # actual v0.9.7 product outputs, never modify their measurements.
        if label=='patched_v097':
            assert value['product_version']=='0.9.6-experimental'
            value['product_version']=version
            value['measurement_harness_reused_from_p4a']=True
            _write(report,value)
        else:
            assert value['product_version']==version
        results[label]=value
        print('RISU_P4B_PAIRED_COMPLETE',label,'recognized',value['static_recognized_projects'],
              flush=True)

    old=results['baseline_v096']
    new=results['patched_v097']
    a={x['id']:x for x in old['projects']}
    b={x['id']:x for x in new['projects']}
    assert len(a)==len(b)==10
    comparisons=[]
    for id in sorted(a):
        previous=a[id];current=b[id]
        assert previous['repository']==current['repository']
        assert previous['commit']==current['commit']
        assert previous['source_sha256']==current['source_sha256']
        assert previous['source_git_blob_verified']==current['source_git_blob_verified']
        assert previous['declared_contract_inventory']==current['declared_contract_inventory']
        comparisons.append({
            'id':id,'repository':previous['repository'],
            'source_commit':previous['commit'],'sha256':previous['source_sha256'],
            'v096':{
                'recognized':previous.get('static_summary',{}).get('openapi_parsed',0)>0,
                'qualification':previous['qualification'],
                'scanner_status':previous.get('static_status'),
                'first_check_status':previous.get('first_check',{}).get('status'),
                'first_check_elapsed_seconds':previous.get('first_check_elapsed_seconds'),
                'scan_elapsed_seconds':previous.get('full_scan_elapsed_seconds'),
            },
            'v097':{
                'recognized':current.get('static_summary',{}).get('openapi_parsed',0)>0,
                'qualification':current['qualification'],
                'scanner_status':current.get('static_status'),
                'first_check_status':current.get('first_check',{}).get('status'),
                'first_check_elapsed_seconds':current.get('first_check_elapsed_seconds'),
                'scan_elapsed_seconds':current.get('full_scan_elapsed_seconds'),
                'incomplete':current.get('static_incomplete',[]),
            }
        })
    n0=old['static_recognized_projects']
    n1=new['static_recognized_projects']
    result={
        'schema':'risu-p4b-paired-v1',
        'phase':'SAME_FROZEN_TEN_POSTHOC_REPAIR_EXPERIMENT',
        'not_a_new_blind_test':True,
        'baseline_product':'0.9.6-experimental',
        'candidate_product':'0.9.7-experimental',
        'preregistered_p4a_target_count':10,
        'both_arms_same_git_blob':True,
        'original_first_round_result_immutable':True,
        'main_baseline_auto_recognized':n0,
        'candidate_auto_recognized':n1,
        'change_in_recognized_projects':n1-n0,
        'a_priori_release_candidate_goal_recognized':8,
        'goal_reached':n1>=8,
        'zero_candidate_project_regressions':all(
            not row['v096']['recognized'] or row['v097']['recognized'] for row in comparisons),
        'actual_sdk_or_mcp_runtime_calls':0,
        'newly_verified_real_consumer_contract_defects':0,
        'first_use_by_independent_developers_tested':False,
        'claim_boundary':'Paired source-only offline scanner usability result; 10 original pinned inputs; no production/API/MCP tool calls, live consumer verification, independent developer use or observed loss.',
        'projects':comparisons,
    }
    _write(output/'P4B_PAIRED_VERDICT.json',result)
    print('RISU_P4B_PAIRED_OUTCOME',json.dumps({
       'before':n0,'after':n1,'goal_reached':result['goal_reached'],
       'zero_regressions':result['zero_candidate_project_regressions']}),flush=True)

if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit('Usage: paired_run.py VERIFIED_INPUTS OUTPUT')
    run(Path(sys.argv[1]),Path(sys.argv[2]))
