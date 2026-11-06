"""P4-H native-capture bridge: previously unseen dev-style formats + fail-closed controls."""
from __future__ import annotations
import copy,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'src'
HAR={"log":{"version":"1.2","entries":[
 {"request":{"method":"GET","url":"http://127.0.0.1:29123/records/valid"},
  "response":{"status":200,"headers":[{"name":"Content-Type","value":"application/json"}],
              "content":{"mimeType":"application/json","text":'{"id":"valid","count":7}'}}},
 {"request":{"method":"GET","url":"http://127.0.0.1:29123/records/missing"},
  "response":{"status":404,"headers":[{"name":"Content-Type","value":"application/json"}],
              "content":{"mimeType":"application/json","text":'{"code":"record_missing","message":"No such record"}'}}}
]}}
RPC=[
 {"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"fetch_record","arguments":{"record_id":"valid"}}},
 {"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text","text":'{"id":"valid","count":7}'}],
        "isError":False,"structuredContent":{"id":"valid","count":7}}},
 {"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"fetch_record","arguments":{"record_id":"missing"}}},
 {"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text","text":'{"code":"record_missing","message":"No such record"}'}],"isError":False}},
]
PAIRS={"schema":"risu-explicit-capture-pairing-v1","pairs":[
 {"case_id":"EXTERNAL_STYLE_200","target":"SDK_OTHER_SERVER","http_entry":0,"mcp_call_id":1,"tool":"fetch_record"},
 {"case_id":"EXTERNAL_STYLE_404","target":"SDK_OTHER_SERVER","http_entry":1,"mcp_call_id":2,"tool":"fetch_record"},
]}

