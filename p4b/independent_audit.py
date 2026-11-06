"""Independent P4-B audit: exact source blobs, both product versions and
honest 10-project denominators. No external API access, no code execution.
"""
from pathlib import Path
import hashlib,json,sys
from p4a.audit_results import git_blob

ROOT=Path(__file__).resolve().parents[1]
FREEZE=json.loads((ROOT/'p4a'/'FROZEN_PREREGISTRATION.json').read_text())
def read(p):return json.loads(p.read_text(encoding='utf-8'))

def audit(inputs,out):
    baseline=read(out/'baseline_v096'/'P4A_10_PROJECT_RESULTS.json')
    candidate=read(out/'patched_v097'/'P4A_10_PROJECT_RESULTS.json')
    paired=read(out/'P4B_PAIRED_VERDICT.json')
    download=read(inputs/'download_report.json')
    assert paired['not_a_new_blind_test'] is True
    assert paired['original_first_round_result_immutable'] is True
    assert paired['both_arms_same_git_blob'] is True
    assert baseline['product_version']=='0.9.6-experimental'
    assert candidate['product_version']=='0.9.7-experimental'
    assert len(paired['projects'])==len(baseline['projects'])==len(candidate['projects'])==10
    assert baseline['static_recognized_projects']==1,baseline['static_recognized_projects']
    fixed=FREEZE['fixed_targets']
    assert len(fixed)==10 and len({x['repository'] for x in fixed})==10
    initial={x['id']:x for x in baseline['projects']}
    updated={x['id']:x for x in candidate['projects']}
    paired_items={x['id']:x for x in paired['projects']}
    downloads={x['id']:x for x in download['projects']}
    assert set(initial)==set(updated)==set(paired_items)==set(downloads)=={
      x['id'] for x in fixed}
    new_count=0;source_verified=0
    for frozen in fixed:
        id=frozen['id'];b=initial[id];c=updated[id];p=paired_items[id]
        d=downloads[id]
        assert b['repository']==c['repository']==p['repository']==frozen['repository']
        assert b['commit']==c['commit']==p['source_commit']==frozen['commit']
        assert d['download_status']=='VERIFIED'
        file=inputs/id/frozen['path']
        raw=file.read_bytes()
        assert len(raw)==frozen['expected_bytes']
        assert git_blob(raw)==frozen['blob_sha1']
        assert hashlib.sha256(raw).hexdigest()==b['source_sha256']==c['source_sha256']==p['sha256']
        source_verified+=1
        assert c['observed_runtime_mcp_calls']==c['external_consumer_calls']==0
        assert not c['confirmed_consumer_contract_mismatch']
        assert b['declared_contract_inventory']==c['declared_contract_inventory']
        assert c['inventory_execution']=='COMPLETE'
        assert c['inventory_status']=='PARSED'
        assert c['scan_execution']=='COMPLETE', (id,c.get('scan_execution'))
        assert c['first_check_execution']=='COMPLETE', (id,c.get('first_check_execution'))
        assert c['first_check']['version']=='0.9.7-experimental'
        assert c['first_check']['execution']=='NONE' and c['first_check']['network_requests']==0
        current=c['static_summary'].get('openapi_parsed',0)>0
        assert current==p['v097']['recognized']
        old=b['static_summary'].get('openapi_parsed',0)>0
        assert old==p['v096']['recognized']
        if old:assert current,'baseline project regressed'
        new_count+=int(current)
    assert paired['candidate_auto_recognized']==candidate['static_recognized_projects']==new_count
    assert paired['main_baseline_auto_recognized']==1
    assert paired['change_in_recognized_projects']==new_count-1
    assert paired['goal_reached']==(new_count>=paired['a_priori_release_candidate_goal_recognized'])
    assert paired['zero_candidate_project_regressions'] is True
    assert paired['newly_verified_real_consumer_contract_defects']==0
    assert paired['actual_sdk_or_mcp_runtime_calls']==0
    audit={
        'status':'PASS',
        'schema':'risu-p4b-independent-audit-v1',
        'same_ten_original_git_commits_and_blobs':source_verified,
        'v096_original_auto_recognized':1,
        'v097_updated_auto_recognized':new_count,
        'v097_goal_8_of_10':new_count>=8,
        'all_evidence_recomputed':True,
        'baseline_no_regression':True,
        'no_unverified_real_defect_claim':True,
        'prereg_sha256':hashlib.sha256((ROOT/'p4a'/'FROZEN_PREREGISTRATION.json').read_bytes()).hexdigest(),
        'paired_report_sha256':hashlib.sha256((out/'P4B_PAIRED_VERDICT.json').read_bytes()).hexdigest(),
        'technical_success_vs_market_success':'scanner coverage does not establish demand or real downstream failure'}
    (out/'P4B_INDEPENDENT_AUDIT.json').write_text(json.dumps(audit,indent=2)+'\n')
    print('RISU_P4B_INDEPENDENT_AUDIT_PASS',json.dumps(audit),flush=True)

if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit('Usage: independent_audit.py VERIFIED_INPUTS OUTPUT')
    audit(Path(sys.argv[1]),Path(sys.argv[2]))
