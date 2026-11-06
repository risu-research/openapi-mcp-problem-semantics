"""P0/P1 regression: evidence/decision consistency and deterministic consumers."""
from __future__ import annotations
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from risu_probe import compare,VERSION
from risu_analyze import analyze
from risu_report import to_sarif,to_markdown
from risu_decision import decide,apply,any_blocking
from risu_witness import witness

BODY={'status':422,'errors':[{'pointer':'/name','message':'required'}],
      'id':'synthetic-id','number':1,'enabled':True}
SRC={'status':422,'content_type':'application/problem+json','body':BODY}
def make_mcp(body=BODY,*,structured=False,flag=True,meta=None):
    if structured:
        m={'structuredContent':copy.deepcopy(body),'isError':flag}
    else:
        m={'content':[{'type':'text','text':json.dumps({'status_code':422,'data':body})}],
           'isError':flag}
    if meta is not None:m['_meta']=meta
    return m
def row(mcp,source=SRC):
    return compare(source,mcp,error_profile='json-errors')
def report(mcp,source=SRC,policy='calibrated'):
    return analyze({'cases':[{'translator':'test','id':'case','source':source,'mcp':mcp}]},
                   policy=policy)

class Policy(unittest.TestCase):
    def test_v094(self):
        self.assertEqual(VERSION,'0.9.4-experimental')
    def test_json_text_legacy_loss_but_no_false_data_destruction_alert(self):
        r=report(make_mcp())
        item=r['results'][0]
        self.assertEqual(item['verdict'],'LOSS')
        self.assertEqual(item['evidence_v1']['body_recovery'],'EXACT_JSON_TEXT')
        self.assertEqual(item['decision_v1']['outcome'],'REVIEW')
        self.assertFalse(any_blocking(r))
        self.assertEqual(r['decision_summary']['REVIEW'],1)
        self.assertEqual(to_sarif(r)['runs'][0]['results'][0]['level'],'warning')
        self.assertEqual(to_sarif(r)['runs'][0]['results'][0]['ruleId'],'RISU202')
        self.assertIn('| REVIEW',to_markdown(r))
        self.assertIn('EXACT_JSON_TEXT',to_markdown(r))
        self.assertNotIn('Verified contract failure',to_markdown(r))
    def test_legacy_strict_carrier_mode_still_blocks(self):
        r=report(make_mcp(),policy='strict-carrier')
        self.assertEqual(r['results'][0]['decision_v1']['reason'],'STRICT_CARRIER_CONTRACT_VIOLATION')
        self.assertTrue(any_blocking(r))
        self.assertEqual(to_sarif(r)['runs'][0]['results'][0]['level'],'error')
    def test_complete_structured_content_passes_without_sarif_warning(self):
        r=report(make_mcp(structured=True,meta={'observed_http_status':422}))
        self.assertEqual(r['results'][0]['decision_v1']['outcome'],'PASS')
        self.assertFalse(any_blocking(r))
        self.assertEqual(len(to_sarif(r)['runs'][0]['results']),0)
    def test_flag_loss_blocks_despite_json_text_exact(self):
        r=report(make_mcp(flag=False))
        self.assertEqual(r['results'][0]['evidence_v1']['body_recovery'],'EXACT_JSON_TEXT')
        self.assertEqual(r['results'][0]['decision_v1']['outcome'],'FAIL')
        self.assertEqual(r['results'][0]['decision_v1']['reason'],'ERROR_FLAG_LOST')
        self.assertTrue(any_blocking(r))
        self.assertEqual(to_sarif(r)['runs'][0]['results'][0]['level'],'error')
    def test_status_conflict_blocks(self):
        r=report(make_mcp(meta={'observed_http_status':409}))
        self.assertEqual(r['results'][0]['decision_v1']['reason'],'EXPLICIT_HTTP_STATUS_CONFLICT')
        self.assertTrue(any_blocking(r))
    def test_partial_nonjson_is_out_of_scope(self):
        src={'status':200,'content_type':'text/plain','body':'ok'}
        r=report({'content':[{'type':'text','text':'ok'}],'isError':False},src)
        self.assertEqual(r['results'][0]['decision_v1']['outcome'],'NOT_APPLICABLE')
    def test_machine_only_metadata_needs_review(self):
        m={'_meta':{'data':BODY,'observed_http_status':422},'isError':True}
        r=report(m)
        self.assertEqual(r['results'][0]['decision_v1']['outcome'],'REVIEW')
        self.assertEqual(r['results'][0]['decision_v1']['reason'],'METADATA_ONLY_CARRIER')
    def test_unsupported_retry_claim_is_failure(self):
        m=make_mcp(structured=True)
        m['_meta']={'retryable':True,'observed_http_status':422}
        r=report(m)
        self.assertEqual(r['results'][0]['decision_v1']['reason'],'UNSUPPORTED_RETRY_CLAIM')
    def test_deferred_and_inspection_failed_distinct(self):
        deferred=decide({'verdict':'INPUT_REQUIRED','evidence_v1':{'body_recovery':'DEFERRED'}})
        failed=decide({'verdict':'ERROR','losses':['unavailable']})
        self.assertEqual(deferred['outcome'],'DEFERRED')
        self.assertEqual(failed['outcome'],'FAIL')
    def test_review_blocks_only_if_explicit(self):
        r=report(make_mcp())
        self.assertFalse(any_blocking(r))
        self.assertTrue(any_blocking(r,fail_review=True))
    def test_baseline_only_suppresses_acknowledged_not_operational(self):
        r=report(make_mcp(flag=False))
        r['results'][0]['baseline']='known'
        self.assertFalse(any_blocking(r,new_only=True))
        p={'results':[{'verdict':'ERROR','baseline':'known','decision_v1':decide({'verdict':'ERROR'})}]}
        self.assertTrue(any_blocking(p,new_only=True))
    def test_sarif_no_legacy_duplicate_error_on_review(self):
        r=report(make_mcp())
        findings=to_sarif(r)['runs'][0]['results']
        self.assertEqual(len(findings),1)
        self.assertEqual(findings[0]['properties']['legacyVerdict'],'LOSS')
        self.assertEqual(findings[0]['properties']['bodyRecovery'],'EXACT_JSON_TEXT')
    def test_contradiction_prevention_output_equals_decision(self):
        for m in (make_mcp(),make_mcp(structured=True),make_mcp(flag=False)):
            r=report(m)
            state=r['results'][0]['decision_v1']['outcome']
            sara=to_sarif(r)['runs'][0]['results']
            self.assertEqual(bool(sara),state in ('REVIEW','FAIL','DEFERRED'))
            if sara:self.assertEqual(sara[0]['properties']['decision'],state)
            self.assertIn(state,to_markdown(r))

