"""Actual public CLI contract for a synthetic and offline model-only minimal repro."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import risu_probe

class CLI(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.input=self.root/'pair.json'
        body={'error':{'code':'rate_limit','message':'synthetic','unused':'x'},'debug':'unused'}
        mcp={'content':[{'type':'text','text':json.dumps({
            'status_code':400,'status':'error','data':body})}],'isError':True}
        self.input.write_text(json.dumps({'source':{
            'status':400,'content_type':'application/json','body':body},
            'mcp_result':mcp}))
    def command(self,*extra):
        p=Path(sys.modules['risu_probe'].__file__)
        return subprocess.run([sys.executable,str(p),'reproduce',str(self.input),
                               '--path','/error/code','--out',str(self.root/'repro'),*extra],
                              text=True,capture_output=True,timeout=12)
    def test_default_does_not_export_potentially_sensitive_response(self):
        p=self.command()
        self.assertEqual(p.returncode,2,p.stdout+p.stderr)
        self.assertIn('REQUIRES_EXPLICIT_SYNTHETIC_APPROVAL',p.stderr)
        self.assertFalse((self.root/'repro').exists())
    def test_generates_1minimal_model_only_repro(self):
        p=self.command('--allow-synthetic-export')
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        out=json.loads(p.stdout)
        self.assertEqual(out['status'],'GENERATED_MODEL_ONLY')
        self.assertEqual(out['minimality'],'ONE_MINIMAL_DELETIONS')
        reduced=json.loads((self.root/'repro'/'synthetic_minimal_pair.json').read_text())
        self.assertEqual(reduced['source']['body'],{'error':{'code':'rate_limit'}})
        meta=json.loads((self.root/'repro'/'reproduction_report.json').read_text())
        self.assertEqual(meta['verification_scope'],'MODEL_ONLY_NOT_LIVE_REPLAY')
        self.assertGreater(meta['original_bytes'],meta['minimal_bytes'])
    def test_never_silently_overwrites_existing_repro_folder(self):
        p=self.command('--allow-synthetic-export')
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        q=self.command('--allow-synthetic-export')
        self.assertEqual(q.returncode,2,q.stdout+q.stderr)
    def test_explicit_status_conflict_rejected(self):
        payload=json.loads(self.input.read_text())
        payload['source']['status']=422
        self.input.write_text(json.dumps(payload))
        result=self.command('--allow-synthetic-export')
        self.assertEqual(result.returncode,2)
        self.assertIn('STATUS_DIFFER',result.stderr)
    def test_json_data_mismatch_rejected(self):
        payload=json.loads(self.input.read_text())
        payload['source']['body']['error']['code']='other'
        self.input.write_text(json.dumps(payload))
        result=self.command('--allow-synthetic-export')
        self.assertEqual(result.returncode,2)
        self.assertIn('BODY_DIFFER',result.stderr)
    def test_zero_config_version(self):
        p=Path(sys.modules['risu_probe'].__file__)
        result=subprocess.run([sys.executable,str(p),'--version'],
                              capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0)
        self.assertIn('0.9.7-experimental',result.stdout)

if __name__=='__main__':
    unittest.main(verbosity=2)
