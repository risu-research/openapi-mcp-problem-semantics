"""P4-R independent source VCR -> real MCP wire -> product classification audit.

No import of risu_residual/arraymatch/coverage/semantics. Inspect the exact
third-party upstream source and code files at pinned Git revision. No network,
no execution of original application code, and no raw values in the receipt.
"""
from __future__ import annotations
import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import yaml

ROOT=Path(__file__).resolve().parent
PINS={
'commit':'e7f0bcf2175823baaceb4844e84f9fc10ef00b40',
'vcr':'e10ad7149bcf3d652cbbf16bc3c6107220e7ea5f',
'client':'3d6d5c27a053879716ed4853ed9d41765af788fe',
'models':'12917122e994e81e3e22b5dda730119a86593771',
'jpo_tool':'603ecc6fd1f1dba905bd34331b294b484a823ce6'
}


def gitblob(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()

def _assert_source_module(path,pin):
    raw=path.read_bytes()
    assert gitblob(raw)==PINS[pin],('PINNED_THIRD_PARTY_SOURCE_CHANGED',pin)
    return raw.decode('utf-8')

def _ast_method(tree,name):
    matched=[x for x in ast.walk(tree) if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef)) and x.name==name]
    assert len(matched)==1,('MISSING_UNIQUE_ORIGINAL_METHOD',name)
    return matched[0]

def _static_origins(external):
    client=_assert_source_module(external/'src/patent_client_agents/jpo/client.py','client')
    models=_assert_source_module(external/'src/patent_client_agents/jpo/models.py','models')
    tool=_assert_source_module(external/'src/patent_client_agents/mcp/tools/jpo.py','jpo_tool')
    ctree=ast.parse(client);mtree=ast.parse(models);ttree=ast.parse(tool)
    process=ast.get_source_segment(client,_ast_method(ctree,'get_design_progress'))
    assert process and 'result = self._parse_result(data)' in process
    assert 'return DesignProgressData.model_validate(result.data)' in process
    assert 'return ApiResult.model_validate(data.get("result", data))' in client
    m=ast.get_source_segment(models,_ast_method(mtree,'has_data'))
    assert 'status_code not in EMPTY_STATUS_CODES' in m
    api=next(x for x in ast.walk(mtree) if isinstance(x,ast.ClassDef) and x.name=='ApiResult')
    declared=set()
    for a in api.body:
        if isinstance(a,ast.AnnAssign) and isinstance(a.target,ast.Name):declared.add(a.target.id)
    assert {'status_code','error_message','remain_access_count','data'}.issubset(declared)
    parent=next(x for x in ast.walk(mtree) if isinstance(x,ast.ClassDef) and x.name=='ParentApplicationInfo')
    expected={'parent_application_number','filing_date','parent_application_category','parent_application_law_code'}
    pdeclared={x.target.id:x for x in parent.body if isinstance(x,ast.AnnAssign) and isinstance(x.target,ast.Name)}
    assert set(pdeclared)==expected
    for field in expected:
        annotation=pdeclared[field]
        assert isinstance(annotation.value,ast.Call)
        assert any(k.arg=='default' and isinstance(k.value,ast.Constant) and k.value.value=='' for k in annotation.value.keywords)
    body=ast.get_source_segment(tool,_ast_method(ttree,'get_jpo_progress'))
    assert body and 'return dump(result) if result else None' in body
    assert 'items, not_found = await fetch_many(' in body
    return {'owner_git_commit_pinned':True,'original_client_selects_only_result_data':True,
            'original_jpo_tool_serializes_typed_data_items':True,
            'original_parent_model_has_four_empty_string_defaults':True,
            'api_result_has_but_progress_output_does_not_return_quota_and_error_envelope':True,
            'does_not_prove_required_metadata_preservation':True}


def _find_keys(v):
    out=set();stack=[v]
    while stack:
        x=stack.pop()
        if isinstance(x,dict):out.update(x);stack.extend(x.values())
        elif isinstance(x,list):stack.extend(x)
    return out


