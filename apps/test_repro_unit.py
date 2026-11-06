"""Offline regression and adversarial safety checks for v0.9.5 developer fix."""
import copy
import json
import random
import unittest
from risu_repair import promote_text_json,read_structured,RepairRejected
from risu_minimize import minimize,MinimizationError,canonical

def frame(status=400,body=None,flag=True,meta=None):
    if body is None:body={'error':{'code':'rate_limit'}}
    m={'content':[{'type':'text','text':json.dumps({
         'tool':'sample','status':'error','status_code':status,'data':body})}],
       'isError':flag}
    if meta is not None:m['_meta']=meta
    return m

class Repair(unittest.TestCase):
    def test_text_only_to_machine_exact(self):
        m=frame()
        saved=copy.deepcopy(m)
        normalized=promote_text_json(m)
        self.assertEqual(normalized['structuredContent'],{'error':{'code':'rate_limit'}})
        self.assertEqual(normalized['_meta']['observed_http_status'],400)
        self.assertEqual(m,saved,'repair modified original in place')
        self.assertEqual(normalized['content'],m['content'])
    def test_metadata_retained(self):
        m=frame(meta={'trace':'synthetic'})
        n=promote_text_json(m)
        self.assertEqual(n['_meta']['trace'],'synthetic')
    def test_no_override_existing_typed_body(self):
        with self.assertRaisesRegex(RepairRejected,'EXISTING_STRUCTURED'):
            promote_text_json({**frame(),'structuredContent':{'known':'good'}})
    def test_conflicting_meta_rejected(self):
        with self.assertRaisesRegex(RepairRejected,'STATUS_METADATA_CONFLICT'):
            promote_text_json(frame(meta={'observed_http_status':422}))
    def test_missing_or_false_error_flag_rejected(self):
        for value in [False,None,1,'true']:
            m=frame(flag=value)
            with self.subTest(value=value),self.assertRaises(RepairRejected):
                promote_text_json(m)
    def test_status_bool_and_out_of_range_rejected(self):
        for status in (True,5999,0,'400',None):
            m=frame()
            m['content'][0]['text']=json.dumps({'status_code':status,'data':{'x':1}})
            with self.subTest(status=status),self.assertRaises(RepairRejected):
                promote_text_json(m)
    def test_extra_prose_rejected(self):
        m=frame()
        m['content'][0]['text']='payload: '+m['content'][0]['text']
        with self.assertRaisesRegex(RepairRejected,'NOT_UNAMBIGUOUS_JSON'):
            promote_text_json(m)
    def test_duplicate_key_and_nan_rejected(self):
        for txt in ['{"status_code":400,"status_code":400,"data":{}}',
                    '{"status_code":400,"data":{"value":NaN}}']:
            m=frame();m['content'][0]['text']=txt
            with self.subTest(txt=txt),self.assertRaises(RepairRejected):
                promote_text_json(m)
    def test_untrusted_first_text_not_skipped(self):
        m=frame()
        m['content'].insert(0,{'type':'text','text':'not json'})
        with self.assertRaises(RepairRejected):
            promote_text_json(m)
    def test_no_text_rejected(self):
        with self.assertRaises(RepairRejected):
            promote_text_json({'content':[],'isError':True})
    def test_invalid_data_rejected(self):
        for body in (None,1,'text',False):
            m=frame()
            m['content'][0]['text']=json.dumps({'status_code':400,'data':body})
            with self.subTest(body=body),self.assertRaises(RepairRejected):
                promote_text_json(m)
    def test_success_with_false_flag(self):
        m=frame(status=200,body={'result':'ok'},flag=False)
        n=promote_text_json(m)
        self.assertEqual(n['structuredContent']['result'],'ok')
    def test_random_conflict_types_rejected(self):
        rng=random.Random(7401)
        for _ in range(80):
            status=rng.choice([401,402,404,409,422,429])
            mismatch=rng.choice([400,200,500,True,'bad'])
            if mismatch==status:continue
            m=frame(status=status,meta={'observed_http_status':mismatch})
            with self.assertRaises(RepairRejected):
                promote_text_json(m)

class Shrinking(unittest.TestCase):
    def test_one_minimal_nested_error_code(self):
        value={'error':{'code':'rate_limit','type':'invalid_request_error',
                        'message':'foo','diagnostics':[1,2,3]},
               'ignored':{'a':[4,5]}}
        prior=copy.deepcopy(value)
        def oracle(obj):
            return isinstance(obj,dict) and isinstance(obj.get('error'),dict) and obj['error'].get('code')=='rate_limit'
        result=minimize(value,oracle)
        self.assertEqual(result['minimal'],{'error':{'code':'rate_limit'}})
        self.assertEqual(result['minimality'],'ONE_MINIMAL_DELETIONS')
        self.assertLess(result['minimal_bytes'],result['original_bytes'])
        self.assertEqual(prior,value)
    def test_one_minimal_github_notfound(self):
        value={'message':'Not Found','documentation_url':'https://example.invalid',
               'status':'404','extra':['x','y']}
        result=minimize(value,lambda obj: isinstance(obj,dict) and obj.get('message')=='Not Found')
        self.assertEqual(result['minimal'],{'message':'Not Found'})
        self.assertEqual(result['minimality'],'ONE_MINIMAL_DELETIONS')
    def test_one_minimal_array_index(self):
        result=minimize({'errors':['bad','good','irrelevant']},
          lambda obj: isinstance(obj,dict) and 'good' in obj.get('errors',[]))
        self.assertEqual(result['minimal'],{'errors':['good']})
        self.assertEqual(result['minimality'],'ONE_MINIMAL_DELETIONS')
    def test_reject_non_reproducing_seed(self):
        with self.assertRaisesRegex(MinimizationError,'INITIAL_COUNTEREXAMPLE'):
            minimize({'x':1},lambda x:False)
    def test_reject_non_json_and_deep(self):
        with self.assertRaises(MinimizationError):
            minimize({'secret':float('nan')},lambda x:True)
        deep={'safe':True}
        for _ in range(90):deep={'a':deep}
        with self.assertRaises(MinimizationError):
            minimize(deep,lambda x:True)
    def test_budget_incomplete_explicit(self):
        data={str(i):i for i in range(60)}
        output=minimize(data,lambda x:True,max_checks=2)
        self.assertEqual(output['minimality'],'INCOMPLETE_BUDGET_OR_SEARCH')
    def test_deterministic_metamorphic_100(self):
        rng=random.Random(981)
        for x in range(100):
            value={'required':{'flag':x,'token':'test-only'},
                   'extra':{str(i):rng.randrange(1,10**6) for i in range(5)}}
            result=minimize(value,
                lambda obj: isinstance(obj,dict) and
                            isinstance(obj.get('required'),dict) and
                            obj['required'].get('flag')==x)
            self.assertEqual(result['minimal'],{'required':{'flag':x}})
            self.assertEqual(result['minimality'],'ONE_MINIMAL_DELETIONS')

if __name__=='__main__':
    unittest.main(verbosity=2)
