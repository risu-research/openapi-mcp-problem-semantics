"""Standalone, dependency-free auditor of full-chain claims and recorded values."""
from pathlib import Path
import argparse, json, hashlib


def audit(result):
    assert result['schema']=='risu-p4d-independent-full-chain-v1'
    p=result['pins']; e=result['execution']; c=result['checks']; entries=result['case_results']
    assert p['source']['repo']=='meilisearch/open-api' and p['source']['operation']=='GET /indexes/{indexUid}'
    assert p['converter']['repo']=='cnoe-io/openapi-mcp-codegen'
    assert p['consumer']['repo']=='langchain-ai/langchain'
    assert e['production_service_touched'] is False and e['external_llm_touched'] is False
    assert e['transport']=='ACTUAL_STDIO_MCP_CLIENT_SESSION'
    assert e['consumer_kind']=='ACTUAL_LANGCHAIN_MCP_AS_LANGCHAIN_TOOL_AND_TOOLMESSAGE'
    assert e['unexpected_http']==[]
    assert e['local_http_gets']=={'/indexes/movies':2,'/indexes/does-not-exist':2}
    assert 'get_index' in e['listed_tools']
    assert len(entries)==2 and {x['case'] for x in entries}=={'success','error'}
    vals={x['case']:x for x in entries}
    success=vals['success'];error=vals['error']
    assert success['arguments']=={'indexUid':'movies'}
    assert error['arguments']=={'indexUid':'does-not-exist'}
    assert success['consumer']['type']=='ToolMessage' and error['consumer']['type']=='ToolMessage'
    assert success['consumer']['status'] in ('success','error') and error['consumer']['status'] in ('success','error')
    source_code=c['source_error_code']
    assert source_code=='index_not_found'
    raw_visible=source_code in json.dumps(error['raw_mcp'],ensure_ascii=False,default=str)
    consumed_visible=source_code in json.dumps({'artifact':error['consumer']['artifact'],'content':error['consumer']['content']},ensure_ascii=False,default=str)
    assert c['mcp_contains_error_code']==raw_visible
    assert c['langchain_model_or_artifact_contains_error_code']==consumed_visible
    assert c['http_error_was_recognized_by_mcp']==error['raw_mcp']['isError']
    assert c['langchain_classified_error']==(error['consumer']['status']=='error')
    assert result['outcome'] in p['outcomes_to_report']
    if result['outcome']=='EXTERNAL_FULL_CHAIN_CONFIRMED_WITH_LOSS': assert not consumed_visible
    if result['outcome']=='EXTERNAL_FULL_CHAIN_CONFIRMED_NO_LOSS': assert consumed_visible
    return {'status':'PASS','outcome':result['outcome'],
            'facts':{'http_error':True,'error_code_seen_by_mcp':raw_visible,
                     'error_code_seen_by_langchain':consumed_visible,
                     'mcp_flag':error['raw_mcp']['isError'],
                     'langchain_error':error['consumer']['status']=='error'},
            'full_chain_sha256':hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('result',type=Path); ap.add_argument('out',type=Path);a=ap.parse_args()
    report=json.loads(a.result.read_text())
    audit_report=audit(report);a.out.write_text(json.dumps(audit_report,indent=2)+'\n')
    print('RISU_P4D_INDEPENDENT_AUDIT',audit_report['status'],audit_report['outcome'])
