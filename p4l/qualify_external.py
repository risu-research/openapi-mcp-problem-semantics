"""P4-L: verify independently *published* original observations. Never synthesize pairing.

Fetch only SHA-pinned third-party public files before offline, read-only analysis.
No third-party code execution, no vendor API credentials, no raw payload published.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parent
PROTOCOL=json.loads((ROOT/'FROZEN_PROTOCOL.json').read_text())

def blob_sha(raw):
    return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()

def download_all(out):
    raw_dir=out/'private_originals_do_not_upload'
    raw_dir.mkdir(parents=True,exist_ok=True)
    manifests=[]
    for source in PROTOCOL['sources']:
        repo=source['repo'];commit=source['commit'];file=source['path']
        url=f'https://raw.githubusercontent.com/{repo}/{commit}/{urllib.parse.quote(file,safe="/")}'
        req=urllib.request.Request(url,headers={'User-Agent':'RISU-P4L-Public-Research-Audit'})
        with urllib.request.urlopen(req,timeout=35) as resp:
            assert resp.status==200
            raw=resp.read(2_000_001)
        assert 0<len(raw)<2_000_000,(source['id'],'oversized')
        assert blob_sha(raw)==source['sha1'],(source['id'],'UNAUTHENTICATED_EXTERNAL_BYTES')
        (raw_dir/source['id']).write_bytes(raw)
        manifests.append({k:source[k] for k in ('id','repo','commit','path','kind')}|
            {'git_blob_sha1':blob_sha(raw),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)})
        print('EXTERNAL_SOURCE_AUTHENTICATED',source['id'],flush=True)
    (out/'provenance_manifest.json').write_text(json.dumps(manifests,indent=2,sort_keys=True)+'\n')
    return raw_dir

def positive_step(trace,tool):
    steps=trace['steps']
    return [s for s in steps if s.get('surface')=='mcp' and s.get('tool')==tool and s.get('op')=='tools/call']

def classify(raw_dir,out):
    trace=json.loads((raw_dir/'monark_trace').read_text())
    provenance=(raw_dir/'monark_provenance').read_text()
    cisco=[json.loads(t) for t in (raw_dir/'cisco_mcp_traffic').read_text().splitlines() if t.strip()]
    tyk=(raw_dir/'tyk_oas_mcp_test').read_text()
    meda=json.loads((raw_dir/'meda_sdk_trace').read_text())
    blitter=(raw_dir/'amiberry_semantic_parity_source').read_text()
    assert trace['schema']=='monark-h5-e2e-trace/1'
    assert 'record-h5-e2e-trace' in provenance and 'PROVENANCE' in provenance
    assert 'recorded end-to-end demonstration' in trace.get('title','').lower()
    mcp=positive_step(trace,'cascade')
    http=[s for s in trace['steps'] if s.get('surface')=='http' and s.get('tool')=='cascade']
    assert len(mcp)==1 and len(http)==1
    a,b=mcp[0],http[0]
    assert a['n']!=b['n'] and a['surface']=='mcp' and b['surface']=='http'
    assert a['request']['method']=='tools/call'
    assert b['request']['method']=='POST' and b['request']['path']=='/cascade'
    assert a['request']['params']['arguments']==b['request']['body']
    assert a['response']==b['response'] and 'structuredContent' in b['response']
    assert a['response'].get('isError',False) is False
    assert b['response'].get('status') is None, 'unexpected status field, investigate classification'
    # Recorded HTTP mirror is a separate actual call made after the MCP call.
    # Equality is semantic parity; no causal API conversion chain occurred.
    errors=[s for s in trace['steps'] if s.get('surface')=='mcp' and
            s.get('op')=='tools/call' and s.get('response',{}).get('isError') is True]
    assert len(errors)>=1
    for e in errors:
        assert 'response' in e and e['request']['method']=='tools/call'
    e=next(x for x in errors if x['tool']=='gate')
    assert e['response']['_meta']['monarkgate.tech/error_code']=='task_class_retired'
    assert not any(s for s in trace['steps'] if s.get('surface')=='http' and
        s.get('tool')=='gate' and s.get('response',{}).get('status',200)>=400)
    # No normal REST upstream for this error has been independently recorded.
    # An absent status is not silently inferred as 200.
    reqs=[x for x in cisco if x.get('direction')=='request' and x.get('method')=='tools/call']
    responses=[x for x in cisco if x.get('direction')=='response' and 'result' in x]
    assert len(reqs)>=2
    assert all(any(z.get('id')==req.get('id') for z in responses) for req in reqs)
    assert all(z.get('direction') in ('request','response') for z in cisco)
    assert not any(x.get('kind') in ('HTTP_REQUEST','HTTP_RESPONSE','UPSTREAM_API') for x in cisco)
    assert 'httptest.NewServer' in tyk and 'makeHandler' in tyk
    assert 'res.StructuredContent.(UpstreamCallOutput)' in tyk
    assert 'out.Status != 200' in tyk
    assert 'func TestOASTool_ProxiesWithAuthAndTrace' in tyk
    assert meda['kind']=='d0_reference_pilot'
    assert len(meda['runs'])>=5
    assert all('receipt' in row and 'proxy' in row['receipt'] for row in meda['runs'])
    # Explicit protocol IDs demonstrate HTTP in meda means the transport of MCP,
    # not an unrelated REST API source being converted into a tool.
    mcp_proxy=[p for row in meda['runs'] for p in row['receipt']['proxy'].get('mcp',[])]
    assert any(p.get('protocol')=='mcp' and p.get('event')=='upstream_response' for p in mcp_proxy)
    assert 'test_every_stable_result_has_http_mcp_body_parity' in blitter
    assert 'pytest.mark.parametrize("code", list(StableCode))' in blitter
    assert 'http_response.json() == json.loads(mcp_response[0].text)' in blitter
    assert 'httpx.ASGITransport' in blitter
    assert 'AsyncMock(return_value=expected)' in blitter
    result={
      'schema':'risu-p4l-independent-public-evidence-qualification-v1',
      'frozen_protocol_sha256':hashlib.sha256((ROOT/'FROZEN_PROTOCOL.json').read_bytes()).hexdigest(),
      'source_count':len(PROTOCOL['sources']),
      'distinct_external_repositories':len(set(x['repo'] for x in PROTOCOL['sources'])),
      'verified_cases':{
        'monark_same_recording_distinct_interface_normal_parity':{
            'count':1,'level':'TIER2_SEMANTIC_PARITY_NOT_CAUSAL',
            'mcp_step':a['n'],'http_step':b['n'],
            'same_arguments':True,'same_response_object':True,
            'original_http_status_recorded':False,
            'why_not_tier1':'Both calls independently invoked same operation; no upstream HTTP request issued as consequence of MCP call'},
        'monark_error_mcp_only':{
            'count':len(errors),'level':'TIER3_ONE_SIDED_MCP_ERROR',
            'example_tool':e['tool'],
            'error_code':'task_class_retired',
            'http_mirror_error_same_call_recorded':False},
        'cisco_independent_recorded_mcp_calls':{
            'count':len(reqs),'level':'TIER3_MCP_ONLY_WITH_PAIRED_MCP_REQUEST_RESPONSE',
            'upstream_rest_http_recorded':False},
        'tyk_independent_converter_handler_test':{
            'count':1,'level':'TIER3_EXTERNALLY_AUTHORED_HTTP_TO_MCP_TEST_SOURCE',
            'on_wire_mcp_client_recorded':False,
            'raw_external_http_mcp_capture_committed':False},
        'meda_independent_mcp_http_transport_trace':{
            'count':len(meda['runs']),'level':'TIER3_MCP_TRANSPORT_ONLY',
            'rest_backend_source_proven':False},
        'amiberry_independent_normal_and_error_two_interface_test':{
            'count':1,'level':'TIER3_ASGI_IN_PROCESS_MOCKED_TEST_SOURCE',
            'success_and_error_parameterized':True,
            'real_mcp_network_wire_traffic_recorded':False}
      },
      'adjudicated_counts':{
        'independent_external_causal_upstream_http_to_mcp_normal':0,
        'independent_external_causal_upstream_http_to_mcp_error':0,
        'independent_external_dual_surface_normal_parity':1,
        'independent_external_recorded_mcp_error_without_http_peer':len(errors),
        'verified_independent_true_negative_causal_pairs':0,
        'field_false_positive_rate':None},
      'limitations':[
        'No publicly attested same-call upstream REST API HTTP response -> MCP result observed under independent external recorder for both normal and error.',
        'Two distinct HTTP and MCP interface calls to same handler do not show that HTTP response caused MCP result.',
        'Tests with mocked internal results or HTTP ASGI in-process are not recorded real service traffic.',
        'MCP carried via HTTP is not a second REST API upstream source.',
        'Original HTTP status absent from Monark mirror record; no status is inferred.',
        'Field FPR null because adjudicated true-negative denominator zero.'
      ]
    }
    out.mkdir(parents=True,exist_ok=True)
    (out/'qualification.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print('P4L_EXTERNAL_EVIDENCE_QUALIFICATION',json.dumps(result['adjudicated_counts'],sort_keys=True),flush=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,default=ROOT/'results')
    p.add_argument('--fetch',action='store_true')
    p.add_argument('--qualify',action='store_true')
    a=p.parse_args()
    if a.fetch:download_all(a.output)
    if a.qualify:classify(a.output/'private_originals_do_not_upload',a.output)
