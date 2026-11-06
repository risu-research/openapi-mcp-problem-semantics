"""Independent, fail-closed audit of synthetic three-project qualification.

A green workflow must guarantee actual tool calls, not merely successful imports.
"""
from pathlib import Path
import hashlib
import json
import sys
import time

base=Path(sys.argv[1] if len(sys.argv)>1 else 'results')
p=base/'THREE_PROJECTS_SUMMARY.json'
report=json.loads(p.read_text(encoding='utf-8'))
assert report['status']=='PASS'
assert report['network']=='Docker --network none'
assert report['fixture']=='SYNTHETIC_GET_ONLY'
assert len(report['projects'])==3
assert report['counterfactual_rejections']==12
assert sum(report['calibrated_summary'].values())==12
assert sum(report['decision_summary'].values())==12
assert report['decision_summary']['FAIL']==3, 'CNOE error-flag loss must remain a confirmed failure'
assert report['consumer_divergent_cases']>=4
assert report['consumer_summary']['json-text-data']>=4
assert report['calibrated_summary'].get('EXACT_JSON_TEXT',0)>=4
assert report['calibrated_summary'].get('EXACT_MACHINE',0)>=2
assert {r['project'] for r in report['projects']}=={'cnoe','fastmcp','mcpgen'}
assert report['pinned_projects']=={
    'cnoe':'8c2b065497cf32ecbb7cf7e28dad3a99c6706c3f',
    'mcpgen':'30ee7cb9c2e923ce901e788b0d911f6547772866',
    'fastmcp':'4.1.6','mcp':'2.3.0'}
assert set(report['reference_controls'].values())=={'PRESERVED'}
assert len(report['original_product_sha256'])==64
for target in report['projects']:
    assert target['version']=='0.9.4-experimental'
    assert target['execution']=='REAL_LOCALHOST_HTTP_AND_EXTERNAL_MCP'
    assert target['first_diagnosis_under_ten_minutes_after_dependencies_ready'] is True
    assert 0 < target['seconds_after_dependencies_ready'] < 600
    assert target['unexpected_http_requests']==0
    assert target['http_get_count']==12
    assert target['observed_loss_count']>=1
    assert target['counterfactual_rejections']==4
    assert len(target['cases'])==4
    assert sorted(row['status'] for row in target['cases'])==[200,400,409,422]
    for row in target['cases']:
        assert row['verdict'] in ('PRESERVED','LOSS','LOSS_AND_INVENTED')
        ev=row['evidence_v1']
        d=row['decision_v1']
        w=row['witness_v1']
        assert d['schema']=='risu-decision-v1' and d['policy']=='calibrated'
        assert d['outcome'] in ('PASS','REVIEW','FAIL','DEFERRED','NOT_APPLICABLE')
        assert d['legacy_verdict']==row['verdict']
        assert w['schema']=='risu-consumer-witness-v1'
        assert w['required_fields']==1
        assert set(w['models'])=={'structured-only','json-text-data'}
        for reading in w['models'].values():
            assert reading['outcome'] in ('PASS','FAIL')
            assert 0<=reading['exact_fields']<=reading['required_fields']==1
            assert reading['error_flag_checked'] is True
        assert ev['schema']=='risu-evidence-v1'
        assert ev['scope']=='FULL_JSON_BODY'
        assert ev['body_loss_claim'] in ('NO_EXACT_INFORMATION_LOSS_PROVEN','OBSERVED_TRUNCATED_PREVIEW')
        assert ev['body_recovery'] in ('EXACT_MACHINE','EXACT_JSON_TEXT','PROVEN_TRUNCATED_PREVIEW',
                                      'UNVERIFIED_TEXT','NO_EXACT_CARRIER_OBSERVED')
        # CNOE adapter summary intentionally omits raw hashes; its earlier
        # matrix is derived from actual product collect and validated by fixture.
        if target['project']!='cnoe':
            assert len(row['source_sha256'])==64
            assert len(row['mcp_sha256'])==64
    if target['project'] in ('cnoe','fastmcp'):
        assert [row['verdict'] for row in target['cases'] if row['status']==200]==['PRESERVED']
        assert [row['evidence_v1']['body_recovery'] for row in target['cases'] if row['status']==200]==['EXACT_MACHINE']
        assert all(row['verdict'] in ('LOSS','LOSS_AND_INVENTED') for row in target['cases'] if row['status']>=400)
    if target['project']=='mcpgen':
        assert all(row['verdict']=='LOSS' for row in target['cases']), 'legacy strict carrier verdict preserved'
        for row in target['cases']:
            ev=row['evidence_v1']
            assert ev['body_recovery']=='EXACT_JSON_TEXT',(row,ev)
            assert ev['envelope_path']=='/data',(row,ev)
            assert ev['http_status']=='TEXT_STATUS_RECOVERABLE',(row,ev)
            assert ev['machine_carrier']=='NONE_CERTIFIED',(row,ev)
            assert row['decision_v1']['outcome']=='REVIEW'
            assert row['witness_v1']['divergent_outcomes'] is True
            assert row['witness_v1']['models']['structured-only']['outcome']=='FAIL'
            assert row['witness_v1']['models']['json-text-data']['outcome']=='PASS'
start=int((base/'begin_unix.txt').read_text())
finish=int((base/'end_unix.txt').read_text())
assert 0<finish-start<600, f'clean setup and three probes exceeded ten minutes: {finish-start}s'
meta={'audit':'PASS','elapsed_total_including_dependency_image_build_seconds':finish-start,
      'per_project_execution_seconds':{x['project']:x['seconds_after_dependencies_ready']
                                      for x in report['projects']},
      'summary_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
      'checked_program_source_sha256':report['original_product_sha256'],
      'three_actual_external_implementations':True,
      'counterfactual_rejections':report['counterfactual_rejections'],
      'calibrated_summary':report['calibrated_summary'],
      'decision_summary':report['decision_summary'],
      'consumer_summary':report['consumer_summary'],
      'consumer_divergent_cases':report['consumer_divergent_cases'],
      'scope':'synthetic loopback GET only, no user workload'}
(base/'INDEPENDENT_AUDIT.json').write_text(json.dumps(meta,indent=2)+'\n')
print('THREE_PROJECTS_INDEPENDENT_AUDIT_PASS',meta)
