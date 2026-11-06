"""Independent audit of third-party pinned original VCR evidence claims. No RISU Probe import."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parent
FROZEN=json.loads((ROOT/'FROZEN_SOURCES.json').read_text())

def gitblob(b):
    return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()

def verify(r,files,cache,full=True):
    assert r['schema']=='risu-p4m-original-third-party-network-artifact-audit-v1'
    assert r['frozen_sources_sha256']==hashlib.sha256((ROOT/'FROZEN_SOURCES.json').read_bytes()).hexdigest()
    assert r['source_count']==len(files)==5
    cfg=FROZEN['original_replay']
    for i,(a,b) in enumerate(zip(cfg['files']+cfg['source_code'],files)):
        assert a['path']==b['source_path'] and a['git_blob_sha1']==b['git_blob_sha1']
        assert len(b['sha256'])==64 and b['size_bytes']>0
        if full:
            raw=(cache/b['cache_name']).read_bytes()
            assert gitblob(raw)==a['git_blob_sha1']
            assert hashlib.sha256(raw).hexdigest()==b['sha256']
            assert len(raw)==b['size_bytes']
    cases=r['third_party_original_cassettes']
    assert len(cases)==2
    for i,c in enumerate(cases):
        assert c['id']==cfg['files'][i]['id']
        assert c['origin']=='ORIGINAL_REDACTED_EXTERNAL_VCR'
        assert c['recorded_upstream_http_status']==200
        assert c['recorded_application_status_code']==cfg['files'][i]['application_status_code']
        assert c['mcp_tools_call_wire_frame_recorded'] is False
        assert c['mcp_isError_recorded'] is False
        assert c['api_http_non2xx_error'] is False
        assert c['causal_upstream_to_final_mcp_wire_confirmed'] is False
        assert c['request_path_matches_original_third_party_test'] is True
        assert c['original_git_blob_sha1']==cfg['files'][i]['git_blob_sha1']
        assert c['application_level_not_found']==(i==1)
        assert c['upstream_recorded_in_mcp_dispatch_test']==(i==0)
        if full:
            v=yaml.safe_load((cache/'item_'+str(i)).read_text(encoding='utf-8-sig'))
            upstream=[x for x in v['interactions'] if x['request']['method']=='GET']
            assert len(upstream)==1
            response=upstream[0]['response']
            assert response['status']['code']==200
            app=json.loads(response['body']['string'])['result']
            assert app['statusCode']==c['recorded_application_status_code']
    assert r['externally_original_recorded_http_success']==1
    assert r['externally_original_recorded_application_not_found']==1
    assert r['original_mcp_dispatch_test_with_recorded_http_success']==1
    assert r['original_mcp_dispatch_test_with_recorded_http_application_error']==0
    assert r['original_full_wire_http_to_mcp_success']==0
    assert r['original_full_wire_http_to_mcp_error']==0
    assert r['field_fpr'] is None
    other=r['unrelated_independent_ci_artifact']
    assert other['repository']=='KryptosAI/mcp-observatory'
    assert other['workflow_run_id']==42245080723
    assert other['artifact_id']==13517149890
    assert other['contains_observed_rest_api_upstream_for_same_mcp_tool_call'] is False
    assert other['may_be_joined_with_jpo_recordings'] is False
    return True

def mutation_controls(r,f,c):
    mutations={
        'fabricate_full_success':lambda x:x.update(original_full_wire_http_to_mcp_success=1),
        'fabricate_full_error':lambda x:x.update(original_full_wire_http_to_mcp_error=1),
        'treat_logical_107_as_HTTP_error':lambda x:x['third_party_original_cassettes'][1].update(api_http_non2xx_error=True),
        'treat_direct_client_as_MCP':lambda x:x.update(original_mcp_dispatch_test_with_recorded_http_application_error=1),
        'fabricate_error_isError':lambda x:x['third_party_original_cassettes'][1].update(mcp_isError_recorded=True),
        'invent_FPR':lambda x:x.update(field_fpr=0.0),
        'join_unrelated_MCP_CI':lambda x:x['unrelated_independent_ci_artifact'].update(may_be_joined_with_jpo_recordings=True),
        'change_external_source_blob':lambda x:x['third_party_original_cassettes'][0].update(original_git_blob_sha1='0'*40),
        'mark_success_case_no_dispatch':lambda x:x['third_party_original_cassettes'][0].update(upstream_recorded_in_mcp_dispatch_test=False)
    }
    caught=[]
    for name,fn in mutations.items():
        x=copy.deepcopy(r);fn(x)
        try:verify(x,f,c,full=False)
        except (AssertionError,ValueError,KeyError,TypeError):caught.append(name)
        else:raise AssertionError('UNCHECKED_FALSE_EVIDENCE:'+name)
    return caught

if __name__=='__main__':
    a=argparse.ArgumentParser()
    a.add_argument('--out',type=Path,default=ROOT/'results')
    args=a.parse_args()
    r=json.loads((args.out/'qualified_originals.json').read_text())
    files=json.loads((args.out/'source_inventory.json').read_text())
    cache=args.out/'private_original_network_recordings_DO_NOT_PUBLISH'
    assert verify(r,files,cache)
    mutations=mutation_controls(r,files,cache)
    assert len(mutations)==9
    receipt={'status':'PASS','source_bytes_sha_verified':len(files),
      'externally_recorded_success_original':1,'externally_recorded_logical_not_found_original':1,
      'mcp_dispatch_function_call_with_original_HTTP_success':1,
      'complete_raw_wire_http_mcp_success':0,'complete_raw_wire_http_mcp_error':0,
      'field_fpr':None,'adversarial_false_evidence_cases_detected':mutations}
    (args.out/'independent_audit.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print('P4M_INDEPENDENT_AUDIT_PASS',json.dumps(receipt,sort_keys=True))
