"""P4-M: qualify *original* third-party VCR network recordings, without running foreign source.

The VCR YAML is a third-party-published, redacted recording. It is NOT a
RISU-written cross-boundary signed capture and does not contain on-wire
MCP CallToolResult. No claim of live vendor API availability or field FPR.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import quote,urlparse
from urllib.request import Request,urlopen
import yaml

ROOT=Path(__file__).resolve().parent
FROZEN=json.loads((ROOT/'FROZEN_SOURCES.json').read_text())

def gitblob(content):
    return hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest()

def fetch_and_verify(out):
    cfg=FROZEN['original_replay']
    cache=out/'private_original_network_recordings_DO_NOT_PUBLISH'
    cache.mkdir(parents=True,exist_ok=True)
    inventory=[]
    items=cfg['files']+cfg['source_code']
    for i,item in enumerate(items):
        path=item['path'];expected=item['git_blob_sha1']
        url='https://raw.githubusercontent.com/'+cfg['repo']+'/'+cfg['commit']+'/'+quote(path,safe='/')
        req=Request(url,headers={'User-Agent':'RISU-P4M-Original-Artifact-Audit'})
        with urlopen(req,timeout=35) as fh:
            assert fh.status==200
            raw=fh.read(1200000)
        assert 0<len(raw)<1200000
        assert gitblob(raw)==expected,('GIT_BLOB_SHA_MISMATCH',path)
        (cache/('item_'+str(i))).write_bytes(raw)
        inventory.append({'id':item.get('id','source_'+str(i)),'source_path':path,
          'git_blob_sha1':expected,'sha256':hashlib.sha256(raw).hexdigest(),
          'size_bytes':len(raw),'cache_name':'item_'+str(i)})
        print('P4M_AUTHENTICATED_THIRD_PARTY_ORIGINAL',i+1,len(items),item.get('id',path),flush=True)
    (out/'source_inventory.json').write_text(json.dumps(inventory,indent=2,sort_keys=True)+'\n')
    return cache

def inspect(out):
    cfg=FROZEN['original_replay']
    items=json.loads((out/'source_inventory.json').read_text())
    cache=out/'private_original_network_recordings_DO_NOT_PUBLISH'
    assert len(items)==5
    for i,item in enumerate(cfg['files']+cfg['source_code']):
        raw=(cache/('item_'+str(i))).read_bytes()
        assert gitblob(raw)==item['git_blob_sha1']
    testsource=(cache/'item_2').read_text()
    mcpsource=(cache/'item_3').read_text()
    assert 'class TestMcpDispatchLive' in testsource
    assert 'get_jpo_progress(DESIGN_APP, ip_type="design")' in testsource
    assert 'record = result.items[0]' in testsource
    assert 'assert record["application_number"] == DESIGN_APP' in testsource
    assert 'async def test_get_patent_progress_not_found' in testsource
    assert 'progress = await client.get_patent_progress(NONEXISTENT_PATENT_APP)' in testsource
    assert 'assert progress is None' in testsource
    assert 'async def get_jpo_progress' in mcpsource
    measured=[]
    for i,f in enumerate(cfg['files']):
        d=yaml.safe_load((cache/('item_'+str(i))).read_text(encoding='utf-8-sig'))
        assert d.get('version')==1 and isinstance(d.get('interactions'),list)
        auth=d['interactions'][0]
        assert auth['request']['method']=='POST'
        assert urlparse(auth['request']['uri']).path=='/auth/token'
        assert auth['response']['status']['code']==200
        upstream=[x for x in d['interactions'] if x['request']['method']=='GET']
        assert len(upstream)==1
        transaction=upstream[0]
        status=transaction['response']['status']['code']
        assert status==f['http_status']
        reqpath=urlparse(transaction['request']['uri']).path
        assert reqpath==f['expected_path']
        content=json.loads(transaction['response']['body']['string'])
        r=content['result']
        assert r['statusCode']==f['application_status_code']
        if f['id']=='jpo_tool_success_cassette':
            assert status==200 and r['statusCode']=='100' and isinstance(r['data'],dict)
            assert r['data'].get('applicationNumber')=='2020015234'
        else:
            assert status==200 and r['statusCode']=='107' and r['data']=={}
            assert bool(r.get('errorMessage'))
        measured.append({
          'id':f['id'],'origin':'ORIGINAL_REDACTED_EXTERNAL_VCR',
          'recorded_upstream_http_status':status,
          'recorded_application_status_code':r['statusCode'],
          'upstream_recorded_in_mcp_dispatch_test':f['id']=='jpo_tool_success_cassette',
          'mcp_tools_call_wire_frame_recorded':False,
          'mcp_isError_recorded':False,
          'api_http_non2xx_error':False,
          'application_level_not_found':r['statusCode']=='107',
          'causal_upstream_to_final_mcp_wire_confirmed':False,
          'request_path_matches_original_third_party_test':True,
          'original_git_blob_sha1':f['git_blob_sha1']})
    assert len(measured)==2
    result={
      'schema':'risu-p4m-original-third-party-network-artifact-audit-v1',
      'frozen_sources_sha256':hashlib.sha256((ROOT/'FROZEN_SOURCES.json').read_bytes()).hexdigest(),
      'source_count':len(items),'third_party_original_cassettes':measured,
      'externally_original_recorded_http_success':1,
      'externally_original_recorded_application_not_found':1,
      'original_mcp_dispatch_test_with_recorded_http_success':1,
      'original_mcp_dispatch_test_with_recorded_http_application_error':0,
      'original_full_wire_http_to_mcp_success':0,
      'original_full_wire_http_to_mcp_error':0,
      'field_fpr':None,
      'unrelated_independent_ci_artifact':{
        'repository':FROZEN['original_ci_artifact']['repository'],
        'workflow_run_id':FROZEN['original_ci_artifact']['workflow_run_id'],
        'artifact_id':FROZEN['original_ci_artifact']['artifact_id'],
        'original_archive_verified_separately':True,
        'contains_observed_rest_api_upstream_for_same_mcp_tool_call':False,
        'may_be_joined_with_jpo_recordings':False
      },
      'limitations':[
        'The success VCR is an original source-HTTP recording from a third-party in-process MCP tool-dispatch test, not full on-wire tools/call output.',
        'The application status 107 in HTTP 200 is a direct JPO client test, not an original MCP error observation.',
        'VCR cassettes are redacted; the repo maintainer states they were recorded live. No independent notary or trusted third-party witness is claimed.',
        'Third-party CI artifact is separate and originates from an unrelated project: cannot prove causal connection to JPO recordings.',
        'No independent developer-published same-call upstream HTTP -> MCP full wire normal/error pair found; field FPR remains undefined.'
      ]}
    (out/'qualified_originals.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print('P4M_ORIGINAL_THIRD_PARTY_ARTIFACTS_QUALIFIED',
          json.dumps({'recorded_http_success':1,'recorded_http_logical_error':1,
          'dispatch_linked_success':1,'dispatch_linked_error':0,
          'full_on_wire_causes_normal':0,'full_on_wire_causes_error':0},sort_keys=True),flush=True)
    return result

if __name__=='__main__':
    a=argparse.ArgumentParser()
    a.add_argument('--out',type=Path,default=ROOT/'results')
    a.add_argument('--fetch',action='store_true')
    a.add_argument('--inspect',action='store_true')
    args=a.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    if args.fetch:fetch_and_verify(args.out)
    if args.inspect:inspect(args.out)
