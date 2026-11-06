"""P3 positive and negative control matrix on authentic generated MCPGen tools.

Each of the four control errors is served through real generated MCP server ->
localhost HTTP, then classified with the *unmodified* external Python SDK.
Two additional HTTP-200 success controls ensure the patch also handles valid
data. No production API calls, and no external vendor source modifications.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path

from risu_fixverify import prepare_consumer_result, verify_preserved, digest_without_values
from risu_repair import read_structured, RepairRejected
from risu_minimize import canonical
from real_contracts import classify_real_sdk

CONTROLS={
 'pygithub-404-generic':('pygithub-404',404,{'message':'Access temporarily restricted','unused':'synthetic'},'GithubException'),
 'pygithub-401-credentials':('pygithub-404',401,{'message':'Bad credentials','unused':'synthetic'},'BadCredentialsException'),
 'stripe-400-invalid-request':('stripe-rate-limit-400',400,
                                {'error':{'code':'parameter_invalid','message':'Synthetic invalid field'},'unused':'synthetic'},
                                'InvalidRequestError'),
 'stripe-401-auth':('stripe-rate-limit-400',401,
                    {'error':{'type':'invalid_request_error','message':'Synthetic auth error'},'unused':'synthetic'},
                    'AuthenticationError')
}
SUCCESS={
 'pygithub-200-success':('pygithub-404',200,{'id':'synth-github-1','active':True}),
 'stripe-200-success':('stripe-rate-limit-400',200,{'id':'synth-stripe-1','active':True})
}

def strict_payload(mcp):
    val=read_structured(mcp)
    return val if isinstance(val,dict) else {}

def error_label(contract,body,status):
    return classify_real_sdk(contract,body,status)

def control_mcp(client, lookup, counter, c, status, body):
    # Hook to existing, already generated and running actual MCPGen server.
    lookup[c['path']]=(status,copy.deepcopy(body))
    old=counter['total']
    result=client.call(c['operation'],{})
    assert counter['total']==old+1,('MCPGen did not perform the GET',c['path'])
    return result

def test_controls(client,lookup,counter,contracts,package,*,write=True):
    records=[]
    stored=[]
    for case,(contract,status,body,expected) in CONTROLS.items():
        c=contracts[contract]
        result=control_mcp(client,lookup,counter,c,status,body)
        before=error_label(contract,strict_payload(result),status)
        after_mcp=prepare_consumer_result(result)
        after=error_label(contract,strict_payload(after_mcp),status)
        original=error_label(contract,body,status)
        assert original==expected,(case,'original SDK expectation drift',original)
        assert after==original,(case,'fix changed original SDK decision',after,original)
        assert strict_payload(after_mcp)==body,(case,'body field lost')
        assert after_mcp['_meta']['observed_http_status']==status
        # Same data already structured: passthrough must be byte-for-byte stable,
        # including original text, status, and metadata.
        pretyped={'structuredContent':copy.deepcopy(body),
                  'content':[{'type':'text','text':'unused-untrusted-text'}],
                  '_meta':{'observed_http_status':status,'trace':'synthetic'},'isError':True}
        preserved=prepare_consumer_result(pretyped)
        assert verify_preserved(pretyped,preserved),(case,'typed regression')
        assert error_label(contract,strict_payload(preserved),status)==expected
        # Mutant patch drops the actual required discriminator. Its failure
        # demonstrates that tests are sensitive, not success-only assertions.
        if case.startswith('pygithub'):
            mutant=copy.deepcopy(body);mutant.pop('message',None)
        else:
            mutant=copy.deepcopy(body);mutant['error'].pop('code',None)
        mutation=error_label(contract,mutant,status)
        # Generic 404 and invalid-request 400 are unchanged when their marker is
        # deleted; the critical fix cases are mutation-tested in run_live.
        records.append({'case':case,'contract':contract,'status':status,
                        'native':original,'before':before,'after':after,
                        'typed_passthrough_preserved':True,
                        'body_sha256':digest_without_values(body),
                        'actual_mcp_sha256':digest_without_values(result),
                        'candidate_mutation_result':mutation})
        stored.append({'case':case,'contract':contract,'status':status,
                       'source_body':body,'mcp_result':result,'expected_native':original})
    for case,(contract,status,body) in SUCCESS.items():
        c=contracts[contract]
        result=control_mcp(client,lookup,counter,c,status,body)
        assert result.get('isError') is not True,(case,'spurious error flag')
        prepared=prepare_consumer_result(result)
        assert strict_payload(prepared)==body,(case,'success body changed')
        assert prepared['_meta']['observed_http_status']==200
        typed={'structuredContent':copy.deepcopy(body),'isError':False,
               '_meta':{'observed_http_status':200},
               'content':[{'type':'text','text':'not parsable'}]}
        assert verify_preserved(prepare_consumer_result(typed),typed)
        records.append({'case':case,'contract':contract,'status':status,
                        'body_sha256':digest_without_values(body),
                        'actual_mcp_sha256':digest_without_values(result),
                        'native':'HTTP_200_OBJECT','before':'NO_STRUCTURED_BODY',
                        'after':'HTTP_200_OBJECT','typed_passthrough_preserved':True})
        stored.append({'case':case,'contract':contract,'status':status,
                       'source_body':body,'mcp_result':result,'expected_native':'HTTP_200_OBJECT'})
    if write:
        root=Path(package)/'control_fixtures';root.mkdir(parents=True,exist_ok=True)
        for record in stored:
            (root/(record['case']+'.json')).write_text(
                json.dumps(record,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    return records
