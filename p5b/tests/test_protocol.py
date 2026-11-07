import importlib.util
from pathlib import Path
import unittest
HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('p5b_proxy',HERE/'proxy.py')
proxy=importlib.util.module_from_spec(spec);spec.loader.exec_module(proxy)

class TestProducerRepair(unittest.TestCase):
    def setUp(self):
        self.request={'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'get_index','arguments':{'path_indexUid':'does-not-exist'}}}
        self.broken={'jsonrpc':'2.0','id':3,'result':{'content':[{'type':'text','text':'failed'}],'structuredContent':{'error':'API request failed: 404 - Index missing'},'isError':False}}
        self.source={'message':'Index missing','code':'index_not_found','type':'invalid_request','link':'https://docs.meilisearch.com'}
    def test_repair_preserves_error_code_and_status(self):
        out,changed=proxy.restore_source_404(self.request,self.broken,self.source)
        self.assertTrue(changed)
        self.assertTrue(out['result']['isError'])
        self.assertEqual(out['result']['structuredContent'],self.source)
        self.assertIn('index_not_found',out['result']['content'][0]['text'])
    def test_backend_unmodified(self):
        before=repr(self.broken)
        proxy.restore_source_404(self.request,self.broken,self.source)
        self.assertEqual(repr(self.broken),before)
    def test_success_passes_through(self):
        request={**self.request,'params':{'name':'get_index','arguments':{'path_indexUid':'movies'}}}
        self.assertEqual(proxy.restore_source_404(request,self.broken,self.source),(self.broken,False))
    def test_other_tool_passes_through(self):
        request={**self.request,'params':{'name':'get_other','arguments':{'path_indexUid':'does-not-exist'}}}
        self.assertEqual(proxy.restore_source_404(request,self.broken,self.source),(self.broken,False))
    def test_missing_source_field_denied(self):
        bad=dict(self.source);del bad['code']
        with self.assertRaises(ValueError):proxy.restore_source_404(self.request,self.broken,bad)
    def test_source_wrong_code_denied(self):
        bad=dict(self.source,code='wrong')
        with self.assertRaises(ValueError):proxy.restore_source_404(self.request,self.broken,bad)
    def test_backend_changed_denied(self):
        bad={'jsonrpc':'2.0','id':3,'result':{'structuredContent':{'other':'data'},'isError':False}}
        with self.assertRaises(ValueError):proxy.restore_source_404(self.request,bad,self.source)
    def test_backend_not_loss_denied(self):
        bad={'jsonrpc':'2.0','id':3,'result':{'structuredContent':self.source,'isError':False}}
        with self.assertRaises(ValueError):proxy.restore_source_404(self.request,bad,self.source)
    def test_no_mutation_on_normal_nonmatching(self):
        req={**self.request,'method':'tools/list'}
        self.assertEqual(proxy.restore_source_404(req,self.broken,self.source),(self.broken,False))

if __name__=='__main__':unittest.main()