def make(root,har=None,rpc=None,pairs=None,consumers=None):
 (root/'capture.har').write_text(json.dumps(HAR if har is None else har))
 (root/'mcp.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in (RPC if rpc is None else rpc)))
 (root/'pairs.json').write_text(json.dumps(PAIRS if pairs is None else pairs))
 if consumers is not None:(root/'consumer.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in consumers))

def run_cli(root,flags=('--recovery','--format','json')):
 env=os.environ.copy();env['PYTHONPATH']=str(SRC)
 return subprocess.run([sys.executable,'-B','-m','risu_probe','analyze',str(root),*flags],env=env,text=True,capture_output=True,timeout=15)

class NativeInterop(unittest.TestCase):
 def setUp(self):
    self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
    self.path=Path(self.temp.name);make(self.path)
 def rewrite(self,har=None,rpc=None,pairs=None,consumers=None):
    make(self.path,har,rpc,pairs,consumers)
 def check_reject(self,substring):
    p=run_cli(self.path)
    self.assertEqual(p.returncode,2,p.stdout)
    self.assertIn(substring,p.stderr)
 def test_new_native_capture_success_and_loss(self):
    p=run_cli(self.path)
    self.assertEqual(p.returncode,0,p.stderr)
    a=json.loads(p.stdout)
    self.assertEqual(a['summary']['PRESERVED'],1)
    self.assertEqual(a['summary']['LOSS'],1)
    self.assertEqual(a['recovery_v1']['summary']['error_flag_lost'],1)
    self.assertEqual(a['recovery_v1']['summary']['consumer_unverified'],2)
    self.assertEqual(a['recovery_v1']['cases'][1]['mcp']['full_body'],'EXACT_JSON_TEXT')
    self.assertEqual(a['recovery_v1']['cases'][0]['mcp']['full_body'],'EXACT_MACHINE')
    self.assertNotIn('No such record',p.stdout)
    self.assertNotIn('record_missing',p.stdout)
    self.assertEqual(a['capture_bridge_v1']['join_kind'],'EXPLICIT_UNVERIFIED_DEVELOPER_PAIRS')
 def test_no_recovery_is_unchanged_core(self):
    p=run_cli(self.path,('--format','json'))
    self.assertEqual(p.returncode,0,p.stderr)
    x=json.loads(p.stdout)
    self.assertNotIn('recovery_v1',x)
    self.assertEqual(x['summary']['LOSS'],1)
 def test_fail_on_loss_keeps_original_exit(self):
    self.assertEqual(run_cli(self.path,('--recovery','--fail-on-loss','--format','json')).returncode,1)
 def test_cross_type_rpc_ids_not_conflated(self):
    r=copy.deepcopy(RPC);r[2]['id']='1';r[3]['id']='1'
    pair=copy.deepcopy(PAIRS);pair['pairs'][1]['mcp_call_id']='1'
    self.rewrite(rpc=r,pairs=pair)
    self.assertEqual(run_cli(self.path).returncode,0)
 def test_unpaired_rpc_is_rejected(self):
    r=copy.deepcopy(RPC);r.pop()
    self.rewrite(rpc=r);self.check_reject('missing')
 def test_rpc_protocol_error_is_not_mcp_tool_error(self):
    r=copy.deepcopy(RPC);r[3]={'jsonrpc':'2.0','id':2,'error':{'code':-32603,'message':'server error'}}
    self.rewrite(rpc=r);self.check_reject('protocol error')
 def test_duplicate_rpc_id_rejected(self):
    self.rewrite(rpc=RPC+[RPC[1]]);self.check_reject('duplicate JSON-RPC')
 def test_duplicate_har_reuse_rejected(self):
    x=copy.deepcopy(PAIRS);x['pairs'][1]['http_entry']=0
    self.rewrite(pairs=x);self.check_reject('reused')
 def test_manifest_missing_rejected(self):
    (self.path/'pairs.json').unlink();self.check_reject('capture requires')
 def test_manifest_wrong_tool_rejected(self):
    x=copy.deepcopy(PAIRS);x['pairs'][0]['tool']='different'
    self.rewrite(pairs=x);self.check_reject('tool name')
 def test_jsonrpc_input_required_rejected(self):
    x=copy.deepcopy(RPC);x[3]['result']['resultType']='input_required'
    self.rewrite(rpc=x);self.check_reject('input_required')
 def test_untrusted_base64_har_rejected(self):
    h=copy.deepcopy(HAR);h['log']['entries'][1]['response']['content']['encoding']='base64'
    self.rewrite(har=h);self.check_reject('encoded HAR')
 def test_header_conflict_rejected(self):
    h=copy.deepcopy(HAR);h['log']['entries'][0]['response']['content']['mimeType']='text/html'
    self.rewrite(har=h);self.check_reject('disagree')
 def test_sensitive_authorization_header_not_exported(self):
    h=copy.deepcopy(HAR);h['log']['entries'][1]['request']['headers']=[{'name':'Authorization','value':'Bearer SECRET_CANARY_123456789'}]
    self.rewrite(har=h)
    p=run_cli(self.path)
    self.assertEqual(p.returncode,0,p.stderr)
    self.assertNotIn('SECRET_CANARY',p.stdout)
 def test_response_duplicate_keys_rejected(self):
    h=copy.deepcopy(HAR);h['log']['entries'][1]['response']['content']['text']='{"code":"a","code":"b"}'
    self.rewrite(har=h);self.check_reject('duplicate JSON key')
 def test_nested_boolean_not_equal_integer(self):
    r=copy.deepcopy(RPC);r[1]['result']['structuredContent']['count']=True
    self.rewrite(rpc=r)
    p=run_cli(self.path);self.assertEqual(p.returncode,0,p.stderr)
    self.assertEqual(json.loads(p.stdout)['recovery_v1']['cases'][0]['mcp']['full_body'],'EXACT_JSON_TEXT')
    self.assertNotEqual(json.loads(p.stdout)['recovery_v1']['cases'][0]['mcp']['fields'][1]['category'],'TYPED_FIELD')
 def test_refuse_missing_consumer_inference(self):
    p=run_cli(self.path)
    self.assertIsNone(json.loads(p.stdout)['recovery_v1']['cases'][1]['consumer'])
 def test_langchain_serialized_native_message(self):
    rows=[{'call_id':2,'kind':'langchain_toolmessage','message':{'type':'tool','status':'success','content':'{"code":"record_missing","message":"No such record"}'}}]
    self.rewrite(consumers=rows)
    p=run_cli(self.path)
    self.assertEqual(p.returncode,0,p.stderr)
    r=json.loads(p.stdout)['recovery_v1']['cases'][1]
    self.assertEqual(r['consumer']['full_body'],'EXACT_JSON_TEXT')
    self.assertEqual(r['consumer_execution_kind_claimed'],'CAPTURED_LANGCHAIN_TOOLMESSAGE_ORIGIN_UNVERIFIED')
 def test_unknown_consumer_format_fails_closed(self):
    self.rewrite(consumers=[{'call_id':2,'kind':'unknown','message':{}}]);self.check_reject('consumer format unsupported')
 def test_consumer_is_not_attributed_if_other_call(self):
    self.rewrite(consumers=[{'call_id':7,'kind':'langchain_toolmessage','message':{'type':'tool','content':'{}'}}])
    p=run_cli(self.path)
    self.assertEqual(p.returncode,0,p.stderr)
    self.assertEqual(json.loads(p.stdout)['recovery_v1']['summary']['consumer_unverified'],2)
 def test_reject_malformed_nonfinite_capture(self):
    (self.path/'mcp.jsonl').write_text('{"jsonrpc":"2.0","id":1,"result":{"content":[],"isError":NaN}}\n')
    self.check_reject('nonfinite')
 def test_reject_symlink_har(self):
    f=self.path/'capture.har';content=f.read_bytes();f.unlink()
    target=self.path/'outside.har';target.write_bytes(content);f.symlink_to(target)
    self.check_reject('nonsymlink')

if __name__=='__main__':unittest.main(verbosity=2)