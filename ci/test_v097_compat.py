"""v0.9.7 scanner-only controls: exact preservation, budgets, no execution.

Run with PYTHONPATH=dist/risu_v09_source after the SHA-verified upgrade.
No internet or third-party repository code is touched by these tests.
"""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from risu_static import scan, _find_files, MAX_BYTES, MAX_SPEC_BYTES, MAX_TOTAL_BYTES, _has_openapi_header
from risu_onboarding import first_check
from risu_probe import VERSION

SMALL={'openapi':'3.1.0','info':{'title':'synthetic','version':'1'},
       'paths':{'/safe':{'get':{'operationId':'read_status',
                              'responses':{'200':{'description':'ok'}}}}}}

class Compatibility(unittest.TestCase):
    def setUp(self):
        self._temp=tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.root=Path(self._temp.name)
    def write(self,name,body):
        p=self.root/name
        p.parent.mkdir(exist_ok=True,parents=True)
        p.write_text(body,encoding='utf-8')
        return p
    def test_version_and_python_original_limit(self):
        self.assertEqual(VERSION,'0.9.7-experimental')
        self.assertEqual(MAX_BYTES,512*1024)
        self.assertEqual(MAX_SPEC_BYTES,16*1024*1024)
        self.assertEqual(MAX_TOTAL_BYTES,35*1024*1024)
    def test_four_real_world_naming_patterns_and_dot_schema(self):
        self.write('open-api.yaml','openapi: 3.1.0\npaths: {}\n')
        self.write('specification/DigitalOcean-public.v2.yaml','openapi: 3.1.0\npaths: {}\n')
        self.write('spec/json/twilio_accounts_v1.json',json.dumps(SMALL))
        self.write('2020-09-14.yml','openapi: 3.1.0\npaths: {}\n')
        self.write('.schema/api.openapi.json',json.dumps(SMALL))
        result=scan(self.root)
        self.assertEqual(result['summary']['openapi_parsed'],5)
        self.assertEqual(result['status'],'NO_STATIC_FINDINGS')
        self.assertEqual(result['summary']['openapi_get_total'],2)
    def test_refuses_unrelated_json_and_private_hidden_folders(self):
        self.write('secrets/application.json','{"credential":"LOCAL_TEST_SENTINEL"}')
        self.write('.private/hidden.yaml','openapi: 3.1.0\npaths: {}\n')
        self.write('.git/config.json',json.dumps(SMALL))
        self.write('.venv/hidden.json',json.dumps(SMALL))
        result=scan(self.root)
        self.assertEqual(result['summary']['eligible_files'],0)
        self.assertEqual(result['summary']['openapi_parsed'],0)
        self.assertEqual(result['status'],'UNVERIFIED')
        self.assertNotIn('LOCAL_TEST_SENTINEL',json.dumps(result))
    def test_regular_supported_named_spec_unchanged(self):
        self.write('openapi.json',json.dumps(SMALL))
        self.assertEqual(scan(self.root)['summary']['openapi_parsed'],1)
    def test_non_header_json_not_selected_even_if_large(self):
        p=self.write('data/long.json','{"records":[1,2,3]}')
        self.assertFalse(_has_openapi_header(p))
        self.assertEqual(scan(self.root)['summary']['eligible_files'],0)
    def test_bounded_large_json_admitted_beyond_old_512k(self):
        large={**SMALL,'x-filler':'x'*700000}
        self.write('latest/large-arbitrary-file.json',json.dumps(large))
        r=scan(self.root)
        self.assertEqual(r['summary']['openapi_parsed'],1)
        self.assertEqual(r['summary']['incomplete_files'],0)
    def test_oversized_named_spec_flagged_not_loaded(self):
        p=self.write('openapi.json','')
        with p.open('wb') as f:f.truncate(MAX_SPEC_BYTES+1)
        r=scan(self.root)
        self.assertEqual(r['status'],'UNVERIFIED')
        self.assertEqual(r['summary']['incomplete_files'],1)
        self.assertIn('16777216',r['incomplete'][0]['reason'])
    def test_overlimit_python_unchanged(self):
        p=self.write('application.py','')
        with p.open('wb') as f:f.truncate(MAX_BYTES+1)
        r=scan(self.root)
        self.assertEqual(r['summary']['python_parsed'],0)
        self.assertIn('524288',r['incomplete'][0]['reason'])
    def test_symlink_disallowed_even_dot_schema(self):
        t=self.write('openapi.json',json.dumps(SMALL))
        link=self.root/'.schema'/'api.openapi.json'
        link.parent.mkdir()
        link.symlink_to(t)
        r=scan(self.root)
        self.assertEqual(r['summary']['openapi_parsed'],1)
        self.assertEqual(r['summary']['eligible_files'],1)
        with self.assertRaisesRegex(Exception,'symlink'):
            _find_files(link)
    def test_yaml_is_never_unsafe_constructed(self):
        self.write('open-api.yml','openapi: 3.1.0\npaths: {}\nx: !!python/object/apply:os.system ["echo BAD"]\n')
        r=scan(self.root)
        self.assertEqual(r['summary']['openapi_parsed'],0)
        self.assertEqual(r['summary']['incomplete_files'],1)
    def test_malformed_json_is_incomplete(self):
        self.write('openapi.json','{"openapi":')
        r=scan(self.root)
        self.assertEqual(r['summary']['incomplete_files'],1)
        self.assertEqual(r['summary']['openapi_parsed'],0)
    def test_hidden_env_is_not_scanned(self):
        self.write('.env','SECRET=CANARY_DO_NOT_EXPORT')
        self.write('.schema/real.json',json.dumps(SMALL))
        r=scan(self.root)
        self.assertEqual(r['summary']['eligible_files'],1)
        self.assertNotIn('SECRET=',json.dumps(r))
    def test_no_execution_with_python_file(self):
        self.write('runner.py',"raise RuntimeError('executed forbidden')\n")
        self.write('open-api.yaml','openapi: 3.1.0\npaths: {}\n')
        r=scan(self.root)
        self.assertEqual(r['summary']['python_parsed'],1)
        self.assertEqual(r['summary']['openapi_parsed'],1)
    def test_parse_json_header_outside_initial_sniff_not_auto_guessed(self):
        self.write('unusual.json',' '*20000+json.dumps(SMALL))
        self.assertEqual(scan(self.root)['summary']['openapi_parsed'],0)
    def test_preserve_source_only_no_network(self):
        self.write('openapi.json',json.dumps(SMALL))
        r=scan(self.root)
        self.assertEqual(r['result_scope'],'OFFLINE_SOURCE_ONLY')
        self.assertNotIn('confirmed',json.dumps(r['findings']).lower())
    def test_explicit_path_still_supported(self):
        p=self.write('fixture.json',json.dumps(SMALL))
        r=scan(p)
        self.assertEqual(r['summary']['openapi_parsed'],1)
    def test_get_metadata_conservative_analysis_unchanged(self):
        x=json.loads(json.dumps(SMALL))
        x['paths']['/safe']['get']['security']=[{'apiKey':[]}]
        self.write('openapi.json',json.dumps(x))
        r=scan(self.root)
        self.assertEqual(r['openapi'][0]['get_excluded_by_conservative_metadata'],1)
        self.assertEqual(r['openapi'][0]['get_with_explicit_examples_or_no_required_arguments'],0)

if __name__=='__main__':
    unittest.main(verbosity=2)
