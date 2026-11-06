"""Derive an explicitly hypothetical change directly from the *observed* P4-S snapshot.

Never modifies the observed input. It is a controlled what-if test, NOT a
claim about any publisher deployment or the actual original developer.
"""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
from risu_contract_history import load_snapshot, _policy_rules

def build(observed: dict) -> tuple[dict,dict]:
    schema=copy.deepcopy(observed['schema'])
    properties=schema['properties']; required=list(schema['required'])
    if set(required)!={'summary','items','provenance'}:
        raise ValueError('P4-S source requiredness differs from frozen observed baseline')
    if properties['items'].get('type')!='array' or properties['not_found'].get('type')!='array':
        raise ValueError('P4-S expected original item/not_found type changed')
    if properties['provenance'].get('type')!='object' or len(properties['provenance'].get('required',[]))!=4:
        raise ValueError('P4-S provenance changed; revise hypothetical scenario before comparing')
    properties['items']={'type':'string','description':'SYNTHETIC upgrade: array converted to string'}
    properties['quota_remaining']={'type':'integer','description':'SYNTHETIC extra required quota field'}
    schema['required']=[x for x in required if x!='provenance']+['not_found','quota_remaining']
    policy=copy.deepcopy(observed['operator_policy'])
    if policy.get('schema')!='risu-explicit-field-obligation-policy-v1':
        raise ValueError('Expected actual P4-S declared operator-policy format')
    cases=policy.get('cases')
    if not isinstance(cases,list) or len(cases)!=1 or cases[0].get('case_id')!='JPO_normal':
        raise ValueError('Unrecognized source policy case')
    obligations=cases[0]['obligations']
    original={r['id']:r for r in obligations}
    if 'operator_quota_visible' not in original or 'operator_error_details_if_nonempty' not in original:
        raise ValueError('Original operator obligations absent')
    obligations[:]=[r for r in obligations if r['id']!='operator_quota_visible']
    error=next(r for r in obligations if r['id']=='operator_error_details_if_nonempty')
    if error['when']!='SOURCE_NONEMPTY' or error['importance']!='HIGH':
        raise ValueError('Original conditional/error importance changed')
    error['when']='ALWAYS'
    error['importance']='CRITICAL'
    error['importance_reason']='SYNTHETIC revised operator rule: error text is required even when source value is empty.'
    obligations.extend([
       {'id':'synthetic_registration_date','basis':'OPERATOR_POLICY',
        'source_path':'/result/data/registrationDate','when':'ALWAYS',
        'allow_normalized':False,'importance':'HIGH',
        'importance_reason':'SYNTHETIC operator wants registration-date preservation.'},
       {'id':'synthetic_request_id','basis':'OPERATOR_POLICY',
        'source_path':'/result/requestId','when':'ALWAYS',
        'allow_normalized':False,'importance':'MEDIUM',
        'importance_reason':'SYNTHETIC trace-correlation duty; no claim that upstream supplies this field.'}])
    # 1 rule removed, 2 added, 3 error-rule attribute changes = 6 distinct events.
    assert len(_policy_rules(policy)) == len(_policy_rules(observed['operator_policy'])) + 1
    return schema,policy

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--observed',required=True)
    p.add_argument('--schema-out',required=True)
    p.add_argument('--policy-out',required=True)
    a=p.parse_args()
    observed=load_snapshot(a.observed)
    if observed['source_kind']!='recorded-tools-list':
        raise ValueError('Scenario derivation requires a recorded tools/list baseline')
    schema,policy=build(observed)
    for path,value in [(a.schema_out,schema),(a.policy_out,policy)]:
        out=Path(path)
        if out.exists():raise ValueError('Refusing to overwrite upgrade fixture')
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False)+'\n')
    print('P4T_EXPLICIT_HYPOTHETICAL_UPGRADE_DERIVED_FROM_REAL_REPLAY_PASS')

if __name__=='__main__':main()
