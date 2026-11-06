"""P3: tests prove the repair is non-destructive and regression-sensitive."""
import copy
import json
import random
import unittest
from risu_fixverify import prepare_consumer_result,verify_preserved,digest_without_values
from risu_repair import RepairRejected,read_structured
from risu_witness import witness

def text_result(body,status=400,flag=True,meta=None):
    r={'content':[{'type':'text','text':json.dumps({
        'status_code':status,'data':body})}], 'isError':flag}
    if meta is not None:r['_meta']=meta
    return r
def typed(body,status=400):
    return {'structuredContent':copy.deepcopy(body),
            'isError':status>=400,
            '_meta':{'observed_http_status':status,'synthetic':'control'},
            'content':[{'type':'text','text':'NOT_JSON_AND_DO_NOT_PARSE'}]}

class Nonregression(unittest.TestCase):
    def test_already_structured_passes_through_without_any_field_changes(self):
        v=typed({'message':'Not Found'})
        old=copy.deepcopy(v)
        n=prepare_consumer_result(v)
        self.assertEqual(n,old)
        self.assertEqual(v,old)
        self.assertIsNot(n,v)
        self.assertIsNot(n['structuredContent'],v['structuredContent'])
        self.assertTrue(verify_preserved(v,n))
    def test_already_structured_with_text_poison_keeps_typed_original(self):
        v=typed({'error':{'code':'rate_limit'}})
        v['content'][0]['text']=json.dumps({'status_code':400,'data':{'error':{'code':'wrong'}}})
        n=prepare_consumer_result(v)
        self.assertEqual(n['structuredContent']['error']['code'],'rate_limit')
        self.assertEqual(n,v)
    def test_existing_structured_null_rejected_no_fallback(self):
        v=typed({'x':1})
        v['structuredContent']=None
        with self.assertRaisesRegex(RepairRejected,'INVALID_EXISTING'):
            prepare_consumer_result(v)
    def test_existing_structured_wrong_type_rejected(self):
        for val in (True,1,'text',None):
            v=typed({'x':1});v['structuredContent']=val
            with self.subTest(val=val),self.assertRaises(RepairRejected):
                prepare_consumer_result(v)
    def test_conflicting_explicit_statuses_rejected(self):
        v=typed({'x':1});v['_meta']['httpStatus']=409
        with self.assertRaisesRegex(RepairRejected,'CONFLICTING_STATUS'):
            prepare_consumer_result(v)
    def test_bad_meta_status_type_rejected(self):
        for val in (True,'400',600,0):
            v=typed({'x':1});v['_meta']['observed_http_status']=val
            with self.subTest(val=val),self.assertRaises(RepairRejected):
                prepare_consumer_result(v)
    def test_already_typed_error_flag_conflict_rejected(self):
        v=typed({'message':'Not Found'});v['isError']=False
        with self.assertRaisesRegex(RepairRejected,'ERROR_FLAG_CONFLICT'):
            prepare_consumer_result(v)
    def test_text_promotion_restores_fields_without_mutating_input(self):
        body={'error':{'code':'rate_limit'},'unrelated':{'a':1}}
        v=text_result(body)
        snapshot=copy.deepcopy(v)
        n=prepare_consumer_result(v)
        self.assertEqual(n['structuredContent'],body)
        self.assertEqual(n['_meta']['observed_http_status'],400)
        self.assertEqual(snapshot,v)
    def test_text_mutated_required_field_detected(self):
        src={'status':400,'content_type':'application/json','body':{'error':{'code':'rate_limit'}}}
        exact=text_result(src['body'])
        repaired=prepare_consumer_result(exact)
        proof=witness(src,repaired,['/error/code'])
        self.assertEqual(proof['models']['structured-only']['outcome'],'PASS')
        broken=copy.deepcopy(repaired);broken['structuredContent']['error'].pop('code')
        proof=witness(src,broken,['/error/code'])
        self.assertEqual(proof['models']['structured-only']['outcome'],'FAIL')
    def test_success_http_200_payload_retained(self):
        v=text_result({'ok':True,'id':'synthetic'},200,False)
        result=prepare_consumer_result(v)
        self.assertEqual(result['structuredContent'],{'ok':True,'id':'synthetic'})
        self.assertFalse(result['isError'])
    def test_poisoned_first_text_cannot_be_skipped(self):
        v=text_result({'x':1})
        v['content'].insert(0,{'type':'text','text':'junk'})
        with self.assertRaises(RepairRejected):
            prepare_consumer_result(v)
    def test_malicious_duplicate_keys_rejected(self):
        v=text_result({'x':1})
        v['content'][0]['text']='{"status_code":400,"data":{"x":1},"data":{"x":2}}'
        with self.assertRaises(RepairRejected):
            prepare_consumer_result(v)
    def test_missing_iserror_flag_rejected(self):
        v=text_result({'x':1});del v['isError']
        with self.assertRaises(RepairRejected):
            prepare_consumer_result(v)
    def test_non_object_mcp_rejected(self):
        for v in (None,[],42):
            with self.subTest(v=v),self.assertRaises(RepairRejected):
                prepare_consumer_result(v)
    def test_original_observation_is_not_replaced_by_bridge(self):
        source=typed({'message':'Not Found'})
        before=digest_without_values(source)
        n=prepare_consumer_result(source)
        self.assertEqual(before,digest_without_values(n))
        n['structuredContent']['message']='changed'
        self.assertEqual(source['structuredContent']['message'],'Not Found')
    def test_empty_but_valid_typed_payload_is_preserved_not_reparsed(self):
        m={'structuredContent':{},'isError':False,
           'content':[{'type':'text','text':'{"status_code":500,"data":{"fake":true}}'}]}
        self.assertEqual(prepare_consumer_result(m),m)
    def test_valid_existing_typed_payload_without_meta_does_not_invent_status(self):
        m={'structuredContent':{'id':'synthetic'},'isError':False}
        self.assertEqual(prepare_consumer_result(m),m)
        self.assertNotIn('_meta',prepare_consumer_result(m))
    def test_unknown_additional_fields_are_retained_exactly(self):
        m=typed({'status':422,'data':[1,{'nested':None}]})
        m['customVendorField']={'list':[True,2.5,'unrelated']}
        self.assertTrue(verify_preserved(prepare_consumer_result(m),m))
    def test_150_deterministic_cross_status_positive_controls(self):
        r=random.Random(6411)
        for i in range(150):
            status=r.choice([200,201,400,401,404,409,422,429,503])
            body={'id':i,'flag':i%2==0,'values':[r.randint(0,1000),None]}
            v=typed(body,status)
            self.assertTrue(verify_preserved(prepare_consumer_result(v),v))
            m=text_result(body,status,status>=400)
            corrected=prepare_consumer_result(m)
            self.assertEqual(corrected['structuredContent'],body)
            self.assertEqual(corrected['_meta']['observed_http_status'],status)
    def test_repair_is_refused_for_status_metadata_mismatch(self):
        v=text_result({'x':1},400,True,{'observed_http_status':409})
        with self.assertRaises(RepairRejected):
            prepare_consumer_result(v)

if __name__=='__main__':unittest.main(verbosity=2)
