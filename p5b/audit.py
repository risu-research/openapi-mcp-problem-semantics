"""Strict, independent standard-library verifier for source -> CNOE -> consumers -> repair.

Replays *checks* from original evidence, never calls a vendor or upgrades a
hypothetical loss into a factual new upstream vulnerability.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

MODES=('passthrough','repair')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def check(report,root:Path):
    assert report['schema']=='risu-p5b-original-converted-consumer-failure-repair-v1'
    e=report['execution'];p=report['pins'];ph=report['phase_results']
    assert p['meilisearch_openapi_git']=='0b0b0fdbb9d5821ec018a3db2777986a231eec37'
    assert p['cnoe_codegen_git']=='8c2b065497cf32ecbb7cf7e28dad3a99c6706c3f'
    assert p['langchain_git']=='bb6a25a878527136dcb1a20507d5c20049427f96'
    assert p['meilisearch_python_git']=='6a6cc2596779a06f121ebb6d88dfa6943ee18d91'
    assert p['sdk_errors_blob_git_sha1']=='9771fba0458973dc5cefe94ee3505e215caa6e66'
    assert e['actual_cnoe_generated_mcp_stdio'] and e['actual_langchain_as_langchain_tool']
    assert e['original_official_meilisearch_sdk_parser']
    assert e['repair_requires_original_http_source_body']
    assert e['no_vendor_production_requests'] and e['no_llm_run']
    assert e['original_source_mutated'] is False and e['external_libraries_patched'] is False
    assert e['unexpected_http']==[]
    assert e['http_get_counts']=={'/indexes/movies':4,'/indexes/does-not-exist':4}
    assert report['original_consumer']['status']=='PASS'
    assert report['converted_consumer']['status']=='EXPECTED_APPLICATION_CONTRACT_FAILURE'
    assert report['converted_consumer']['exception_type']=='SourceErrorContractFailure'
    assert 'SOURCE_ERROR_CODE_UNAVAILABLE' in report['converted_consumer']['reason']
    assert report['repaired_consumer']['status']=='PASS'
    original=report['original_consumer']['result'];fixed=report['repaired_consumer']['result']
    for k in ('code','error_type','link'):
        assert original[k]==fixed[k],('source not reconstructed exactly',k)
    assert original['code']=='index_not_found' and original['error_type']=='invalid_request'
    assert original['status']==fixed['status']==404
    assert report['tool_names']['passthrough']==report['tool_names']['repair']
    for mode in MODES:
        cases=ph[mode];assert len(cases)==2 and {v['case'] for v in cases}=={'error','success'}
        for v in cases:assert v['langchain']['type']=='ToolMessage'
    b={v['case']:v for v in ph['passthrough']};f={v['case']:v for v in ph['repair']}
    assert b['error']['raw_mcp']['isError'] is False
    assert b['error']['langchain']['status']=='success'
    assert 'index_not_found' not in json.dumps(b['error'])
    assert f['error']['raw_mcp']['isError'] is True
    assert f['error']['langchain']['status']=='error'
    assert f['error']['raw_mcp']['structuredContent']['code']=='index_not_found'
    assert 'index_not_found' in json.dumps(f['error']['langchain']['content'])
    assert b['success']['raw_mcp']==f['success']['raw_mcp']
    assert b['success']['langchain']['artifact']==f['success']['langchain']['artifact']
    source=f['error']['raw_mcp']['structuredContent']
    assert set(source)=={'message','code','type','link'}
    assert hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest()==e['original_http_response_sha256']
    for mode in MODES:
        path=root/(mode+'_wire.jsonl')
        assert sha(path)==report['wire_audits'][mode]['wire_sha256']
        events=[json.loads(x) for x in path.read_text().splitlines()]
        req=[x['frame'] for x in events if x['direction']=='client_to_proxy' and x['frame'].get('method')=='tools/call']
        before=[x['frame'] for x in events if x['direction']=='backend_to_proxy' and x['frame'].get('id') in {r['id'] for r in req}]
        after=[x['frame'] for x in events if x['direction']=='proxy_to_client' and x['frame'].get('id') in {r['id'] for r in req}]
        assert len(req)==len(before)==len(after)==4
        before={x['id']:x for x in before};after={x['id']:x for x in after}
        ids={r['id'] for r in req if r['params']['arguments']=={'path_indexUid':'does-not-exist'}}
        assert len(ids)==2
        for i in ids:
            assert not before[i]['result'].get('isError',False)
            assert 'index_not_found' not in json.dumps(before[i])
            if mode=='repair':
                assert after[i]['result']['isError'] is True
                assert after[i]['result']['structuredContent']==source
                assert 'index_not_found' in after[i]['result']['content'][0]['text']
            else:assert before[i]==after[i]
        for i in set(before)-ids:assert before[i]==after[i]
        repairs=[x['frame'] for x in events if x['direction']=='repair_event' and x['frame'].get('id') in before]
        assert sum(bool(x['changed']) for x in repairs)==(2 if mode=='repair' else 0)
    return {'audit':'PASS','external_consumer_original':'PASS',
       'external_consumer_broken':'EXPECTED_APPLICATION_CONTRACT_FAILURE',
       'external_consumer_repaired':'PASS','original_cnoe_unmodified':True,
       'source_repair_allowlisted':True,
       'result_sha256':hashlib.sha256(json.dumps(report,sort_keys=True).encode()).hexdigest()}

def main():
    p=argparse.ArgumentParser();p.add_argument('report',type=Path);p.add_argument('out',type=Path);a=p.parse_args()
    d=json.loads(a.report.read_text());result=check(d,a.report.parent)
    a.out.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print('P5B_INDEPENDENT_RECOMPUTED_AUDIT_PASS',json.dumps(result,sort_keys=True))
if __name__=='__main__':main()