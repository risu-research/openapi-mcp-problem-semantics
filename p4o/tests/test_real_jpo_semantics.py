"""P4-O real third-party original-JPO VCR replay with real SDK stdio wire tests.

These P4-N observations are RISU-run replays, not independently published
third-party same-call MCP wire. The test compares real replayed wire bytes,
never a synthetic replacement for them. No live API or external LLM.
"""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
NATIVE=ROOT/'p4n'/'results'/'risu_native_inputs'
MAP=ROOT/'p4o'/'fixtures'/'jpo_observed_mapping.json'
CLI=ROOT/'p4n'/'external_upstream'/'.venv'/'bin'/'risu-probe'

class RealJpoWireSemanticContract(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.data=self.root/'data';shutil.copytree(NATIVE/'normal',self.data)
        self.mapping=self.root/'map.json';self.select_map('normal')

    def select_map(self,name):
        cfg=json.loads(MAP.read_text())
        case_id='JPO_'+name
        cfg['cases']=[x for x in cfg['cases'] if x['case_id']==case_id]
        assert len(cfg['cases'])==1
        self.mapping.write_text(json.dumps(cfg))

    def use_case(self,name):
        shutil.rmtree(self.data)
        shutil.copytree(NATIVE/name,self.data)
        self.select_map(name)

    def cli(self,*flags):
        return subprocess.run([str(CLI),'analyze',str(self.data),'--recovery','--format','json',
                               '--semantic-map',str(self.mapping),*flags],
            capture_output=True,text=True,timeout=18,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})

    def check(self):
        proc=self.cli()
        self.assertEqual(proc.returncode,0,proc.stderr)
        return json.loads(proc.stdout)

    def update_mcp(self,mutator):
        path=self.data/'mcp.jsonl'
        rows=[json.loads(line) for line in path.read_text().splitlines()]
        mutator(rows)
        path.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows))

    def update_har(self,mutator):
        path=self.data/'capture.har'
        obj=json.loads(path.read_text());mutator(obj)
        path.write_text(json.dumps(obj,ensure_ascii=False))

    def update_map(self,mutator):
        data=json.loads(self.mapping.read_text());mutator(data)
        self.mapping.write_text(json.dumps(data))

    def test_real_found_case_all_declared_values_match(self):
        r=self.check()
        self.assertEqual(r['semantic_mapping_v1']['rules_summary']['OBSERVED_MATCH'],7)
        self.assertEqual(r['semantic_mapping_v1']['cases_summary']['ALL_DECLARED_CHECKS_MATCH'],1)
        self.assertEqual(r['causal_gate_v1']['summary']['CONFIRMED_LOSS'],0)

    def test_real_no_data_case_status_to_notfound(self):
        self.use_case('logical_not_found')
        r=self.check()
        self.assertEqual(r['semantic_mapping_v1']['rules_summary']['OBSERVED_MATCH'],1)
        self.assertEqual(r['semantic_mapping_v1']['cases'][0]['checks'][0]['reason'],
                         'DECLARED_NO_DATA_LOOKUP_TRANSITION_VALIDATED')
        self.assertEqual(r['results'][0]['verdict'],'LOSS')
        self.assertEqual(r['results'][0]['decision_v1']['outcome'],'REVIEW')
        self.assertEqual(r['causal_gate_v1']['summary']['CONFIRMED_LOSS'],0)

    def test_identity_of_source_frozen(self):
        r=self.check()
        self.assertEqual(r['semantic_mapping_v1']['mapping_authority'],
                         'OPERATOR_DECLARED_NOT_INDEPENDENT_DOMAIN_PROOF')
        self.assertTrue(r['semantic_mapping_v1']['all_passing_is_not_full_semantic_preservation'])

    def test_wildly_different_source_value_cannot_pass(self):
        def change(h):
            row=h['log']['entries'][0]['response']['content']
            x=json.loads(row['text']);x['result']['data']['designArticle']='fabricated';row['text']=json.dumps(x)
        self.update_har(change)
        self.assertEqual(self.check()['semantic_mapping_v1']['rules_summary']['CONTRADICTED'],1)

    def test_mcp_mapped_value_removed_cannot_pass(self):
        self.update_mcp(lambda x:x[-1]['result']['structuredContent']['items'][0].pop('design_class'))
        r=self.check()
        self.assertEqual(r['semantic_mapping_v1']['rules_summary']['CONTRADICTED'],1)

    def test_missing_structured_content_not_satisfied_by_text(self):
        self.update_mcp(lambda x:x[-1]['result'].pop('structuredContent'))
        r=self.check()
        self.assertGreater(r['semantic_mapping_v1']['rules_summary']['INSUFFICIENT'],0)

    def test_no_data_wrong_ident_cannot_pass(self):
        self.use_case('logical_not_found')
        self.update_mcp(lambda x:x[-1]['result']['structuredContent'].__setitem__('not_found',['2222222222']))
        self.assertEqual(self.check()['semantic_mapping_v1']['rules_summary']['CONTRADICTED'],1)

    def test_no_data_invalid_source_status_cannot_pass(self):
        self.use_case('logical_not_found')
        def change(h):
            obj=h['log']['entries'][0]['response']['content']
            v=json.loads(obj['text']);v['result']['statusCode']='100';obj['text']=json.dumps(v)
        self.update_har(change)
        self.assertEqual(self.check()['semantic_mapping_v1']['rules_summary']['CONTRADICTED'],1)

    def test_no_data_nonempty_source_cannot_pass(self):
        self.use_case('logical_not_found')
        def change(h):
            obj=h['log']['entries'][0]['response']['content']
            v=json.loads(obj['text']);v['result']['data']={'value':'unexpected'};obj['text']=json.dumps(v)
        self.update_har(change)
        self.assertEqual(self.check()['semantic_mapping_v1']['rules_summary']['CONTRADICTED'],1)

    def test_http_error_flag_missing_never_whitewashed(self):
        self.update_har(lambda h:h['log']['entries'][0]['response'].__setitem__('status',404))
        r=self.check()['semantic_mapping_v1']
        self.assertEqual(r['cases_summary']['DECLARED_MAPPING_CONTRADICTED'],1)
        self.assertIn('BUILTIN_HTTP_ERROR_FLAG',[x['id'] for x in r['cases'][0]['checks']])

    def test_provenance_not_promoted_by_mapping(self):
        self.assertEqual(self.check()['causal_gate_v1']['summary']['CONFIRMED_LOSS'],0)

    def test_contradiction_fails_strict_semantic_flag(self):
        self.use_case('logical_not_found')
        self.update_mcp(lambda x:x[-1]['result']['structuredContent']['not_found'].clear())
        self.assertEqual(self.cli('--fail-on-semantic-contradiction').returncode,1)

    def test_true_match_has_success_exit(self):
        self.assertEqual(self.cli('--fail-on-semantic-contradiction').returncode,0)

    def test_duplicate_declaration_rejected(self):
        self.update_map(lambda x:x['cases'].append(copy.deepcopy(x['cases'][0])))
        self.assertEqual(self.cli().returncode,2)

    def test_unknown_code_transform_disallowed(self):
        self.update_map(lambda x:x['cases'][0]['rules'][0].__setitem__('python','lambda a:b'))
        self.assertEqual(self.cli().returncode,2)

    def test_dev_supplied_case_id_wrong_rejected(self):
        self.update_map(lambda x:x['cases'][0].__setitem__('case_id','NOT_RECORDED'))
        self.assertEqual(self.cli().returncode,2)

    def test_local_pairing_rule_cannot_change_tool_call(self):
        self.update_mcp(lambda x:x[-2]['params'].__setitem__('name','a_different_tool'))
        self.assertEqual(self.cli().returncode,2)

    def test_symlink_contract_rejected(self):
        link=self.root/'mapping-link.json';link.symlink_to(self.mapping)
        self.assertEqual(self.cli('--semantic-map',str(link)).returncode,2)

    def test_trust_contract_from_untrusted_capture_rejected(self):
        embedded=self.data/'unsafe.json';embedded.write_bytes(self.mapping.read_bytes())
        self.assertEqual(self.cli('--semantic-map',str(embedded)).returncode,2)

    def test_unchanged_without_opt_in(self):
        x=subprocess.run([str(CLI),'analyze',str(self.data),'--recovery','--format','json'],
                         capture_output=True,text=True,timeout=18)
        self.assertEqual(x.returncode,0,x.stderr)
        out=json.loads(x.stdout)
        self.assertNotIn('semantic_mapping_v1',out)
        self.assertEqual(out['summary']['LOSS'],1)

if __name__=='__main__':
    unittest.main()