class Consumer(unittest.TestCase):
    def test_exact_text_diverges_two_consumers(self):
        proof=witness(SRC,make_mcp(),['/errors/0/pointer'])
        self.assertEqual(proof['models']['structured-only']['outcome'],'FAIL')
        self.assertEqual(proof['models']['json-text-data']['outcome'],'PASS')
        self.assertTrue(proof['divergent_outcomes'])
    def test_structured_passes_text_fails(self):
        proof=witness(SRC,make_mcp(structured=True),['/errors/0/pointer'])
        self.assertEqual(proof['models']['structured-only']['outcome'],'PASS')
        self.assertEqual(proof['models']['json-text-data']['outcome'],'FAIL')
        self.assertTrue(proof['divergent_outcomes'])
    def test_wrong_value_fails_both(self):
        wrong=copy.deepcopy(BODY);wrong['errors'][0]['pointer']='/somewhere-else'
        proof=witness(SRC,make_mcp(wrong),['/errors/0/pointer'])
        self.assertFalse(proof['divergent_outcomes'])
        self.assertTrue(all(x['outcome']=='FAIL' for x in proof['models'].values()))
    def test_partial_body_can_satisfy_explicit_field_contract(self):
        partial={'errors':[{'pointer':'/name'}]}
        proof=witness(SRC,make_mcp(partial),['/errors/0/pointer'])
        self.assertEqual(proof['models']['json-text-data']['outcome'],'PASS')
        self.assertEqual(proof['models']['structured-only']['outcome'],'FAIL')
    def test_bool_vs_number_is_never_equal(self):
        src={'status':200,'content_type':'application/json','body':{'x':1}}
        m={'structuredContent':{'x':True},'isError':False}
        p=witness(src,m,['/x'],require_error_flag=False)
        self.assertEqual(p['models']['structured-only']['outcome'],'FAIL')
    def test_error_flag_can_reject_completely_exact_payload(self):
        p=witness(SRC,make_mcp(flag=False),['/errors/0/pointer'])
        self.assertEqual(p['models']['json-text-data']['outcome'],'FAIL')
        self.assertEqual(p['models']['json-text-data']['reason'],'ERROR_FLAG_MISMATCH')
    def test_optional_status_contract_for_json_envelope(self):
        p=witness(SRC,make_mcp(),['/status'],require_http_status=True)
        self.assertEqual(p['models']['json-text-data']['outcome'],'PASS')
        self.assertEqual(p['models']['structured-only']['outcome'],'FAIL')
    def test_strict_status_conflict_rejected(self):
        m=make_mcp()
        m['content'][0]['text']=json.dumps({'data':BODY,'status_code':409})
        p=witness(SRC,m,['/status'],require_http_status=True)
        self.assertEqual(p['models']['json-text-data']['outcome'],'FAIL')
    def test_duplicate_key_uncertified(self):
        m={'content':[{'type':'text','text':'{"data":'+json.dumps(BODY)+',"data":'+json.dumps(BODY)+'}'}],'isError':True}
        p=witness(SRC,m,['/status'])
        self.assertEqual(p['models']['json-text-data']['outcome'],'FAIL')
    def test_fenced_json_is_parsed_if_complete(self):
        m=make_mcp()
        m['content'][0]['text']='```json\n'+m['content'][0]['text']+'\n```'
        p=witness(SRC,m,['/status'])
        self.assertEqual(p['models']['json-text-data']['outcome'],'PASS')
    def test_free_prose_is_never_parsed_as_hidden_json(self):
        m=make_mcp()
        m['content'][0]['text']='For your information: '+m['content'][0]['text']
        p=witness(SRC,m,['/status'])
        self.assertEqual(p['models']['json-text-data']['outcome'],'FAIL')
    def test_metadata_only_may_be_exact_but_both_readers_fail(self):
        p=witness(SRC,{'_meta':{'data':BODY},'isError':True},['/status'])
        self.assertTrue(all(x['outcome']=='FAIL' for x in p['models'].values()))
    def test_invalid_contract_is_fail_closed(self):
        with self.assertRaises(ValueError):witness(SRC,make_mcp(),['/unknown'])
        with self.assertRaises(ValueError):witness(SRC,make_mcp(),['/status','/status'])
    def test_sensitive_values_absent_in_report(self):
        secret='PRIVATE_SENTINEL_NEVER_EXPORT_2949'
        src={'status':200,'content_type':'application/json','body':{'token':secret}}
        m={'content':[{'type':'text','text':json.dumps({'data':{'token':secret}})}],'isError':False}
        output=json.dumps(witness(src,m,['/token']))
        self.assertNotIn(secret,output)
        self.assertEqual(json.loads(output)['models']['json-text-data']['outcome'],'PASS')
    def test_cli_witness_and_analyze_exit_policy(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            matrix=root/'matrix.json'
            matrix.write_text(json.dumps({'cases':[{'id':'triad','translator':'project','source':SRC,'mcp':make_mcp()}]}))
            script=Path(sys.modules['risu_probe'].__file__)
            def command(*args):
                return subprocess.run([sys.executable,str(script),*args],
                                      capture_output=True,text=True,timeout=10)
            p=command('analyze',str(matrix),'--format','sarif','--fail-on-loss')
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertIn('RISU202',p.stdout)
            p=command('analyze',str(matrix),'--policy','strict-carrier','--format','sarif','--fail-on-loss')
            self.assertEqual(p.returncode,1,p.stderr)
            self.assertIn('RISU201',p.stdout)
            p=command('witness',str(matrix),'--path','/status',
                      '--fail-on-consumer','json-text-data')
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertIn('divergent_outcomes',p.stdout)
            p=command('witness',str(matrix),'--path','/status',
                      '--fail-on-consumer','structured-only')
            self.assertEqual(p.returncode,1,p.stderr)
    def test_two_models_are_not_actual_llm_evaluation(self):
        p=witness(SRC,make_mcp(),['/status'])
        self.assertIn('no LLM behavior inferred',p['claim_boundary'])

if __name__=='__main__':
    unittest.main(verbosity=2)