def independent_review(external,results):
    actual=subprocess.check_output(['git','-C',str(external),'rev-parse','HEAD'],text=True).strip()
    assert actual==PINS['commit'],('PINNED_THIRD_PARTY_COMMIT_DRIFT',actual)
    provenance=_static_origins(external)
    origin=external/'tests/cassettes/tests_jpo_test_live_py_TestMcpDispatchLive_test_progress_design.yaml'
    raw=origin.read_bytes()
    assert gitblob(raw)==PINS['vcr']
    y=yaml.safe_load(raw);s=[x for x in y['interactions'] if x['request']['method']=='GET']
    assert len(s)==1 and s[0]['response']['status']['code']==200
    body=json.loads(s[0]['response']['body']['string'])
    assert body['result']['statusCode']=='100'
    http=json.loads((results/'risu_native_inputs/normal/capture.har').read_text())
    derived=json.loads(http['log']['entries'][0]['response']['content']['text'])
    assert derived==body, 'derived HAR differs from original external HTTP VCR'
    report=json.loads((results/'normal/p4r_residual_classification.json').read_text())
    assert report['version']=='0.9.14-experimental'
    old=json.loads((results/'normal/p4q_array_diagnosis.json').read_text())
    for key in ('summary','diagnostic_summary','decision_summary','causal_gate_v1','source_coverage_with_arrays_v1','field_coverage_v1','array_identity_v1','semantic_mapping_v1'):
        assert report[key]==old[key],('P4R_CHANGED_LEGACY_RESULT',key)
    assert report['results'][0]['verdict']=='LOSS'
    assert report['results'][0]['decision_v1']['outcome']=='REVIEW'
    assert report['causal_gate_v1']['summary']['CONFIRMED_LOSS']==0
    assert report['results'][0]['causal_v1']['outcome']=='CONDITIONAL_MISMATCH'
    wire=(results/'normal/observed_stdio_wire.jsonl').read_bytes()
    rows=[json.loads(line) for line in wire.splitlines()]
    assert len(rows)==7
    assert rows[-2]['method']=='tools/call' and rows[-2]['params']['name']=='get_jpo_progress'
    assert rows[-1].get('id')==rows[-2]['id']==3
    mcp=rows[-1]['result']
    assert mcp.get('isError') is False and isinstance(mcp['structuredContent']['items'],list)
    assert len(mcp['structuredContent']['items'])==1
    structured=mcp['structuredContent'];item=structured['items'][0]
    src=body['result'];data=src['data']
    pairs=[('disappearanceDate','disappearance_date'),('erasureIdentifier','erasure_identifier'),
        ('expireDate','expire_date'),('principalDesignApplicationNumber','principal_design_application_number'),
        ('priorityRightInformation','priority_right_information'),('publicationDate','publication_date'),
        ('registrationDate','registration_date')]
    assert len(pairs)==7
    for a,b in pairs:
        assert type(data[a]) is type(item[b]) and data[a]==item[b],('P4R_ORIGINAL_VALUE_DID_NOT_SURVIVE',a)
    assert data['parentApplicationInformation']=={}
    parent=item['parent_application_information']
    assert isinstance(parent,dict) and set(parent)=={'parent_application_number','filing_date','parent_application_category','parent_application_law_code'}
    assert all(type(x) is str and not x for x in parent.values())
    assert src['errorMessage']=='' and type(src['remainAccessCount']) is str and src['remainAccessCount']
    names=_find_keys(mcp)
    assert not {'errorMessage','error_message','remainAccessCount','remain_access_count'} & names
    assert all('errorMessage' not in text.get('text','') and 'remainAccessCount' not in text.get('text','') and
          'remain_access_count' not in text.get('text','') for text in mcp['content'] if text.get('type')=='text')
    assert all(src['remainAccessCount'] not in text.get('text','') for text in mcp['content'] if text.get('type')=='text')
    assert src['remainAccessCount'] not in json.dumps(structured,ensure_ascii=False)
    r=report['residual_disposition_v1']
    c=r['cases'][0];t=r['summary']
    assert (t['source_leaf_units'],t['baseline_verified'],t['exact_new'],t['normalized_new'],
            t['observed_nonexposure'],t['final_verified'],t['remaining_unverified'],t['final_verified_pct']) == (134,124,7,1,2,132,2,98.51)
    assert set(c['remaining_unverified_source_paths'])=={'/result/errorMessage','/result/remainAccessCount'}
    checks={x['id']:x for x in c['rules']}
    assert len(checks)==10
    assert sum(x['outcome']=='VERIFIED_EXACT_REMAP' for x in checks.values())==7
    assert sum(x['outcome']=='VERIFIED_EMPTY_STRUCTURAL_EXPANSION' for x in checks.values())==1
    assert sum(x['outcome']=='OBSERVED_NONEXPOSURE' for x in checks.values())==2
    assert r['observed_nonexposure_is_not_confirmed_semantic_loss']
    assert '799' not in json.dumps(r)
    # Independently check the second original upstream not-found case remains unchanged.
    other=json.loads((results/'logical_not_found/p4p_field_coverage.json').read_text())
    assert other['field_coverage_v1']['cases'][0]['full_source']['total_source_leaf_units']==4
    assert other['field_coverage_v1']['cases'][0]['full_source']['coverage_verified_units']==2
    assert other['causal_gate_v1']['summary']['CONFIRMED_LOSS']==0
    return {'schema':'risu-p4r-independent-original-source-and-mcp-wire-audit-v1',
            'status':'PASS','original_owner':'parkerhancock/patent-client-agents',
            'pinned_original_git_commit':PINS['commit'],'original_vcr_git_blob_sha1':gitblob(raw),
            'original_http_200':True,'original_app_status_100':True,
            'source_field_leaf_units':134,'previous_verified':124,
            'exact_typed_remaps':7,'empty_object_structural_normalization':1,
            'observed_not_exposed_envelope_fields':2,'verified_source_leaf_units':132,
            'remaining_unverified_fields':2,'verified_source_pct':98.51,
            'all_original_two_cases_verified':134,'all_original_two_cases_source_leaf_units':138,
            'all_two_case_verified_pct':round(134/138*100,2),
            'raw_syntactic_LOSS_unchanged':True,'calibrated_REVIEW_unchanged':True,
            'independent_original_same_call_complete_causal_pairs':0,
            'field_FPR':None,'provenance':provenance,
            'nonexposure_is_not_domain_required_data_loss':True,
            'mcp_wire_is_our_replay_from_owner_http_not_owner_original_wire':True}


