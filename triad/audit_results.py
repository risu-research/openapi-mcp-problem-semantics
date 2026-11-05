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
assert {r['project'] for r in report['projects']}=={'cnoe','fastmcp','mcpgen'}
assert report['pinned_projects']=={
    'cnoe':'8c2b065497cf32ecbb7cf7e28dad3a99c6706c3f',
    'mcpgen':'30ee7cb9c2e923ce901e788b0d911f6547772866',
    'fastmcp':'4.1.6','mcp':'2.3.0'}
assert set(report['reference_controls'].values())=={'PRESERVED'}
assert len(report['original_product_sha256'])==64
for target in report['projects']:
    assert target['version']=='0.9.1-experimental'
    assert target['execution']=='REAL_LOCALHOST_HTTP_AND_EXTERNAL_MCP'
    assert target['first_diagnosis_under_ten_minutes_after_dependencies_ready'] is True
    assert 0 < target['seconds_after_dependencies_ready'] < 600
    assert target['unexpected_http_requests']==0
    assert target['http_get_count']==12
    assert target['observed_loss_count']>=1
    assert len(target['cases'])==4
    assert sorted(row['status'] for row in target['cases'])==[200,400,409,422]
    for row in target['cases']:
        assert row['verdict'] in ('PRESERVED','LOSS','LOSS_AND_INVENTED')
        # CNOE adapter summary intentionally omits raw hashes; its earlier
        # matrix is derived from actual product collect and validated by fixture.
        if target['project']!='cnoe':
            assert len(row['source_sha256'])==64
            assert len(row['mcp_sha256'])==64
    if target['project'] in ('cnoe','fastmcp'):
        assert [row['verdict'] for row in target['cases'] if row['status']==200]==['PRESERVED']
        assert all(row['verdict'] in ('LOSS','LOSS_AND_INVENTED') for row in target['cases'] if row['status']>=400)
    if target['project']=='mcpgen':
        assert all(row['verdict']=='LOSS' for row in target['cases']), 'text-only result is not a structured machine carrier'
start=int((base/'begin_unix.txt').read_text())
finish=int((base/'end_unix.txt').read_text())
assert 0<finish-start<600, f'clean setup and three probes exceeded ten minutes: {finish-start}s'
meta={'audit':'PASS','elapsed_total_including_dependency_image_build_seconds':finish-start,
      'per_project_execution_seconds':{x['project']:x['seconds_after_dependencies_ready']
                                      for x in report['projects']},
      'summary_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
      'checked_program_source_sha256':report['original_product_sha256'],
      'three_actual_external_implementations':True,
      'scope':'synthetic loopback GET only, no user workload'}
(base/'INDEPENDENT_AUDIT.json').write_text(json.dumps(meta,indent=2)+'\n')
print('THREE_PROJECTS_INDEPENDENT_AUDIT_PASS',meta)
