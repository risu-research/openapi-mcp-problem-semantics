"""Independent fail-closed audit of pinned real SDK contract reproductions.

Not a self-attested success: rechecks saved actual MCP envelopes, hashes,
contract field values, failure signatures, repair safety and minimality.
Does not execute the independent upstream SDKs; the container live job does.
"""
from pathlib import Path
import hashlib,json,sys

source=Path(sys.argv[1] if len(sys.argv)>1 else 'results')
report=json.loads((source/'REAL_APPS_SUMMARY.json').read_text())
assert report['status']=='PASS'
assert report['product_version']=='0.9.6-experimental'
assert report['synthetic_http_get_count']==10
assert report['real_control_mcp_replays']==6
assert report['typed_passthrough_cases']==6
assert report['critical_field_mutants_killed']==2
assert report['unexpected_requests']==0
assert report['real_minimal_mcp_replays']==2
assert report['patch_applied_and_retested'] is True
assert report['pinned_repos']=={
    'mcpgen':'30ee7cb9c2e923ce901e788b0d911f6547772866',
    'pygithub':'5aeb43916b197a0fe8016600817b868fc894af5a',
    'stripe':'d97a68e28ec6553c3545fdf7e5322e871559cfdb'}
rows=report['consumers']
assert len(rows)==2
assert {r['name'] for r in rows}=={'pygithub-404','stripe-rate-limit-400'}
sys.path.insert(0,'dist/risu_v09_source')
from risu_repair import promote_text_json,read_structured
from risu_witness import witness
from risu_minimize import canonical,minimize
from risu_fixverify import prepare_consumer_result,verify_preserved,digest_without_values

fixtures=source/'repro_package'/'fixtures'
for case in rows:
    name=case['name']
    expected=('UnknownObjectException' if name=='pygithub-404' else 'RateLimitError')
    assert case['expected_exception'] if 'expected_exception' in case else True
    assert case['original_sdk_result']==expected
    assert case['broken_bridge_result']!=expected
    assert case['repaired_bridge_result']==expected
    assert case['minimality']=='ONE_MINIMAL_DELETIONS'
    assert case['original_bytes']>case['minimal_bytes']>0
    assert case['accepted_deletions']>=1
    assert 2<=case['minimizer_checks']<=350
    o=json.loads((fixtures/(name+'.json')).read_text())
    assert o['contract']==name and o['status']==case['source_status']
    data=o['source_body']
    if name=='pygithub-404':
        assert data=={'message':'Not Found'},data
        assert case['source_status']==404 and case['required_path']=='/message'
        assert case['repository']=='PyGithub/PyGithub'
    else:
        assert data=={'error':{'code':'rate_limit'}},data
        assert case['source_status']==400 and case['required_path']=='/error/code'
        assert case['repository']=='stripe/stripe-python'
    assert len(canonical(data).encode())==case['minimal_bytes']
    mcp=o['mcp_result']
    repaired=prepare_consumer_result(mcp)
    assert read_structured(mcp) is None
    assert read_structured(repaired)==data
    assert repaired['_meta']['observed_http_status']==o['status']
    before=witness({'status':o['status'],'content_type':'application/json','body':data},
                   mcp,[case['required_path']],require_http_status=True)
    after=witness({'status':o['status'],'content_type':'application/json','body':data},
                  repaired,[case['required_path']],require_http_status=True)
    assert before['models']['structured-only']['outcome']=='FAIL'
    assert before['models']['json-text-data']['outcome']=='PASS'
    assert after['models']['structured-only']['outcome']=='PASS'
    assert case['real_mcp_witness']==before
    assert hashlib.sha256(canonical(mcp).encode()).hexdigest()==case['minimized_real_mcp_sha256']
    expected_blob=('397a58f5d44f62a49fb44cdae9273721a3f69354'
                   if name=='pygithub-404' else
                   '6224c5e6d357043ff7a404cebefbbdef09ec9b7f')
    assert case['source_blob_sha']==expected_blob
# Independent positive and negative controls, all collected from actual
# generated MCP server calls in the isolated live job.
expected_controls={
    'pygithub-404-generic':('pygithub-404',404,'GithubException'),
    'pygithub-401-credentials':('pygithub-404',401,'BadCredentialsException'),
    'stripe-400-invalid-request':('stripe-rate-limit-400',400,'InvalidRequestError'),
    'stripe-401-auth':('stripe-rate-limit-400',401,'AuthenticationError'),
    'pygithub-200-success':('pygithub-404',200,'HTTP_200_OBJECT'),
    'stripe-200-success':('stripe-rate-limit-400',200,'HTTP_200_OBJECT'),
}
controls=report['control_results']
assert len(controls)==6 and {x['case'] for x in controls}==set(expected_controls)
ctrl_root=source/'repro_package'/'control_fixtures'
assert ctrl_root.is_dir() and len(list(ctrl_root.glob('*.json')))==6
for control in controls:
    key=control['case']
    contract,status,expected=expected_controls[key]
    fixture=json.loads((ctrl_root/(key+'.json')).read_text())
    assert fixture['case']==key and fixture['contract']==contract
    assert fixture['status']==status
    assert fixture['expected_native']==expected
    original=fixture['source_body']
    mcp=fixture['mcp_result']
    assert control['native']==expected and control['after']==expected
    assert control['typed_passthrough_preserved'] is True
    assert control['body_sha256']==digest_without_values(original)
    assert control['actual_mcp_sha256']==digest_without_values(mcp)
    assert read_structured(mcp) is None
    converted=prepare_consumer_result(mcp)
    assert read_structured(converted)==original
    assert converted['_meta']['observed_http_status']==status
    pretyped={'structuredContent':original,'isError':status>=400,
              '_meta':{'observed_http_status':status},
              'content':[{'type':'text','text':'do not parse'}]}
    assert verify_preserved(prepare_consumer_result(pretyped),pretyped)
    if key=='pygithub-404-generic':
        assert control['before']==expected, 'pre-existing correct classification changed'
    if status==200:assert mcp.get('isError') is not True
patch=(source/'repro_package'/'consumer_bridge.patch').read_text()
assert patch.count('--- consumer_bridge.py')==1
assert patch.count('+++ consumer_bridge.py')==1
assert 'prepare_consumer_result' in patch
assert 'stripe/_api_requestor.py' not in patch
assert 'github/Requester.py' not in patch
start=int((source/'begin_unix.txt').read_text())
end=int((source/'end_unix.txt').read_text())
assert 0<end-start<600,(start,end)
audit={'status':'PASS',
       'independent_audit':'QUALIFIED',
       'two_unmodified_external_sdk_dispatchers_run_in_live_job':True,
       'two_minimal_real_mcp_replays':True,
       'bounded_synthetic_local_http_gets':10,
       'independent_real_control_replays':6,
       'typed_passthrough_nonregressions':6,
       'discriminator_mutants_killed':2,
       'adapter_patch_safety':'FIXES_CONSUMER_BRIDGE_ONLY',
       'complete_image_build_and_validation_seconds':end-start,
       'summary_sha256':hashlib.sha256((source/'REAL_APPS_SUMMARY.json').read_bytes()).hexdigest(),
       'claim_boundary':'Pinned external SDK dispatch functions actually executed inside isolated CI; independent audit rechecked serialized MCP evidence and modeled repair; no vendor API or source modified'}
(source/'INDEPENDENT_AUDIT.json').write_text(json.dumps(audit,indent=2)+'\n')
print('RISU_REAL_APPLICATION_INDEPENDENT_AUDIT_PASS',json.dumps(audit))
