"""Independent source-equivalence fixture tests, no target imports or execution."""
from __future__ import annotations
import ast,tempfile,types,unittest,zipfile
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'p5e'))
from optimize_ast import patch

def load(name,source):
    x=types.ModuleType(name)
    exec(compile(source,name,'exec'),x.__dict__)
    return x

SAMPLES=[
 ('details_client.py','def make_api_request():\n    return (False, {"error":"bad", "details":{"code":"X"}})\n'),
 ('client.py','from stuff.api.client import make_api_request\nasync def get_thing():\n    ok,response=await make_api_request()\n    if not ok:\n        return {"error":response.get("error")}\n'),
 ('simple.py','def get_thing():\n    ok,response=make_api_request()\n    if ok is False:\n        return {"error":response.get("error")}\n'),
 ('bounded.py','def shorten_error_body(response):\n    return response.text[:100]+" ... truncated"\n'),
 ('http_error.py','def thing():\n    try:\n        return 3\n    except HTTPStatusError as err:\n        return {"error":str(err)}\n'),
 ('slice_in_error.py','def my_error_handler(response):\n    return response.text[:128]\n'),
 ('nested.py','def thing():\n    def child():\n        try:\n            raise HTTPError()\n        except HTTPError as e:\n            return {"error":str(e)}\n    return child\n'),
 ('not_a_candidate.py','def read(response):\n    return response.text[:120]\n'),
 ('invalid.py','def broken(\n'),
]
class ASTOptimizationEquivalence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with zipfile.ZipFile(ROOT/'baseline'/'wheels'/'risu_probe_preview-0.9.19.dev0-py3-none-any.whl') as z:
            old=z.read('risu_static.py').decode()
        new=(ROOT/'p5e'/'product_source'/'risu_static.py').read_text(encoding='utf-8')
        cls.old=old;cls.new=new
        cls.before=load('before',old);cls.after=load('after',new)
    def test_patch_is_exact(self):
        self.assertEqual(patch(self.old),self.new)
    def test_all_rules_equal_on_sample_corpus(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)
            for name,source in SAMPLES:(folder/name).write_text(source)
            a=self.before.scan(folder);b=self.after.scan(folder)
            self.assertEqual(a,b)
            self.assertGreaterEqual(len(a['findings']),4)
            for code in ('RPY201','RPY202','RPY203'):
                self.assertTrue(any(x['rule_id']==code for x in a['findings']),code)
    def test_each_source_case_exact(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/'sample.py'
            for name,src in SAMPLES:
                f.write_text(src)
                self.assertEqual(self.before.scan(f),self.after.scan(f),name)
    def test_binding_helper_same_result(self):
        fn=ast.parse('def f():\n  ok,resp=make_api_request()\n  return ok').body[0]
        self.assertEqual(self.before._api_call_bindings(fn),self.after._api_call_bindings(fn))
    def test_no_target_code_execution(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);marker=root/'EXECUTED'
            (root/'unsafe.py').write_text('from pathlib import Path\nPath('+repr(str(marker))+').write_text("bad")\n')
            self.after.scan(root)
            self.assertFalse(marker.exists())
    def test_large_file_incomplete_diagnostic_same(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/'large.py').write_text('x="'+('a'*530000)+'"')
            self.assertEqual(self.before.scan(root),self.after.scan(root))
    def test_nested_return_visit_order(self):
        src='def fn():\n  ok,x=make_api_request()\n  if not ok:\n    for y in (1,):\n      if y: return {"error":x.get("error")}\n'
        a=self.before._python_rules([(Path('/tmp/f.py'),ast.parse(src))],Path('/tmp'))
        b=self.after._python_rules([(Path('/tmp/f.py'),ast.parse(src))],Path('/tmp'))
        self.assertEqual(a,b)
if __name__=='__main__':unittest.main()
