"""Independent P4-O verifier of real third-party JPO original VCR replay outcomes.

Reads original wire and old/new RISU reports; never imports the semantic
mapping comparator. Purpose is to catch forged "fully preserved" claims,
lost error-flag red flags and mutated JPO case interpretations.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path

def check(root,contract,summary,check_files=True):
    original=json.loads((root/'independent_audit.json').read_text()) if check_files else None
    if check_files:
        assert original['status']=='PASS'
        assert original['original_upstream_cassettes_git_pinned']==2
        assert original['actual_replayed_raw_mcp_stdio_wires']==2
        assert original['independent_original_both_boundary_proof']==0
        assert original['field_fpr'] is None
    assert contract['schema']=='risu-observed-semantic-mapping-v1'
    assert len(contract['cases'])==2
    count=sum(len(row['rules']) for row in contract['cases'])
    assert count==8
    assert [x['case_id'] for x in contract['cases']]==['JPO_normal','JPO_logical_not_found']
    assert summary['external_original_commit']=='e7f0bcf2175823baaceb4844e84f9fc10ef00b40'
    assert summary['original_independently_recorded_complete_causal_pairs']==0
    expected={'normal':('100','2020015234',7),'logical_not_found':('107','9999999999',1)}
    audited=[]
    for case,(app_status,application,checks) in expected.items():
        old=json.loads((root/case/'risu_product_diagnosis.json').read_text())
        new=json.loads((root/case/'p4o_semantic_diagnosis.json').read_text())
        receipt=json.loads((root/case/'case_report.json').read_text())
        wire=(root/case/'observed_stdio_wire.jsonl').read_bytes()
        d=new['semantic_mapping_v1']
        assert new['version']=='0.9.11-experimental'
        assert new['results'][0]['verdict']==old['results'][0]['verdict']=='LOSS'
        assert new['results'][0]['losses']==old['results'][0]['losses']==['/result (missing)']
        assert new['results'][0]['decision_v1']['outcome']=='REVIEW'
        assert old['results'][0]['decision_v1']['outcome']=='REVIEW'
        assert d['schema']=='risu-observed-semantic-mapping-results-v1'
        assert d['mapping_authority']=='OPERATOR_DECLARED_NOT_INDEPENDENT_DOMAIN_PROOF'
        assert d['all_passing_is_not_full_semantic_preservation'] is True
        assert 'full information survival' in d['does_not_prove']
        assert d['rules_summary']=={'OBSERVED_MATCH':checks,'CONTRADICTED':0,'INSUFFICIENT':0}
        assert d['cases_summary']['ALL_DECLARED_CHECKS_MATCH']==1
        assert d['cases_summary']['DECLARED_MAPPING_CONTRADICTED']==0
        assert len(d['cases'])==1 and d['cases'][0]['outcome']=='ALL_DECLARED_CHECKS_MATCH'
        assert len(d['cases'][0]['checks'])==checks
        assert all(x['outcome']=='OBSERVED_MATCH' for x in d['cases'][0]['checks'])
        assert new['causal_gate_v1']['summary']['CONFIRMED_LOSS']==0
        assert new['results'][0]['causal_v1']['outcome']=='CONDITIONAL_MISMATCH'
        assert new['results'][0]['causal_v1']==old['results'][0]['causal_v1']
        assert receipt['original_http_status']==200
        assert receipt['original_application_status_code']==app_status
        assert receipt['original_vcr_interactions_replayed']==2
        assert receipt['mcp_call_isError'] is False
        assert receipt['mcp_call_has_structuredContent'] is True
        assert receipt['external_independently_recorded_same_call_mcp_wire'] is False
        assert hashlib.sha256(wire).hexdigest()==receipt['mcp_call_raw_wire_sha256']
        wire_rows=[json.loads(x) for x in wire.splitlines()]
        assert len(wire_rows)==7
        assert wire_rows[-2]['method']=='tools/call'
        assert wire_rows[-2]['params']['arguments']['application_number']==application
        assert wire_rows[-1]['result']==receipt['mcp_call_result']
        structured=wire_rows[-1]['result']['structuredContent']
        if case=='normal':
            assert structured['items'][0]['application_number']==application
            assert structured['not_found']==[]
            assert d['cases'][0]['checks'][0]['reason']=='DECLARED_FOUND_LOOKUP_TRANSITION_VALIDATED'
        else:
            assert structured['items']==[]
            assert structured['not_found']==[application]
            assert d['cases'][0]['checks'][0]['reason']=='DECLARED_NO_DATA_LOOKUP_TRANSITION_VALIDATED'
        # Do not count the untranslated source statusCode or remainAccessCount as
        # explicitly observed carried values. Declared rules check selected scope.
        checked_names=[r['id'] for r in contract['cases'][0 if case=='normal' else 1]['rules']]
        assert len(checked_names)==checks
        assert len(set(checked_names))==checks
        audited.append({'case':case,'original_http_status':200,
                        'original_app_status':app_status,'observed_mcp_isError':False,
                        'observed_structured_lookup':True,
                        'scoped_matches':checks,'raw_syntactic_loss':1,
                        'calibrated_review':1,'causal_confirmed_loss':0,
                        'actual_stdio_wire_sha256':hashlib.sha256(wire).hexdigest()})
    return audited

def mutants(root,contract,summary):
    # Perturb aggregate declarations to assert the independent verifier detects false claims.
    variations={
      'fake_mapping_schema':lambda x:x['contract'].update(schema='vendor-certified-full-equivalence'),
      'invent_complete_causal_pairs':lambda x:x['summary'].update(original_independently_recorded_complete_causal_pairs=2),
      'fake_source_commit':lambda x:x['summary'].update(external_original_commit='0'*40),
      'delete_equal_path_check':lambda x:x['contract']['cases'][0]['rules'].pop(),
      'duplicate_application_rule':lambda x:x['contract']['cases'][1]['rules'].append(copy.deepcopy(x['contract']['cases'][1]['rules'][0])),
    }
    caught=[]
    for name,fn in variations.items():
        obj={'contract':copy.deepcopy(contract),'summary':copy.deepcopy(summary)}
        fn(obj)
        try:check(root,obj['contract'],obj['summary'],check_files=False)
        except (AssertionError,KeyError,TypeError,ValueError):caught.append(name)
        else:raise AssertionError('P4O_AUDITOR_MISSED_FALSE_CLAIM '+name)
    assert len(caught)==len(variations)
    return caught

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--results',type=Path,required=True)
    p.add_argument('--contract',type=Path,required=True)
    a=p.parse_args()
    contract=json.loads(a.contract.read_text())
    summary=json.loads((a.results/'summary.json').read_text())
    rows=check(a.results,contract,summary)
    caught=mutants(a.results,contract,summary)
    audit={'schema':'risu-p4o-real-third-party-vcr-replay-semantic-audit-v1',
       'status':'PASS','original_third_party_http_source_records':2,
       'newly_replayed_actual_mcp_stdio_calls':2,'validated_declared_rules':8,
       'validated_cases':2,'unmapped_source_fields_not_certified':True,
       'confirmed_causal_loss':0,'independent_external_same_call_wire':0,'field_fpr':None,
       'mutations_detected':caught,'per_case':rows}
    (a.results/'p4o_independent_audit.json').write_text(json.dumps(audit,indent=2,sort_keys=True)+'\n')
    print('P4O_INDEPENDENT_SEMANTIC_AUDIT_PASS',json.dumps(audit,sort_keys=True),flush=True)

if __name__=='__main__':main()