def false_claim_checks(r):
    changes={
        'fake_source_total':lambda x:x.update(source_field_leaf_units=133),
        'fake_full_preservation':lambda x:x.update(verified_source_leaf_units=134),
        'fake_exact_remap_count':lambda x:x.update(exact_typed_remaps=9),
        'hide_envelope_nonexposure':lambda x:x.update(observed_not_exposed_envelope_fields=0),
        'falsify_normalization':lambda x:x.update(empty_object_structural_normalization=0),
        'fake_causal_attestation':lambda x:x.update(independent_original_same_call_complete_causal_pairs=1),
        'fake_FPR_zero':lambda x:x.update(field_FPR=0),
        'fake_case_total':lambda x:x.update(all_original_two_cases_verified=138),
        'invent_original_wire':lambda x:x.update(mcp_wire_is_our_replay_from_owner_http_not_owner_original_wire=False),
        'false_domain_loss':lambda x:x.update(nonexposure_is_not_domain_required_data_loss=False)
    }
    def check(x):
        assert x['status']=='PASS'
        assert (x['source_field_leaf_units'],x['previous_verified'],x['exact_typed_remaps'],
                x['empty_object_structural_normalization'],x['observed_not_exposed_envelope_fields'],
                x['verified_source_leaf_units'],x['remaining_unverified_fields'])==(134,124,7,1,2,132,2)
        assert x['field_FPR'] is None and x['all_original_two_cases_verified']==134
        assert x['independent_original_same_call_complete_causal_pairs']==0
        assert x['nonexposure_is_not_domain_required_data_loss'] is True
        assert x['mcp_wire_is_our_replay_from_owner_http_not_owner_original_wire'] is True
    check(r);caught=[]
    for name,fn in changes.items():
        forged=copy.deepcopy(r);fn(forged)
        try:check(forged)
        except AssertionError:caught.append(name)
        else:raise AssertionError('INDEPENDENT_AUDITOR_ACCEPTED_FORGED_CLAIM: '+name)
    assert len(caught)==len(changes)==10
    return caught


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--external',type=Path,required=True)
    p.add_argument('--results',type=Path,required=True);a=p.parse_args()
    receipt=independent_review(a.external,a.results)
    receipt['ten_false_claims_blocked']=false_claim_checks(receipt)
    (a.results/'p4r_independent_audit.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print('P4R_INDEPENDENT_VCR_AND_RAW_MCP_WIRE_AUDIT_PASS',json.dumps({
        'from_134':receipt['source_field_leaf_units'],
        'verified':receipt['verified_source_leaf_units'],
        'exact':receipt['exact_typed_remaps'],
        'normalized':receipt['empty_object_structural_normalization'],
        'exposed_absent':receipt['observed_not_exposed_envelope_fields'],
        'false_claims_blocked':len(receipt['ten_false_claims_blocked'])},sort_keys=True),flush=True)
