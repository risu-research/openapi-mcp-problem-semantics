"""P4-R fail-closed tests. Local fixture is a clearly labeled synthetic
reconstruction; GitHub CI uses the pinned *original* JPO VCR replay instead.
"""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from risu_capture import load_capture_directory
from risu_residual import assess_residual, _load_contract

HERE=Path(__file__).resolve().parents[1]
ROOT=HERE.parent
CAPTURE=Path(os.getenv('P4R_CAPTURE',str(ROOT/'p4n/results/risu_native_inputs/normal')))
BASE=Path(os.getenv('P4R_BASE_REPORT',str(ROOT/'p4n/results/normal/p4q_array_diagnosis.json')))
CONTRACT=HERE/'fixtures/jpo_residual_fields.json'
SEM=HERE/'fixtures/jpo_semantic_normal_only.json'
ARRAY=HERE/'fixtures/jpo_arrays.json'


def source():
    payload,_=load_capture_directory(CAPTURE)
    baseline=json.loads(BASE.read_text())['source_coverage_with_arrays_v1']
    return payload,baseline


def check(payload,baseline,contract=CONTRACT):
    return assess_residual(payload,baseline,contract,CAPTURE)


def rules(report):
    return {r['id']:r for r in report['cases'][0]['rules']}


def cli(extra=None):
    args=[sys.executable,'-m','risu_probe','analyze',str(CAPTURE),'--recovery',
          '--semantic-map',str(SEM),'--field-coverage','--array-map',str(ARRAY),
          '--residual-map',str(CONTRACT),'--format','json']
    if extra:args+=extra
    return subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=35)


class ResidualOriginalFieldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture,cls.original_base=source()

    def setUp(self):
        self.p=copy.deepcopy(self.fixture)
        self.b=copy.deepcopy(self.original_base)
        self.body=self.p['cases'][0]['source']['body']['result']
        self.item=self.p['cases'][0]['mcp']['structuredContent']['items'][0]

    def test_01_exact_original_p4q_baseline(self):
        c=self.b['cases'][0]
        self.assertEqual((c['total_source_leaf_units'],c['combined_verified_units'],c['combined_unverified_units']),(134,124,10))
    def test_02_all_ten_paths_declared_exactly(self):
        spec,_=_load_contract(CONTRACT,CAPTURE)
        self.assertEqual({x['source_path'] for x in spec['cases'][0]['rules']},set(self.b['cases'][0]['still_unverified_source_paths']))
    def test_03_expected_classification(self):
        r=check(self.p,self.b)
        self.assertEqual((r['summary']['exact_new'],r['summary']['normalized_new'],r['summary']['observed_nonexposure']),(7,1,2))
        self.assertEqual((r['summary']['final_verified'],r['summary']['remaining_unverified'],r['summary']['final_verified_pct']),(132,2,98.51))
    def test_04_unchanged_lookup_status_not_recounted(self):
        self.assertEqual(check(self.p,self.b)['cases'][0]['prior_verified'],124)
    def test_05_string_alias_mapped_strictly(self):
        for f,t in [('disappearanceDate','disappearance_date'),('erasureIdentifier','erasure_identifier'),
                    ('expireDate','expire_date'),('principalDesignApplicationNumber','principal_design_application_number'),
                    ('publicationDate','publication_date'),('registrationDate','registration_date')]:
            self.assertEqual(self.body['data'][f],self.item[t]);self.assertIs(type(self.body['data'][f]),type(self.item[t]))
    def test_06_empty_array_alias_not_glossed_over(self):
        self.assertEqual(self.body['data']['priorityRightInformation'],[])
        self.assertEqual(self.item['priority_right_information'],[])
    def test_07_normalized_parent_object_is_not_exact(self):
        r=rules(check(self.p,self.b))['parent_application_empty_expanded']
        self.assertEqual(r['outcome'],'VERIFIED_EMPTY_STRUCTURAL_EXPANSION')
        self.assertFalse(r['verified_exact']);self.assertTrue(r['verified_normalized'])
        self.assertEqual(self.body['data']['parentApplicationInformation'],{})
    def test_08_empty_expansion_has_four_fields(self):
        self.assertEqual(set(self.item['parent_application_information']),{'filing_date','parent_application_category','parent_application_law_code','parent_application_number'})
        self.assertTrue(all(x=='' for x in self.item['parent_application_information'].values()))
    def test_09_quota_absent_observed(self):
        self.assertEqual(rules(check(self.p,self.b))['source_remaining_quota_envelope']['outcome'],'OBSERVED_NONEXPOSURE')
    def test_10_empty_error_message_field_absent_observed(self):
        self.assertEqual(rules(check(self.p,self.b))['source_error_message_envelope']['outcome'],'OBSERVED_NONEXPOSURE')
    def test_11_value_tampering_is_contradiction(self):
        self.item['registration_date']='19000101'
        self.assertEqual(rules(check(self.p,self.b))['registration_date']['outcome'],'CONTRADICTED')
    def test_12_numeric_type_coercion_is_contradiction(self):
        self.item['erasure_identifier']=0
        self.assertEqual(rules(check(self.p,self.b))['erasure_identifier']['outcome'],'CONTRADICTED')
    def test_13_empty_string_removed_is_contradiction(self):
        self.item.pop('publication_date')
        self.assertEqual(rules(check(self.p,self.b))['publication_date']['outcome'],'CONTRADICTED')
    def test_14_empty_array_replaced_is_contradiction(self):
        self.item['priority_right_information']={}
        self.assertEqual(rules(check(self.p,self.b))['priority_right_information']['outcome'],'CONTRADICTED')
    def test_15_source_object_not_empty_rejected(self):
        self.body['data']['parentApplicationInformation']={'parentApplicationNumber':'2020000000'}
        # Source empty-object leaf became a nested subtree: P4-Q denominator invalid. Fail closed.
        with self.assertRaises(ValueError):check(self.p,self.b)
    def test_16_nonempty_default_invented(self):
        self.item['parent_application_information']['parent_application_number']='invented'
        self.assertEqual(rules(check(self.p,self.b))['parent_application_empty_expanded']['outcome'],'CONTRADICTED')
    def test_17_extra_default_field_invented(self):
        self.item['parent_application_information']['extra']=''
        self.assertEqual(rules(check(self.p,self.b))['parent_application_empty_expanded']['outcome'],'CONTRADICTED')
    def test_18_default_target_null_rejected(self):
        self.item['parent_application_information']=None
        self.assertEqual(rules(check(self.p,self.b))['parent_application_empty_expanded']['outcome'],'CONTRADICTED')
    def test_19_quota_reappears_by_field_name(self):
        self.item['remain_access_count']='799'
        self.assertEqual(rules(check(self.p,self.b))['source_remaining_quota_envelope']['outcome'],'CONTRADICTED')
    def test_20_quota_token_in_summary_is_not_proof_of_absence(self):
        self.p['cases'][0]['mcp']['structuredContent']['summary']+=' 799'
        self.assertEqual(rules(check(self.p,self.b))['source_remaining_quota_envelope']['outcome'],'INSUFFICIENT')
    def test_21_named_field_in_mcp_text_is_detected(self):
        self.p['cases'][0]['mcp']['content'][0]['text']+=' remainAccessCount'
        self.assertEqual(rules(check(self.p,self.b))['source_remaining_quota_envelope']['outcome'],'CONTRADICTED')
    def test_22_unreadable_mcp_content_cannot_prove_nonexposure(self):
        self.p['cases'][0]['mcp']['content']=[{'type':'image','data':'xxx'}]
        self.assertEqual(rules(check(self.p,self.b))['source_remaining_quota_envelope']['outcome'],'INSUFFICIENT')
    def test_23_nonempty_error_message_no_absence_credit(self):
        self.body['errorMessage']='Internal error encountered'
        self.assertEqual(rules(check(self.p,self.b))['source_error_message_envelope']['outcome'],'INSUFFICIENT')
    def test_24_missing_source_field_cannot_count(self):
        del self.body['data']['registrationDate']
        with self.assertRaises(ValueError):check(self.p,self.b)
    def test_25_baseline_truncation_rejected(self):
        self.b['cases'][0]['still_unverified_paths_truncated']=True
        with self.assertRaises(ValueError):check(self.p,self.b)
    def test_26_alias_must_include_original_name(self):
        spec=json.loads(CONTRACT.read_text());spec['cases'][0]['rules'][-1]['field_aliases']=['phantom_field']
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'bad.json';path.write_text(json.dumps(spec))
            with self.assertRaises(ValueError):check(self.p,self.b,path)
    def test_27_duplicate_source_claim_rejected(self):
        spec=json.loads(CONTRACT.read_text());spec['cases'][0]['rules'][-1]['source_path']=spec['cases'][0]['rules'][0]['source_path']
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'bad.json';path.write_text(json.dumps(spec))
            with self.assertRaises(ValueError):check(self.p,self.b,path)
    def test_28_duplicate_target_claim_rejected(self):
        spec=json.loads(CONTRACT.read_text());spec['cases'][0]['rules'][1]['target_path']=spec['cases'][0]['rules'][0]['target_path']
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'bad.json';path.write_text(json.dumps(spec))
            with self.assertRaises(ValueError):check(self.p,self.b,path)
    def test_29_json_output_does_not_reveal_token(self):
        r=check(self.p,self.b)
        blob=json.dumps(r,ensure_ascii=False)
        self.assertNotIn('"799"',blob);self.assertNotIn('2020015234',blob);self.assertNotIn('20450624',blob)
        self.assertTrue(r['observed_nonexposure_is_not_confirmed_semantic_loss'])
    def test_30_no_causal_proof_by_classifier(self):
        r=check(self.p,self.b)
        self.assertFalse(r['cases'][0]['independent_causality_verified'])
        self.assertFalse(any(x['causal_loss_confirmed'] for x in r['cases'][0]['rules']))
    def test_31_cli_full_scoped_pass(self):
        p=cli();self.assertEqual(p.returncode,0,p.stderr)
        r=json.loads(p.stdout)
        self.assertEqual(r['version'],'0.9.14-experimental')
        self.assertEqual(r['residual_disposition_v1']['summary']['final_verified'],132)
        self.assertEqual(r['results'][0]['verdict'],'LOSS')
        self.assertEqual(r['causal_gate_v1']['summary']['CONFIRMED_LOSS'],0)
        self.assertEqual(r['results'][0]['decision_v1']['outcome'],'REVIEW')
    def test_32_cli_strict_gap_uses_exit_1_not_proven_loss(self):
        p=cli(['--fail-on-residual-gap']);self.assertEqual(p.returncode,1,p.stderr)
        self.assertEqual(json.loads(p.stdout)['causal_gate_v1']['summary']['CONFIRMED_LOSS'],0)
    def test_33_cli_nonexposure_gate_exit_1(self):
        p=cli(['--fail-on-residual-nonexposure']);self.assertEqual(p.returncode,1,p.stderr)
    def test_34_cli_contradiction_flag_no_false_block(self):
        p=cli(['--fail-on-residual-contradiction']);self.assertEqual(p.returncode,0,p.stderr)
    def test_35_cli_rejects_missing_array_map(self):
        p=cli();q=subprocess.run([sys.executable,'-m','risu_probe','analyze',str(CAPTURE),
            '--semantic-map',str(SEM),'--field-coverage','--residual-map',str(CONTRACT)],
            capture_output=True,text=True,timeout=30)
        self.assertEqual(q.returncode,2,q.stderr)
    def test_36_cli_rejects_failure_flag_without_map(self):
        q=subprocess.run([sys.executable,'-m','risu_probe','analyze',str(CAPTURE),
            '--fail-on-residual-gap','--format','json'],capture_output=True,text=True,timeout=30)
        self.assertEqual(q.returncode,2,q.stderr)
    def test_37_legacy_default_run_unchanged(self):
        q=subprocess.run([sys.executable,'-m','risu_probe','analyze',str(CAPTURE),
            '--format','json'],capture_output=True,text=True,timeout=30)
        self.assertEqual(q.returncode,0,q.stderr)
        self.assertNotIn('residual_disposition_v1',json.loads(q.stdout))
    def test_38_different_map_fails_closed(self):
        spec=json.loads(CONTRACT.read_text());spec['schema']='bad'
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'bad.json';path.write_text(json.dumps(spec))
            with self.assertRaises(ValueError):check(self.p,self.b,path)

if __name__=='__main__':unittest.main()
