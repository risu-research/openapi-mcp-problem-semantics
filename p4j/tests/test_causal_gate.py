"""P4-J independent trust boundary, forged joins, and protocol mutation suite."""
from __future__ import annotations
import base64,copy,hashlib,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

HERE=Path(__file__).resolve().parents[1]
SRC=HERE/'src'
sys.path.insert(0,str(SRC))
from risu_causality import canonical,digest,sha_bytes,SCHEMA,TRUST,CALL_KIND

HAR={'log':{'version':'1.2','entries':[
 {'request':{'method':'GET','url':'http://127.0.0.1:6543/records/valid','headers':[]},
  'response':{'status':200,'headers':[{'name':'Content-Type','value':'application/json'}],
              'content':{'mimeType':'application/json','text':'{"id":"valid","count":7}'}}},
 {'request':{'method':'GET','url':'http://127.0.0.1:6543/records/missing','headers':[]},
  'response':{'status':404,'headers':[{'name':'Content-Type','value':'application/json'}],
              'content':{'mimeType':'application/json','text':'{"code":"record_missing","message":"No such record"}'}}}]}}
RPC=[
 {'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'fetch_record','arguments':{'record_id':'valid'}}},
 {'jsonrpc':'2.0','id':1,'result':{'isError':False,'structuredContent':{'id':'valid','count':7},'content':[{'type':'text','text':'{"id":"valid","count":7}'}]}},
 {'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'fetch_record','arguments':{'record_id':'missing'}}},
 {'jsonrpc':'2.0','id':2,'result':{'isError':False,'content':[{'type':'text','text':'{"code":"record_missing","message":"No such record"}'}]}}]
PAIRS={'schema':'risu-explicit-capture-pairing-v1','pairs':[
 {'case_id':'NORMAL_200','target':'test-dev','http_entry':0,'mcp_call_id':1,'tool':'fetch_record'},
 {'case_id':'FALSE_FLAG_404','target':'test-dev','http_entry':1,'mcp_call_id':2,'tool':'fetch_record'}]}

def files(root,har=None,rpc=None,pairs=None):
    (root/'capture.har').write_text(json.dumps(HAR if har is None else har))
    (root/'mcp.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in (RPC if rpc is None else rpc)))
    (root/'pairs.json').write_text(json.dumps(PAIRS if pairs is None else pairs))

def cli(root,*opts):
    env=os.environ.copy();env['PYTHONPATH']=str(SRC)
    return subprocess.run([sys.executable,'-B','-m','risu_probe','analyze',str(root),
       '--recovery','--format','json',*opts],text=True,capture_output=True,env=env,timeout=10)

def make_witness(root,trust_out,link_indices=(0,1),mutate=None,other_key=False):
    """Synthetic witness for verifier unit testing, NOT evidence of a live call."""
    har=json.loads((root/'capture.har').read_text())
    rpc=[json.loads(x) for x in (root/'mcp.jsonl').read_text().splitlines()]
    pairs=json.loads((root/'pairs.json').read_text())
    for i in range(2):
        token='unit-test-observer-token-'+str(i)+'-0123456'
        rpc[2*i]['params']['arguments']['risu_trace_token']=token
        har['log']['entries'][i]['request']['headers'].append({'name':'X-RISU-Trace-Token','value':token})
    files(root,har,rpc,pairs)
    statement={'schema':SCHEMA,'observer_kind':'BOUNDARY_RECORDER_V1',
      'issuer':'p4j-unit-test-recorder','session_id':'unit-test-session-0',
      'file_sha256':{p:sha_bytes((root/p).read_bytes()) for p in ('capture.har','mcp.jsonl','pairs.json')},
      'links':[]}
    for i in link_indices:
        token=rpc[2*i]['params']['arguments']['risu_trace_token']
        seq=4*i
        vals=[rpc[2*i],har['log']['entries'][i]['request'],har['log']['entries'][i]['response'],rpc[2*i+1]]
        statement['links'].append({'case_id':pairs['pairs'][i]['case_id'],
          'http_entry':i,'mcp_call_id':i+1,'tool':'fetch_record','trace_token_sha256':sha_bytes(token.encode()),
          'events':[{'kind':k,'sequence':seq+j,'sha256':digest(v)} for j,(k,v) in enumerate(zip(CALL_KIND,vals))]})
    if mutate:mutate(statement)
    key=Ed25519PrivateKey.generate()
    trusted=key.public_key().public_bytes(encoding=serialization.Encoding.Raw,format=serialization.PublicFormat.Raw)
    sig=key.sign(canonical(statement))
    statement['signature']={'algorithm':'Ed25519','key_id':'unit-test-recorder','value_base64':base64.b64encode(sig).decode()}
    (root/'causal_witness.json').write_text(json.dumps(statement))
    if other_key:
        trusted=Ed25519PrivateKey.generate().public_key().public_bytes(encoding=serialization.Encoding.Raw,format=serialization.PublicFormat.Raw)
    trust={'schema':TRUST,'trusted_recorders':[{'key_id':'unit-test-recorder','issuer':'p4j-unit-test-recorder',
      'observer_kind':'BOUNDARY_RECORDER_V1','ed25519_public_key_base64':base64.b64encode(trusted).decode()}]}
    trust_out.write_text(json.dumps(trust))
    return statement

class CausalGate(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.parent=Path(self.tmp.name)
        self.root=self.parent/'capture';self.root.mkdir()
        self.trust=self.parent/'trusted_recorders.json'
        files(self.root)
    def call(self,*opts):
        return cli(self.root,*opts)
    def assert_reject(self,piece):
        x=self.call('--causal-trust-store',str(self.trust))
        self.assertEqual(x.returncode,2,x.stdout)
        self.assertIn(piece,x.stderr)
    def gate(self,*opts):
        x=self.call(*opts)
        self.assertEqual(x.returncode,0,x.stderr)
        return json.loads(x.stdout)
    def test_unsigned_false_loss_is_conditional(self):
        x=self.gate()
        self.assertEqual(x['summary']['LOSS'],1)
        self.assertEqual(x['causal_gate_v1']['summary']['CONFIRMED_LOSS'],0)
        self.assertEqual(x['causal_gate_v1']['summary']['CONDITIONAL_MISMATCH'],1)
        self.assertTrue(x['legacy_verdicts_are_not_causal_proof'])
    def test_normal_no_loss_is_conditional_without_proof(self):
        self.assertEqual(self.gate()['results'][0]['causal_v1']['outcome'],'CONDITIONAL_MATCH')
    def test_no_proof_no_confirmed_fail(self):
        self.assertEqual(self.call('--fail-on-confirmed-loss').returncode,0)
    def test_historical_fail_on_loss_retained(self):
        self.assertEqual(self.call('--fail-on-loss').returncode,1)
    def test_actual_valid_crypto_receipt_promotes_only_proven_case(self):
        make_witness(self.root,self.trust)
        d=self.gate('--causal-trust-store',str(self.trust))
        self.assertEqual(d['causal_gate_v1']['summary']['CONFIRMED_LOSS'],1)
        self.assertEqual(d['causal_gate_v1']['summary']['WITNESSED_NO_LOSS_IN_OBSERVED_FIELDS'],1)
        self.assertEqual(d['recovery_v1']['summary']['error_flag_lost'],1)
        self.assertNotIn('unit-test-observer-token',json.dumps(d))
    def test_confirmed_fail_exit(self):
        make_witness(self.root,self.trust)
        self.assertEqual(self.call('--causal-trust-store',str(self.trust),'--fail-on-confirmed-loss').returncode,1)
    def test_only_witnessed_normal_case_leaves_loss_conditional(self):
        make_witness(self.root,self.trust,link_indices=(0,))
        x=self.gate('--causal-trust-store',str(self.trust))
        self.assertEqual(x['causal_gate_v1']['summary']['CONFIRMED_LOSS'],0)
        self.assertEqual(x['causal_gate_v1']['summary']['CONDITIONAL_MISMATCH'],1)
    def test_unsigned_witness_without_external_trust_is_still_conditional(self):
        make_witness(self.root,self.trust)
        d=self.gate()
        self.assertEqual(d['causal_gate_v1']['summary']['CONFIRMED_LOSS'],0)
        self.assertEqual(d['causal_gate_v1']['witness_reason'],'NO_EXTERNAL_TRUST_ROOT')
    def test_witness_bad_signature_refused(self):
        make_witness(self.root,self.trust)
        path=self.root/'causal_witness.json';w=json.loads(path.read_text());w['session_id']='impostor';path.write_text(json.dumps(w))
        self.assert_reject('signature verification FAILED')
    def test_altered_raw_http_refused(self):
        make_witness(self.root,self.trust)
        p=self.root/'capture.har';h=json.loads(p.read_text());h['log']['entries'][1]['response']['content']['text']='{}';p.write_text(json.dumps(h))
        self.assert_reject('capture bytes changed')
    def test_altered_rpc_refused(self):
        make_witness(self.root,self.trust)
        p=self.root/'mcp.jsonl';p.write_text(p.read_text().replace('record_missing','record_changed'))
        self.assert_reject('capture bytes changed')
    def test_wrong_independent_signing_key_refused(self):
        make_witness(self.root,self.trust,other_key=True)
        self.assert_reject('signature verification FAILED')
    def test_unsupported_issuer_refused(self):
        make_witness(self.root,self.trust)
        p=self.trust;j=json.loads(p.read_text());j['trusted_recorders'][0]['issuer']='other';p.write_text(json.dumps(j))
        self.assert_reject('issuer or observer scope')
    def test_trust_store_embedded_in_capture_directory_refused(self):
        local=self.root/'my_own_keys.json';make_witness(self.root,local)
        x=self.call('--causal-trust-store',str(local))
        self.assertEqual(x.returncode,2)
        self.assertIn('outside untrusted capture',x.stderr)
    def test_wrong_trace_token_refused_even_when_signed(self):
        def mutate(w):w['links'][1]['trace_token_sha256']='0'*64
        make_witness(self.root,self.trust,mutate=mutate)
        self.assert_reject('correlation token digest')
    def test_missing_unsafe_falsified_observation_refused(self):
        def mutate(w):w['links'][1]['events'][1]['sha256']='0'*64
        make_witness(self.root,self.trust,mutate=mutate)
        self.assert_reject('boundary contents')
    def test_violated_event_order_refused(self):
        def mutate(w):w['links'][1]['events'][2]['sequence']=w['links'][1]['events'][1]['sequence']
        make_witness(self.root,self.trust,mutate=mutate)
        self.assert_reject('out-of-order')
    def test_replayed_link_for_wrong_call_refused(self):
        def mutate(w):w['links'][1]['mcp_call_id']=1
        make_witness(self.root,self.trust,mutate=mutate)
        self.assert_reject('witness pair differs')
    def test_duplicate_attested_case_refused(self):
        def mutate(w):w['links'].append(copy.deepcopy(w['links'][1]))
        make_witness(self.root,self.trust,mutate=mutate)
        self.assert_reject('duplicated or unmatched witnessed case')
    def test_signed_witness_on_different_raw_capture_refused(self):
        make_witness(self.root,self.trust)
        p=self.root/'pairs.json';j=json.loads(p.read_text());j['pairs'][1]['case_id']='NEW_CASE';p.write_text(json.dumps(j))
        self.assert_reject('capture bytes changed')
    def test_malformed_untrusted_capture_rejected_before_proof(self):
        (self.root/'mcp.jsonl').write_text('{ bad\n')
        self.assertEqual(self.call().returncode,2)
    def test_no_truststore_sarif_denied(self):
        x=cli(self.root,'--format','sarif')
        self.assertEqual(x.returncode,2)
        self.assertIn('SARIF',x.stderr)
    def test_unexpected_truststore_on_saved_matrix_refused(self):
        p=self.parent/'saved.json';p.write_text(json.dumps({'cases':[{'id':'X','translator':'test-dev','source':{'status':200,'content_type':'application/json','body':{'count':1}},'mcp':{'content':[{'type':'text','text':'{\"count\":1}'}],'isError':False,'structuredContent':{'count':1}}}]}))
        env={**os.environ,'PYTHONPATH':str(SRC)}
        x=subprocess.run([sys.executable,'-B','-m','risu_probe','analyze',str(p),
            '--causal-trust-store',str(self.parent/'anything.json')],env=env,text=True,capture_output=True)
        self.assertEqual(x.returncode,2)
        self.assertIn('requires an original',x.stderr)
    def test_missing_pairs_declined(self):
        (self.root/'pairs.json').unlink()
        self.assertEqual(self.call().returncode,2)
    def test_developer_pair_does_not_promote_even_with_arbitrary_claim(self):
        pair=json.loads((self.root/'pairs.json').read_text())
        pair['causality']='PROVEN_BY_DEVELOPER'
        (self.root/'pairs.json').write_text(json.dumps(pair))
        d=self.gate()
        self.assertEqual(d['causal_gate_v1']['summary']['CONFIRMED_LOSS'],0)
    def test_plain_json_output_contains_proof_warning(self):
        d=self.gate()
        self.assertIn('cannot prove',d['causal_gate_v1']['boundary'])

if __name__=='__main__':unittest.main(verbosity=2)
