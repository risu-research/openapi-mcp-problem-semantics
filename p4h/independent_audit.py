"""Independent audit of P4-H's actual SDK stdio capture and product verdict.

No import from RISU Probe: re-check native evidence and compare to CLI output.
This only validates an intentionally scripted demo, never attests external
production origin of the developer-declared HTTP->MCP join.
"""
from __future__ import annotations
import argparse,hashlib,json,copy
from pathlib import Path


def sha(raw):return hashlib.sha256(raw).hexdigest()

def read_json(path):
    def hook(pairs):
        d={}
        for k,v in pairs:
            if k in d:raise AssertionError('duplicate JSON property')
            d[k]=v
        return d
    def const(x):raise AssertionError('nonfinite JSON literal')
    return json.loads(path.read_text(),object_pairs_hook=hook,parse_constant=const)

def audit(root):
    root=Path(root)
    files={k:root/'native_sdk_capture'/k for k in ('capture.har','mcp.jsonl','pairs.json')}
    out=read_json(root/'real_sdk_capture_diagnosis.json')
    previous=read_json(root/'p4g_regression.json')
    har=read_json(files['capture.har'])
    links=read_json(files['pairs.json'])
    lines=files['mcp.jsonl'].read_text().splitlines()
    frames=[json.loads(x) for x in lines]
    assert len(frames)==9,('unexpected SDK wire frame count',len(frames))
    assert [x.get('method') for x in frames]==['initialize',None,'notifications/initialized','tools/list',None,'tools/call',None,'tools/call',None]
    assert [x['id'] for x in frames if x.get('method')=='tools/call']==[3,4]
    assert frames[5]['params']['name']==frames[7]['params']['name']=='fetch_record'
    assert [frames[5]['params']['arguments']['record_id'],frames[7]['params']['arguments']['record_id']]==['valid','missing']
    assert frames[6]['id']==3 and frames[8]['id']==4
    typed=frames[6]['result'];missing=frames[8]['result']
    assert typed['isError'] is False and missing['isError'] is False
    assert typed['structuredContent']=={'id':'valid','state':'ready','count':7}
    assert 'structuredContent' not in missing or missing['structuredContent'] is None
    assert missing['content'][0]['type']=='text'
    assert links['schema']=='risu-explicit-capture-pairing-v1'
    assert links['pairs']==[
        {'case_id':'SDK_NATIVE_200','target':'external-sdk-testserver','http_entry':0,'mcp_call_id':3,'tool':'fetch_record'},
        {'case_id':'SDK_NATIVE_404','target':'external-sdk-testserver','http_entry':1,'mcp_call_id':4,'tool':'fetch_record'}]
    entries=har['log']['entries']
    assert len(entries)==2
    original=[]
    for i,e in enumerate(entries):
        assert e['request']['method']=='GET'
        assert e['request']['url'].startswith('http://127.0.0.1:')
        assert e['request']['url'].endswith('/records/'+('valid' if i==0 else 'missing'))
        assert e['response']['status']==(200 if i==0 else 404)
        assert e['response']['content']['mimeType']=='application/json'
        raw=e['response']['content']['text']
        assert e['response']['bodySize']==len(raw.encode())
        original.append(json.loads(raw))
    assert original==[{'id':'valid','state':'ready','count':7},
                      {'code':'record_missing','message':'No such record'}]
    assert original[0]==typed['structuredContent']
    assert original[1]==json.loads(missing['content'][0]['text'])
    assert out['version']=='0.9.9-experimental'
    assert out['summary']['PRESERVED']==1 and out['summary']['LOSS']==1
    assert out['decision_summary']['PASS']==1 and out['decision_summary']['FAIL']==1
    r=out['recovery_v1']
    assert r['summary']=={'error_flag_lost':1,'full_body_exact_machine_mcp':1,
       'full_body_exact_json_text_mcp':1,'full_body_no_exact_carrier_mcp':0,'consumer_unverified':2}
    assert [(x['id'],x['error_flag'],x['mcp']['full_body']) for x in r['cases']]==[
        ('SDK_NATIVE_200','MATCH','EXACT_MACHINE'),
        ('SDK_NATIVE_404','ERROR_FLAG_LOST','EXACT_JSON_TEXT')]
    assert all(x['consumer'] is None for x in r['cases'])
    assert all(x['category']=='PARSED_JSON_TEXT_FIELD' for x in r['cases'][1]['mcp']['fields'])
    bridge=out['capture_bridge_v1']
    assert bridge['join_kind']=='EXPLICIT_UNVERIFIED_DEVELOPER_PAIRS'
    assert bridge['source_inference'] is False and bridge['live_execution'] is False
    assert bridge['capture_files_sha256']=={k:sha(p.read_bytes()) for k,p in files.items()}
    assert previous['summary']['PRESERVED']==2 and previous['summary']['LOSS']==3
    assert previous['diagnostic_summary']['ERROR_FLAG_LOST']==1
    assert previous['recovery_v1']['summary']['consumer_unverified']==0
    assert 'mcp==2.3.0' in (root/'installed_sdk_dependencies.txt').read_text().splitlines()
    exported=json.dumps(out)
    for bad in ['No such record','record_missing','/records/missing']:
        assert bad not in exported,('raw source value leaked',bad)
    return {'status':'PASS','schema':'risu-p4h-independent-native-capture-audit-v1',
        'source':'actual mcp==2.3.0 native stdio frames, local scripted demo server',
        'sdk_native_frames':len(frames),'http_gets':len(entries),
        'observed_status':[200,404],
        'product_results':['PRESERVED','LOSS'],
        'error_flag_lost_count':1,'recovery_exact_machine':1,'recovery_exact_json_text':1,
        'consumer_unverified':2,
        'provenance_scope':'user-declared pairing conditional; code-origin test fixture, not third-party production capture',
        'input_sha256':bridge['capture_files_sha256']}

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('results_root',type=Path)
    p.add_argument('out',type=Path)
    opts=p.parse_args()
    result=audit(opts.results_root)
    opts.out.parent.mkdir(exist_ok=True,parents=True)
    opts.out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print('P4H_INDEPENDENT_NATIVE_AUDIT',result['status'],result['product_results'])