"""Dependency-free second-project audit. Checks results not pre-chosen verdicts."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

def canonical_sha(body):
    return hashlib.sha256(json.dumps(body,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def audit(result):
    assert result['schema']=='risu-p4e-second-independent-full-chain-v1'
    p=result['pins'];e=result['execution'];c=result['checks'];r=result['results']
    assert p['schema']=='risu-p4e-second-independent-integration-prereg-v1'
    assert p['source']['repo']=='DeepL/openapi'
    assert p['source']['commit']=='2b5e50f83888960923bf7c842e75ef2dbf309e96'
    assert p['source']['blob_git_sha1']=='f1029f7003e08ce82c3322bd3f6d9ad97f594ee2'
    assert p['converter']['repo']=='PrefectHQ/fastmcp'
    assert p['converter']['version']=='4.1.6'
    assert p['consumer']['repo']=='pydantic/pydantic-ai'
    assert p['consumer']['commit']=='61db3e988851c8905bc16c8f518a1052deccec5d'
    assert e['vendor_api_called'] is False
    assert e['external_llm_called'] is False
    assert e['credentials_used'] is False
    assert e['transport']=='REAL_MCP_SDK_STDIO_SESSION_AND_LOCALHOST_HTTP'
    assert e['consumer']=='ORIGINAL_PYDANTICAI_MCP_RESULT_MAPPER_NOT_FULL_AGENT'
    assert 'getUsage' in e['tool_list']
    assert e['unexpected_http_requests']==[]
    derived=result['derived_spec']
    assert derived['paths'].keys()=={'/v2/usage'}
    assert list(derived['paths']['/v2/usage'])==['get']
    assert 'security' not in derived['paths']['/v2/usage']['get']
    assert derived['servers'][0]['url'].startswith('http://127.0.0.1:')
    assert canonical_sha(derived)==c['derived_spec_sha256']
    trace=e['http_trace']
    assert len(trace)==len(r)==3
    assert [x['case'] for x in r]==['S200','E456','E429']
    assert [x['status'] for x in r]==[200,456,429]
    assert [x['id'] for x in trace]==['S200','E456','E429']
    assert [x['status'] for x in trace]==[200,456,429]
    assert all(x['path']=='/v2/usage' and x['method']=='GET' for x in trace)
    for record in trace:
        raw=record['raw_http_body_utf8'].encode('utf-8')
        assert hashlib.sha256(raw).hexdigest()==record['raw_sha256']
        assert json.loads(raw)==record['body']

    assert all(x['status']==y['status'] and x['body']==y['original_body'] for x,y in zip(trace,r))
    assert r[0]['original_body']=={'character_count':180118,'character_limit':1250000}
    assert p['cases'][0]['body_source']=='verbatim vendor free example'
    for x,y in zip(r,p['cases']):
        assert x['case']==y['id'] and x['status']==y['status']
        if y['body'] is not None:
            assert x['original_body']==y['body']
            assert x['structured_control']['typed_code_preserved'] is True
            assert x['structured_control']['mapped'].get('code')==y['body']['code']
        assert x['original_sha256']==canonical_sha(x['original_body'])
        assert isinstance(x['mcp']['content'],list)
        assert isinstance(x['mcp']['isError'],bool)
        if y['body'] is not None:
            code=y['body']['code']
            actual_machine=bool(isinstance(x['mcp']['structuredContent'],dict) and
                                x['mcp']['structuredContent'].get('code')==code)
            actual_consumer=bool(isinstance(x['consumer']['mapped'],dict) and
                                 x['consumer']['mapped'].get('code')==code)
            assert x['mcp_typed_code_accessible']==actual_machine
            assert x['consumer_typed_code_accessible']==actual_consumer
            assert x['mcp_any_text_mentions_code']==(code in json.dumps(x['mcp']['content'],sort_keys=True,ensure_ascii=False))
            assert x['consumer_any_text_mentions_code']==(code in json.dumps(x['consumer']['mapped'],sort_keys=True,ensure_ascii=False))
        else:
            assert x['mcp_typed_code_accessible'] is None
            assert x['consumer_typed_code_accessible'] is None
    errors=r[1:]
    assert c['synthetic_error_codes'] is True
    assert c['preservation_controls'] is True
    assert c['positive_success_case_observed'] is True
    assert c['error_flags']==[x['mcp']['isError'] for x in errors]
    assert c['typed_codes_consumer']==[x['consumer_typed_code_accessible'] for x in errors]
    assert len(c['source_sha256'])==len(c['derived_spec_sha256'])==64
    lost=sum(x['consumer_typed_code_accessible'] is False for x in errors)
    preserved=sum(x['consumer_typed_code_accessible'] is True for x in errors)
    claimed=('TYPED_ERROR_LOSS_ACROSS_CHAIN' if lost==2 else
             'TYPED_ERROR_PRESERVED_ACROSS_CHAIN' if preserved==2 else
             'MIXED_OR_INCONCLUSIVE')
    assert result['outcome']==claimed
    return {'status':'PASS','result':claimed,
      'source':'DeepL/openapi','converter':'FastMCP 4.1.6','consumer':'PydanticAI original mapper',
      'http_codes':[x['status'] for x in r],
      'observed_mcp_isError':c['error_flags'],
      'typed_code_consumer_visible':c['typed_codes_consumer'],
      'error_text_mentions_code':[x['consumer_any_text_mentions_code'] for x in errors],
      'result_sha256':hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()}

def audit_vendor_source(result, path):
    blob=path.read_bytes()
    pinned=result['pins']['source']
    assert hashlib.sha256(blob).hexdigest()==result['checks']['source_sha256']
    git_blob=hashlib.sha1(b'blob '+str(len(blob)).encode()+b'\\0'+blob).hexdigest()
    assert git_blob==pinned['blob_git_sha1']
    vendor=json.loads(blob)
    assert vendor['info']['version']==pinned['api_version']
    op=vendor['paths']['/v2/usage']['get']
    assert op['operationId']=='getUsage'
    assert result['derived_spec']['paths']['/v2/usage']['get']=={
      key:value for key,value in op.items() if key!='security'}
    example=op['responses']['200']['content']['application/json']['examples']['free']['value']
    assert result['results'][0]['original_body']==example
    assert op['responses']['429']['$ref']=='#/components/responses/TooManyRequests'
    assert op['responses']['456']['$ref']=='#/components/responses/QuotaExceeded'
    schema=vendor['components']['schemas']['ErrorResponse']
    assert 'code' in schema['properties'] and schema['properties']['code']['type']=='string'
    assert schema['required']==['message']
    return {'original_git_blob':git_blob,'original_sha256':hashlib.sha256(blob).hexdigest(),
            'original_bytes':len(blob)}

def negative_mutations(result):
    import copy
    checks=[]
    tests={
      'alter_http_status':lambda v:v['execution']['http_trace'][1].update(status=200),
      'fabricate_consumer_typed_access':lambda v:v['results'][1].update(consumer_typed_code_accessible=True),
      'alter_original_code':lambda v:v['results'][2]['original_body'].update(code='ALTERED'),
      'change_claimed_outcome':lambda v:v.update(outcome='TYPED_ERROR_PRESERVED_ACROSS_CHAIN' if v['outcome']!='TYPED_ERROR_PRESERVED_ACROSS_CHAIN' else 'TYPED_ERROR_LOSS_ACROSS_CHAIN'),
      'remove_original_control':lambda v:v['results'][1]['structured_control'].update(typed_code_preserved=False),
      'change_mcp_error_flag_without_summary':lambda v:v['results'][1]['mcp'].update(isError=not v['results'][1]['mcp']['isError']),
      'alter_http_bytes_not_hash':lambda v:v['execution']['http_trace'][2].update(raw_http_body_utf8='{}'),
      'change_derived_spec_without_hash':lambda v:v['derived_spec']['paths']['/v2/usage']['get'].update(operationId='FALSIFIED'),
    }
    for name,mutate in tests.items():
        forged=copy.deepcopy(result)
        mutate(forged)
        try:
            audit(forged)
        except (AssertionError,TypeError,KeyError,ValueError):
            checks.append(name)
        else:
            raise AssertionError('MUTATION_NOT_CAUGHT: '+name)
    assert len(checks)==len(tests)
    return checks

if __name__=='__main__':
    pa=argparse.ArgumentParser()
    pa.add_argument('evidence',type=Path)
    pa.add_argument('out',type=Path)
    a=pa.parse_args()
    report=json.loads(a.evidence.read_text())
    source_path=a.evidence.parent/'vendor_openapi.json'
    assert source_path.is_file(),'PINNED_VENDOR_SPEC_NOT_IN_EVIDENCE'
    audited=audit(report)
    audited['verified_vendor_source']=audit_vendor_source(report,source_path)
    audited['negative_mutation_detections']=negative_mutations(report)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(audited,indent=2,sort_keys=True)+'\n')
    print('RISU_P4E_INDEPENDENT_AUDIT_PASS',audited['result'],
          'mutation_controls',len(audited['negative_mutation_detections']),flush=True)
