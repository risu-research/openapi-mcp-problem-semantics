import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'p4t'))
from risu_contract_history import create_snapshot, load_snapshot, diff_snapshots, timeline, _write

class P4UContractSafety(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name)
        self.a=self.folder/'old.json';self.b=self.folder/'new.json'
        self.a.write_text(json.dumps({'jsonrpc':'2.0','id':2,'result':{'tools':[{'name':'convert_time','outputSchema':{'type':'object','properties':{'source':{'type':'object'},'target':{'type':'object'}},'required':['source','target']}}]}}))
        self.b.write_text(json.dumps({'jsonrpc':'2.0','id':2,'result':{'tools':[{'name':'convert_time','outputSchema':{'type':'object','properties':{'source':{'type':'object'},'target':{'type':'object'},'later_occurrence':{'anyOf':[{'type':'object'},{'type':'null'}]}},'required':['source','target']}}]}}))
        self.o=create_snapshot(str(self.a),None,'2026.10.19','convert_time');_write(str(self.folder/'snap1.json'),self.o)
        self.n=create_snapshot(str(self.b),None,'2026.11.4','convert_time',str(self.folder/'snap1.json'))
        _write(str(self.folder/'snap2.json'),self.n)
    def test_actual_wire_shape(self):
        self.assertEqual(self.n['source_kind'],'recorded-tools-list')
    def test_modified_snapshot_rejected(self):
        d=json.loads((self.folder/'snap2.json').read_text());d['schema']['properties']['later_occurrence']['type']='string'
        (self.folder/'snap2.json').write_text(json.dumps(d))
        with self.assertRaises(ValueError):load_snapshot(self.folder/'snap2.json')
    def test_no_policy_is_not_evidence(self):
        self.assertIsNone(self.o['operator_policy'])
        self.assertIsNone(self.n['operator_policy'])
    def test_optional_is_not_new_required(self):
        d=diff_snapshots(self.o,self.n)
        self.assertEqual([x['kind'] for x in d['publisher_schema_events']],['NEW_OPTIONAL_FIELD'])
        self.assertEqual(d['potential_breaking_changes'],[])
        self.assertEqual(d['operator_policy_events'],[])
    def test_provenance_no_contract_claim(self):
        self.assertIn('neither live deployment',self.n['trust_notice'])
    def test_reversed_chronology_rejected(self):
        with self.assertRaises(ValueError):timeline([str(self.folder/'snap2.json'),str(self.folder/'snap1.json')])
    def test_timeline_hash_link(self):
        self.assertEqual(timeline([str(self.folder/'snap1.json'),str(self.folder/'snap2.json')])['verified_hash_links'],1)
    def test_wrong_tool_rejected(self):
        with self.assertRaises(ValueError):create_snapshot(str(self.a),None,'v','no_such_tool')
if __name__=='__main__':unittest.main()
