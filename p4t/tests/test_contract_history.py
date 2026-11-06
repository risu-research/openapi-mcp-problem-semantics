import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from risu_contract_history import (canonical,cli,create_snapshot,diff_snapshots,digest,
    load_snapshot,read_json_or_jsonl,resolve_schema,timeline,_flatten,_policy_rules)
FIX=ROOT/'fixtures'

class TestContractHistory(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cwd=Path(self.tmp.name)
        self.a=create_snapshot(str(FIX/'baseline_schema.json'),str(FIX/'operator_old.json'),'1.0',"get_jpo_progress")
        self.ap=self.cwd/'v1.json';self.ap.write_text(json.dumps(self.a))
        self.b=create_snapshot(str(FIX/'upgrade_schema.json'),str(FIX/'operator_new.json'),'2.0',"get_jpo_progress",str(self.ap))
        self.bp=self.cwd/'v2.json';self.bp.write_text(json.dumps(self.b))
    def test_01_digest_repeatable(self): self.assertEqual(digest({'a':1,'b':2}),digest({'b':2,'a':1}))
    def test_02_hash_length(self): self.assertEqual(len(self.a['snapshot_sha256']),64)
    def test_03_link(self): self.assertEqual(self.b['previous_snapshot_sha256'],self.a['snapshot_sha256'])
    def test_04_loaded(self):self.assertEqual(load_snapshot(self.ap),self.a)
    def test_05_tamper_rejected(self):
        obj=copy.deepcopy(self.a);obj['version']='1.1';self.ap.write_text(json.dumps(obj))
        with self.assertRaises(ValueError):load_snapshot(self.ap)
    def test_06_wrong_format(self):
        obj=copy.deepcopy(self.a);obj['format']='other';self.ap.write_text(json.dumps(obj))
        with self.assertRaises(ValueError):load_snapshot(self.ap)
    def test_07_nonempty_versions(self):
        with self.assertRaises(ValueError):create_snapshot(str(FIX/'baseline_schema.json'),None,'  ',None)
    def test_08_source_kind_schema_file(self):self.assertEqual(self.a['source_kind'],'schema-file')
    def test_09_input_sha(self):self.assertEqual(len(self.a['input_sha256']['schema']),64)
    def test_10_direct_four(self):self.assertEqual(diff_snapshots(self.a,self.b)['summary']['direct_schema_events'],4)
    def test_11_inherited_four(self):self.assertEqual(diff_snapshots(self.a,self.b)['summary']['inherited_effects'],4)
    def test_12_policy_six(self):self.assertEqual(diff_snapshots(self.a,self.b)['summary']['operator_policy_events'],6)
    def test_13_added_required(self):self.assertIn(('NEW_REQUIRED_FIELD','/quota_remaining'),self.eventset())
    def test_14_optional_required(self):self.assertIn(('OPTIONAL_TO_REQUIRED','/not_found'),self.eventset())
    def test_15_required_optional(self):self.assertIn(('REQUIRED_TO_OPTIONAL','/provenance'),self.eventset())
    def test_16_type_change(self):self.assertIn(('TYPE_CHANGED','/items'),self.eventset())
    def test_17_ripple_not_direct(self):
        d=diff_snapshots(self.a,self.b)
        self.assertFalse(any('/provenance/' in x['path'] for x in d['publisher_schema_events']))
        self.assertEqual(len([x for x in d['inherited_effects_not_independent_changes'] if '/provenance/' in x['path']]),4)
    def test_18_breaking_count(self):self.assertEqual(diff_snapshots(self.a,self.b)['summary']['potential_breaking'],3)
    def test_19_no_loss_claim(self):self.assertIn('No observed upgrade',diff_snapshots(self.a,self.b)['limitation'])
    def test_20_policy_add(self):self.assertIn('OPERATOR_RULE_ADDED',self.policykinds())
    def test_21_policy_removed(self):self.assertIn('OPERATOR_RULE_REMOVED',self.policykinds())
    def test_22_policy_attribute(self):self.assertIn('OPERATOR_RULE_ATTRIBUTE_CHANGED',self.policykinds())
    def test_23_not_supplier_contract(self):self.assertIn('neither live deployment',self.a['trust_notice'])
    def test_24_cross_tool_rejected(self):
        b=copy.deepcopy(self.b);b['tool']='other'
        with self.assertRaises(ValueError):diff_snapshots(self.a,b)
    def test_25_timeline_valid(self):self.assertEqual(timeline([str(self.ap),str(self.bp)])['verified_hash_links'],1)
    def test_26_timeline_reversal(self):
        with self.assertRaises(ValueError):timeline([str(self.bp),str(self.ap)])
    def test_27_timeline_short(self):
        with self.assertRaises(ValueError):timeline([str(self.ap)])
    def test_28_timeline_unlinked(self):
        b=copy.deepcopy(self.b);b['previous_snapshot_sha256']='0'*64
        b['snapshot_sha256']=digest({k:v for k,v in b.items() if k!='snapshot_sha256'})
        self.bp.write_text(json.dumps(b))
        with self.assertRaises(ValueError):timeline([str(self.ap),str(self.bp)])
    def test_29_required_undeclared_reject(self):
        with self.assertRaises(ValueError):_flatten({'properties':{},'required':['ghost']})
    def test_30_required_duplicate_reject(self):
        with self.assertRaises(ValueError):_flatten({'properties':{'x':{}},'required':['x','x']})
    def test_31_duplicate_operator_reject(self):
        with self.assertRaises(ValueError):_policy_rules({'rules':[{'id':'a'},{'id':'a'}]})
    def test_32_bad_operator_missing_key(self):
        with self.assertRaises(ValueError):_policy_rules({'rules':[{'condition':'always'}]})
    def test_33_jsonl_tools_list(self):
        p=self.cwd/'wire.jsonl';p.write_text(json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/list'})+'\n'+json.dumps({'jsonrpc':'2.0','id':1,'result':{'tools':[{'name':'test','outputSchema':json.loads((FIX/'baseline_schema.json').read_text())}]}})+'\n')
        schema,source=resolve_schema(read_json_or_jsonl(p),'test');self.assertEqual(source,'recorded-tools-list');self.assertEqual(schema['required'],['summary','items','provenance'])
    def test_34_wrong_tool_reject(self):
        with self.assertRaises(ValueError):resolve_schema([{'result':{'tools':[{'name':'x','outputSchema':json.loads((FIX/'baseline_schema.json').read_text())}]}}],'y')
    def test_35_ambiguous_tool_reject(self):
        m={'result':{'tools':[{'name':'x','outputSchema':json.loads((FIX/'baseline_schema.json').read_text())},{'name':'y','outputSchema':json.loads((FIX/'baseline_schema.json').read_text())}]}}
        with self.assertRaises(ValueError):resolve_schema([m],None)
    def test_36_direct_json_schema(self):self.assertEqual(resolve_schema([json.loads((FIX/'baseline_schema.json').read_text())],None)[1],'schema-file')
    def test_37_duplicate_path_policy(self):
        a=copy.deepcopy(self.a);a['operator_policy']={'rules':[{'id':'dup','condition':'always'},{'id':'dup','condition':'never'}]}
        with self.assertRaises(ValueError):diff_snapshots(a,self.b)
    def test_38_no_previous_link_first(self):self.assertIsNone(self.a['previous_snapshot_sha256'])
    def test_39_snapshot_wrong_schema_file(self):
        p=self.cwd/'bad.json';p.write_text('{}')
        with self.assertRaises(ValueError):create_snapshot(str(p),None,'v0',None)
    def test_40_cli_diff_breaking_exit(self):self.assertEqual(cli(['diff',str(self.ap),str(self.bp),'--fail-on-potential-breaking']),1)
    def test_41_cli_diff_normal_exit(self):self.assertEqual(cli(['diff',str(self.ap),str(self.bp)]),0)
    def test_42_cli_timeline_exit(self):self.assertEqual(cli(['timeline',str(self.ap),str(self.bp)]),0)
    def test_43_cli_existing_output_rejected(self):
        o=self.cwd/'exists';o.write_text('marker')
        self.assertEqual(cli(['snapshot','--schema',str(FIX/'baseline_schema.json'),'--version','3','--out',str(o)]),2)
    def test_44_non_json_path_rejected(self):
        p=self.cwd/'malformed';p.write_text('NOT_JSON')
        with self.assertRaises(ValueError):read_json_or_jsonl(p)
    def test_45_policy_not_required_on_snapshot(self):self.assertIsNone(create_snapshot(str(FIX/'baseline_schema.json'),None,'solo',None)['operator_policy'])
    def test_46_deterministic_diff(self):self.assertEqual(digest(diff_snapshots(self.a,self.b)),digest(diff_snapshots(self.a,self.b)))
    def test_47_reverse_diff_not_same(self):self.assertNotEqual(diff_snapshots(self.a,self.b)['publisher_schema_events'],diff_snapshots(self.b,self.a)['publisher_schema_events'])
    def test_48_cli_snapshot_success(self):
        p=self.cwd/'new.json'
        self.assertEqual(cli(['snapshot','--schema',str(FIX/'baseline_schema.json'),'--version','3','--tool','get_jpo_progress','--out',str(p)]),0)
        self.assertTrue(p.exists())
    def test_49_input_canonical_utf8(self):self.assertIn('한글',canonical({'k':'한글'}).decode('utf-8'))
    def test_50_serialized_result(self):json.dumps(diff_snapshots(self.a,self.b))
    def eventset(self):return {(e['kind'],e['path']) for e in diff_snapshots(self.a,self.b)['publisher_schema_events']}
    def policykinds(self):return {e['kind'] for e in diff_snapshots(self.a,self.b)['operator_policy_events']}

if __name__=='__main__': unittest.main()
