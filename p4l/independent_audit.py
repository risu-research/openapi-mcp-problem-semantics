"""Independent P4-L original third-party evidence audit and falsification controls."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import argparse

ROOT=Path(__file__).resolve().parent
FROZEN=json.loads((ROOT/'FROZEN_PROTOCOL.json').read_text())

def git_sha(b):
    return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()

def audit(report,manifest,raw_dir,check_files=True):
    assert report['schema']=='risu-p4l-independent-public-evidence-qualification-v1'
    assert report['frozen_protocol_sha256']==hashlib.sha256((ROOT/'FROZEN_PROTOCOL.json').read_bytes()).hexdigest()
    assert manifest and len(manifest)==len(FROZEN['sources'])==6
    assert report['source_count']==6
    assert report['distinct_external_repositories']==5
    assert len(set(x['repo'] for x in manifest))==5
    for expected,actual in zip(FROZEN['sources'],manifest):
        for field in ('id','repo','commit','path','kind'):
            assert expected[field]==actual[field],(field,expected['id'])
        assert expected['sha1']==actual['git_blob_sha1']
        assert len(actual['sha256'])==64
        if check_files:
            data=(raw_dir/expected['id']).read_bytes()
            assert git_sha(data)==expected['sha1']
            assert hashlib.sha256(data).hexdigest()==actual['sha256']
            assert len(data)==actual['bytes']
    c=report['verified_cases'];n=report['adjudicated_counts']
    assert len(c)==6
    mon=c['monark_same_recording_distinct_interface_normal_parity']
    assert mon['count']==1 and mon['level']=='TIER2_SEMANTIC_PARITY_NOT_CAUSAL'
    assert mon['mcp_step']!=mon['http_step']
    assert mon['same_arguments'] is True and mon['same_response_object'] is True
    assert mon['original_http_status_recorded'] is False
    assert 'distinct' in mon['why_not_tier1'].lower() or 'independently' in mon['why_not_tier1'].lower() or 'Both calls' in mon['why_not_tier1']
    err=c['monark_error_mcp_only']
    assert err['level']=='TIER3_ONE_SIDED_MCP_ERROR'
    assert err['count']>=1 and err['example_tool']=='gate'
    assert err['error_code']=='task_class_retired'
    assert err['http_mirror_error_same_call_recorded'] is False
    cisco=c['cisco_independent_recorded_mcp_calls']
    assert cisco['count']>=2
    assert cisco['level']=='TIER3_MCP_ONLY_WITH_PAIRED_MCP_REQUEST_RESPONSE'
    assert cisco['upstream_rest_http_recorded'] is False
    tyk=c['tyk_independent_converter_handler_test']
    assert tyk['count']==1 and tyk['on_wire_mcp_client_recorded'] is False
    assert tyk['raw_external_http_mcp_capture_committed'] is False
    meda=c['meda_independent_mcp_http_transport_trace']
    assert meda['count']>=5 and meda['rest_backend_source_proven'] is False
    ami=c['amiberry_independent_normal_and_error_two_interface_test']
    assert ami['success_and_error_parameterized'] is True
    assert ami['real_mcp_network_wire_traffic_recorded'] is False
    assert n['independent_external_causal_upstream_http_to_mcp_normal']==0
    assert n['independent_external_causal_upstream_http_to_mcp_error']==0
    assert n['independent_external_dual_surface_normal_parity']==1
    assert n['independent_external_recorded_mcp_error_without_http_peer']==err['count']
    assert n['verified_independent_true_negative_causal_pairs']==0
    assert n['field_false_positive_rate'] is None
    if check_files:
        t=json.loads((raw_dir/'monark_trace').read_text())
        a=next(x for x in t['steps'] if x.get('n')==mon['mcp_step'])
        b=next(x for x in t['steps'] if x.get('n')==mon['http_step'])
        assert a['surface']=='mcp' and b['surface']=='http'
        assert a['request']['params']['arguments']==b['request']['body']
        assert a['response']==b['response']
        assert 'status' not in b['response']
        assert any(x.get('surface')=='mcp' and x.get('response',{}).get('isError') is True for x in t['steps'])
        source=(raw_dir/'amiberry_semantic_parity_source').read_text()
        assert 'AsyncMock(return_value=expected)' in source
        assert 'httpx.ASGITransport' in source
    return {'status':'PASS','external_source_bytes_git_sha_verified':len(manifest),
            'tier1_causal_success':0,'tier1_causal_error':0,
            'tier2_same_run_two_interface_parity':1,
            'tier3_one_sided_error':err['count'],
            'field_fpr':None,'field_fpr_reason':'ZERO_ADJUDICATED_INDEPENDENT_TRUE_NEGATIVE_HTTP_TO_MCP_CAUSAL_PAIRS'}

def adversarial(report,manifest,raw):
    edits={
      'invent_causal_success':lambda z:z['adjudicated_counts'].update(independent_external_causal_upstream_http_to_mcp_normal=1),
      'invent_causal_error':lambda z:z['adjudicated_counts'].update(independent_external_causal_upstream_http_to_mcp_error=1),
      'fabricate_field_fpr':lambda z:z['adjudicated_counts'].update(field_false_positive_rate=0),
      'claim_monark_causal':lambda z:z['verified_cases']['monark_same_recording_distinct_interface_normal_parity'].update(level='TIER1_CAUSAL'),
      'claim_monark_http_status':lambda z:z['verified_cases']['monark_same_recording_distinct_interface_normal_parity'].update(original_http_status_recorded=True),
      'claim_error_http_peer':lambda z:z['verified_cases']['monark_error_mcp_only'].update(http_mirror_error_same_call_recorded=True),
      'claim_tyk_onwire':lambda z:z['verified_cases']['tyk_independent_converter_handler_test'].update(on_wire_mcp_client_recorded=True),
      'claim_meda_rest_backend':lambda z:z['verified_cases']['meda_independent_mcp_http_transport_trace'].update(rest_backend_source_proven=True),
      'claim_amiberry_wire':lambda z:z['verified_cases']['amiberry_independent_normal_and_error_two_interface_test'].update(real_mcp_network_wire_traffic_recorded=True)
    }
    caught=[]
    for name,change in edits.items():
        fake=copy.deepcopy(report);change(fake)
        try:audit(fake,manifest,raw,check_files=False)
        except (AssertionError,KeyError,TypeError,ValueError):caught.append(name)
        else:raise AssertionError('UNCATCHED_CLAIM_FORGERY:'+name)
    assert len(caught)==len(edits)
    return caught

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--results',type=Path,default=ROOT/'results')
    a=p.parse_args()
    report=json.loads((a.results/'qualification.json').read_text())
    manifest=json.loads((a.results/'provenance_manifest.json').read_text())
    raw=a.results/'private_originals_do_not_upload'
    outcome=audit(report,manifest,raw)
    outcome['adversarial_mutations_caught']=adversarial(report,manifest,raw)
    (a.results/'independent_audit.json').write_text(json.dumps(outcome,indent=2,sort_keys=True)+'\n')
    print('P4L_INDEPENDENT_SOURCE_AUDIT_PASS',json.dumps(outcome,sort_keys=True),flush=True)

if __name__=='__main__':main()
