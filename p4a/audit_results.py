"""Independent audit of the original ten-project denominator and source hashes.

A correctly reported unsupported or zero-finding project is NOT a test
failure. Audit fails only on dishonest/missing results or provenance.
"""
import hashlib,json
from pathlib import Path
import sys

BASE=Path(__file__).resolve().parent
FROZEN=json.loads((BASE/'FROZEN_PREREGISTRATION.json').read_text())
def git_blob(content):
    return hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest()
def audit(inputs:Path,out:Path):
    download=json.loads((inputs/'download_report.json').read_text())
    result=json.loads((out/'P4A_10_PROJECT_RESULTS.json').read_text())
    fixed=FROZEN['fixed_targets']
    assert len(fixed)==10 and len(result['projects'])==len(download['projects'])==10
    assert result['projects_in_denominator']==result['preregistered_project_count']==10
    assert result['product_version']=='0.9.6-experimental'
    pby={x['id']:x for x in result['projects']}
    dby={x['id']:x for x in download['projects']}
    assert len(pby)==len(dby)==10
    counts={}
    verified=recognized=posthoc_recognized=total_get=total_error=0
    for target in fixed:
        id=target['id'];p=pby[id];d=dby[id]
        assert p['repository']==target['repository']==d['repository']
        assert p['commit']==target['commit']==d['commit']
        assert p['source_file']==target['path']==d['path']
        assert p['source_git_blob_verified']==(d['download_status']=='VERIFIED')
        assert p['observed_runtime_mcp_calls']==p['external_consumer_calls']==0
        assert p['confirmed_consumer_contract_mismatch'] is False
        counts[p['qualification']]=counts.get(p['qualification'],0)+1
        posthoc=p.get('posthoc_explicit_file_path')
        if d['download_status']=='VERIFIED':
            assert posthoc and posthoc['status']=='SECONDARY_POSTHOC_NOT_PREREGISTERED'
            if posthoc['execution']=='COMPLETE':
                summary=posthoc.get('summary',{})
                assert summary['openapi_parsed'] in (0,1)
                posthoc_recognized+=int(summary['openapi_parsed']>0)
        if d['download_status']=='VERIFIED':
            file=inputs/id/target['path']
            raw=file.read_bytes()
            assert len(raw)==target['expected_bytes']
            assert git_blob(raw)==target['blob_sha1']
            assert hashlib.sha256(raw).hexdigest()==d['sha256']==p['source_sha256']
            assert d['actual_bytes']==len(raw)
            verified+=1
        else:
            assert p['qualification']=='FETCH_FAILED'
            assert not (inputs/id/target['path']).exists()
        if p.get('first_check'):
            a=p['first_check']
            assert a['execution']=='NONE' and a['network_requests']==0
            assert a['version']=='0.9.6-experimental'
            assert a['findings']>=0 and a['incomplete']>=0
        if p.get('static_summary'):
            st=p['static_summary']
            assert st['eligible_files']>=0 and st['incomplete_files']>=0
            assert st['openapi_parsed'] in (0,1)
            assert st['findings']==len(p.get('static_findings',[]))
            recognized+=int(st['openapi_parsed']>0)
        if 'declared_contract_inventory' in p:
            v=p['declared_contract_inventory']
            assert v['kind']=='EXTERNAL_OPENAPI_DECLARATIONS_ONLY'
            assert not v['actual_MCP_call_executed']
            assert not v['real_consumer_source_examined']
            assert not v['confirmed_consumer_contract_mismatch']
            assert 0<=v['get_with_any_error_or_default']<=v['get_operations']<=v['paths_total']
            assert 0<=v['get_with_json_error_response_content']<=v['get_operations']
            total_get+=v['get_operations']
            total_error+=v['get_with_any_error_or_default']
    assert result['qualification_counts']==counts
    assert result['verified_source_count']==verified
    assert result['static_recognized_projects']==recognized
    assert result['posthoc_direct_path_recognized_projects']==posthoc_recognized
    assert result['posthoc_arm_can_change_primary_denominator'] is False
    assert result['total_declared_GET_operations_in_parsed_specs']==total_get
    assert result['total_declared_GETs_with_error_or_default']==total_error
    assert result['confirmed_real_consumer_mismatches']==0
    assert result['independent_developer_onboarding_measured'] is False
    assert 'No vendor API' in result['claim_boundary']
    for name in ['FROZEN_PREREGISTRATION.json','fetch_frozen.py',
                 'run_offline.py','inventory.py']:
        assert (BASE/name).exists()
    audit={
        'schema':'risu-p4a-audit-v1',
        'status':'PASS','preregistered_and_accounted_for':10,
        'source_blob_identity_matches':verified,
        'static_recognized':recognized,
        'posthoc_direct_path_recognized':posthoc_recognized,
        'posthoc_does_not_reclassify_original_results':True,
        'static_not_recognized_or_failed':10-recognized,
        'new_confirmed_consumer_defects':0,
        'unaffiliated_developer_adoption':False,
        'original_denomination_preserved':True,
        'research_main_untouched':True,
        'spec_only_signals_not_promoted_to_bugs':True,
        'prereg_sha256':hashlib.sha256((BASE/'FROZEN_PREREGISTRATION.json').read_bytes()).hexdigest(),
        'results_sha256':hashlib.sha256((out/'P4A_10_PROJECT_RESULTS.json').read_bytes()).hexdigest()
    }
    (out/'INDEPENDENT_P4A_AUDIT.json').write_text(json.dumps(audit,indent=2)+'\n')
    print('RISU_P4A_INDEPENDENT_AUDIT_PASS',json.dumps(audit))

if __name__=='__main__':
    if len(sys.argv)!=3:
        raise SystemExit('Usage: audit_results.py INPUT_DIR RESULT_DIR')
    audit(Path(sys.argv[1]),Path(sys.argv[2]))
