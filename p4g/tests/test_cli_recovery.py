"""CLI-level original v0.9.8 recovery integration acceptance and adversarial controls."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'src'
DATA=json.loads((ROOT/'evidence/saved_p4de.json').read_text())

def run_cli(data=None,extra=(),format='json'):
    with tempfile.TemporaryDirectory() as d:
        matrix=Path(d)/'cases.json'
        matrix.write_text(json.dumps(DATA if data is None else data,ensure_ascii=False))
        out=Path(d)/'out.json'
        env=os.environ.copy();env['PYTHONPATH']=str(SRC)
        cmd=[sys.executable,'-m','risu_probe','analyze',str(matrix),'--format',format,'--out',str(out),*extra]
        p=subprocess.run(cmd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=12)
        return p,(out.read_text() if out.exists() else '')

class OneCommandIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p,out=run_cli(extra=('--recovery',))
        assert p.returncode==0,(p.stderr,p.stdout)
        cls.report=json.loads(out)
        cls.byc={x['id']:x for x in cls.report['recovery_v1']['cases']}
    def test_all_five_and_expected_baseline(self):
        r=self.report
        self.assertEqual(r['version'],'0.9.8-experimental')
        self.assertEqual(r['summary']['LOSS'],3)
        self.assertEqual(r['summary']['PRESERVED'],2)
        self.assertEqual(r['diagnostic_summary']['ERROR_FLAG_LOST'],1)
        self.assertEqual(r['diagnostic_summary']['UNSTRUCTURED_UPSTREAM_ERROR'],3)
        self.assertEqual(r['recovery_v1']['case_count'],5)
    def test_p4d_error_not_confused_with_consumer(self):
        d=self.byc['D404']
        self.assertEqual(d['error_flag'],'ERROR_FLAG_LOST')
        self.assertEqual(d['consumer_error_classification'],'success')
        fields={v['path']:v['category'] for v in d['consumer']['fields']}
        self.assertEqual(fields['/message'],'TEXT_VALUE_MENTION_ONLY')
        self.assertEqual(fields['/code'],'ABSENT_IN_OBSERVED_CARRIERS')
    def test_p4e_456_exact_recoverable_429_missing(self):
        a=self.byc['E456'];b=self.byc['E429']
        self.assertEqual(a['mcp']['full_body'],'EXACT_JSON_TEXT')
        self.assertEqual(a['consumer']['full_body'],'EXACT_JSON_TEXT')
        self.assertEqual(a['consumer']['fields'][0]['category'],'PARSED_JSON_TEXT_FIELD')
        self.assertEqual(b['mcp']['full_body'],'NO_EXACT_OBJECT_CARRIER')
        self.assertEqual(b['consumer']['fields'][0]['category'],'ABSENT_IN_OBSERVED_CARRIERS')
    def test_positive_controls(self):
        self.assertTrue(all(self.byc[x]['mcp']['full_body']=='EXACT_MACHINE' and
                            self.byc[x]['consumer']['full_body']=='EXACT_MACHINE' for x in ('D200','S200')))
    def test_not_exporting_raw_secret_values(self):
        data=json.dumps(self.report['recovery_v1'])
        for secret in ('index_not_found','RISU_SYNTH_QUOTA_EXCEEDED','RISU_SYNTH_RATE_LIMITED','Index `does-not-exist` not found'):
            self.assertNotIn(secret,data)
    def test_old_cli_unchanged_without_flag(self):
        p,out=run_cli();self.assertEqual(p.returncode,0,p.stderr)
        raw=json.loads(out)
        self.assertNotIn('recovery_v1',raw)
        self.assertEqual(raw['summary'],self.report['summary'])
        self.assertEqual(raw['diagnostic_summary'],self.report['diagnostic_summary'])
        self.assertEqual(raw['decision_summary'],self.report['decision_summary'])
        self.assertEqual(raw['results'],self.report['results'])
    def test_text_one_command(self):
        p,out=run_cli(format='text',extra=('--recovery',))
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn('Recovery Lens |',out)
        self.assertIn('ERROR_FLAG_LOST',out)
        self.assertIn('PARSED_JSON_TEXT_FIELD',out)
        self.assertIn('ABSENT_IN_OBSERVED_CARRIERS',out)
    def test_markdown_one_command(self):
        p,out=run_cli(format='markdown',extra=('--recovery',))
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn('## Recovery Lens',out)
    def test_sarif_rejects_unrepresented_recovery(self):
        p,out=run_cli(format='sarif',extra=('--recovery',))
        self.assertEqual(p.returncode,2)
        self.assertIn('not supported with SARIF',p.stderr)
        self.assertFalse(out)
    def test_duplicate_ids_but_different_targets(self):
        x=copy.deepcopy(DATA)
        x['cases'][0]['id']='same';x['cases'][2]['id']='same'
        p,out=run_cli(x,extra=('--recovery',))
        self.assertEqual(p.returncode,0,p.stderr)
        r=json.loads(out)
        self.assertEqual([y['id'] for y in r['recovery_v1']['cases']].count('same'),2)
    def test_absent_consumer_marks_untested(self):
        x=copy.deepcopy(DATA)
        x['cases'][3].pop('observed_consumer')
        p,out=run_cli(x,extra=('--recovery',))
        self.assertEqual(p.returncode,0,p.stderr)
        r=json.loads(out)['recovery_v1']['cases'][3]
        self.assertIsNone(r['consumer'])
    def test_text_mentions_do_not_certify_typed(self):
        x=copy.deepcopy(DATA);x['cases'][3]['mcp']['content'][0]['text']='A note RISU_SYNTH_QUOTA_EXCEEDED'
        p,out=run_cli(x,extra=('--recovery',))
        self.assertEqual(p.returncode,0,p.stderr)
        entry=json.loads(out)['recovery_v1']['cases'][3]
        code=next(f for f in entry['mcp']['fields'] if f['path']=='/code')
        self.assertEqual(code['category'],'TEXT_VALUE_MENTION_ONLY')
    def test_prefix_status_forgery_does_not_certify(self):
        x=copy.deepcopy(DATA);r=x['cases'][3]
        r['mcp']['content'][0]['text']=r['mcp']['content'][0]['text'].replace('HTTP error 456','HTTP error 457')
        p,out=run_cli(x,extra=('--recovery',))
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertNotEqual(json.loads(out)['recovery_v1']['cases'][3]['mcp']['full_body'],'EXACT_JSON_TEXT')
    def test_nested_bool_int_not_same(self):
        import risu_recovery
        self.assertFalse(risu_recovery.equal({'nested':{'flag':True}},{'nested':{'flag':1}}))
        self.assertFalse(risu_recovery.equal({'items':[1]},{'items':[True]}))
    def test_sensitive_field_name_hashed(self):
        import risu_recovery
        fields=risu_recovery.fields_at_stage({'private@example.com':'value'},[],[],404)['fields']
        self.assertNotIn('private@example.com',json.dumps(fields))
        self.assertTrue(fields[0]['path'].startswith('/[key:'))
    def test_large_consumer_blocked(self):
        x=copy.deepcopy(DATA)
        x['cases'][3]['observed_consumer']['consumer']['mapped']='x'*60100
        p,out=run_cli(x,extra=('--recovery',))
        self.assertEqual(p.returncode,2)
        self.assertIn('oversized',p.stderr)
    def test_oversized_matrix_refused(self):
        import risu_recovery
        huge={'cases':DATA['cases']*11}
        with self.assertRaisesRegex(ValueError,'too many cases'):
            risu_recovery.analyze_saved(huge,{'results':[]})
    def test_recovery_never_executes_external_code(self):
        x=copy.deepcopy(DATA)
        x['cases'][3]['observed_consumer']['consumer']['mapped']='__import__("os").system("touch /tmp/should_never_run")'
        p,_=run_cli(x,extra=('--recovery',))
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertFalse(Path('/tmp/should_never_run').exists())
    def test_duplicate_json_key_rejected_before_analysis(self):
        with tempfile.TemporaryDirectory() as d:
            matrix=Path(d)/'bad.json'
            matrix.write_text('{"cases":[], "cases":[]}')
            env=os.environ.copy();env['PYTHONPATH']=str(SRC)
            p=subprocess.run([sys.executable,'-m','risu_probe','analyze',str(matrix),'--recovery'],
                env=env,text=True,capture_output=True,timeout=10)
            self.assertEqual(p.returncode,2)
            self.assertIn('duplicate JSON key',p.stderr)
    def test_nonfinite_json_constant_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            matrix=Path(d)/'bad.json'
            matrix.write_text('{"cases":[NaN]}')
            env=os.environ.copy();env['PYTHONPATH']=str(SRC)
            p=subprocess.run([sys.executable,'-m','risu_probe','analyze',str(matrix),'--recovery'],
                env=env,text=True,capture_output=True,timeout=10)
            self.assertEqual(p.returncode,2)
            self.assertIn('nonfinite JSON constant',p.stderr)
    def test_status_456_survives_text_but_not_machine(self):
        x=self.byc['E456']
        self.assertTrue(all(f['category']=='PARSED_JSON_TEXT_FIELD' for f in x['mcp']['fields']))
        self.assertEqual(x['error_flag'],'MATCH')
    def test_loss_exit_is_preserved(self):
        p,_=run_cli(extra=('--recovery','--fail-on-loss'))
        self.assertEqual(p.returncode,1,p.stderr)
    def test_targets_native_matrix_and_missing_consumer(self):
        x={'targets':[{'target':'DeepL-FastMCP', 'cases':[{'case':'one',
            'upstream':copy.deepcopy(DATA['cases'][3]['source']),
            'mcp_wire':copy.deepcopy(DATA['cases'][3]['mcp'])}]}]}
        p,out=run_cli(x,extra=('--recovery',))
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(json.loads(out)['recovery_v1']['cases'][0]['id'],'one')
        self.assertIsNone(json.loads(out)['recovery_v1']['cases'][0]['consumer'])

if __name__=='__main__':unittest.main(verbosity=2)