"""24 deterministic evidence tests plus 150 seeded mutation counterexamples. Stdlib only."""
from __future__ import annotations
import copy,json,random,unittest
from risu_evidence import assess
from risu_probe import compare, VERSION
from risu_analyze import analyze

BODY={'type':'https://example.invalid/422','title':'validation failed',
      'status':422,'errors':[{'pointer':'#/items/0/name','message':'missing'}],
      'id':'synthetic-identifier','active':False,'count':7}

def source(body=BODY,status=422,content_type='application/problem+json'):
    return {'status':status,'content_type':content_type,'body':copy.deepcopy(body)}

def text(value,status=422,*,extra=None):
    obj={'content':[{'type':'text','text':value}],'isError':status>=400}
    if extra:obj.update(extra)
    return obj

def check(src,mcp):
    ev=assess(src,mcp)
    wire=compare(src,mcp,error_profile='json-errors')
    assert wire['evidence_v1']==ev
    return ev,wire

class Evidence(unittest.TestCase):
    def test_legacy_verdict_retained_but_text_json_reclassified(self):
        e,w=check(source(),text(json.dumps(BODY,sort_keys=True)))
        self.assertEqual(w['verdict'],'LOSS')
        self.assertEqual(e['body_recovery'],'EXACT_JSON_TEXT')
        self.assertEqual(e['body_loss_claim'],'NO_EXACT_INFORMATION_LOSS_PROVEN')
        self.assertEqual(e['recommended_action'],'EMIT_STRUCTURED_CONTENT')

    def test_mcpgen_envelope_json_text_and_status_are_recoverable(self):
        m=text(json.dumps({'tool':'get_order','status':'error','status_code':422,'data':BODY}))
        e,_=check(source(),m)
        self.assertEqual(e['body_recovery'],'EXACT_JSON_TEXT')
        self.assertEqual(e['envelope_path'],'/data')
        self.assertEqual(e['http_status'],'TEXT_STATUS_RECOVERABLE')
        self.assertEqual(e['error_flag'],'ERROR_FLAG_MATCH')

    def test_machine_exact_and_flag_independent(self):
        m={'structuredContent':copy.deepcopy(BODY),'isError':False,'_meta':{'observed_http_status':422}}
        e,w=check(source(),m)
        self.assertEqual(e['body_recovery'],'EXACT_MACHINE')
        self.assertEqual(e['error_flag'],'ERROR_FLAG_LOST')
        self.assertEqual(e['http_status'],'MACHINE_STATUS_MATCH')
        self.assertEqual(w['verdict'],'LOSS')

    def test_machine_wrapped_payload_is_not_destroyed(self):
        m={'structuredContent':{'tool':'get_order','data':copy.deepcopy(BODY)},'isError':True}
        e,_=check(source(),m)
        self.assertEqual(e['body_recovery'],'EXACT_MACHINE')
        self.assertEqual(e['machine_carrier'],'STRUCTURED_ENVELOPE_EXACT')

    def test_metadata_and_resource_are_distinguished(self):
        cases=[({'_meta':{'result':copy.deepcopy(BODY)},'isError':True},'METADATA_ONLY_EXACT'),
               ({'content':[{'type':'resource','resource':{
                 'mimeType':'application/problem+json','text':json.dumps(BODY)}}],
                 'isError':True},'TYPED_RESOURCE_EXACT')]
        for mc,channel in cases:
            with self.subTest(channel=channel):
                e,_=check(source(),mc);self.assertEqual(e['machine_carrier'],channel)

    def test_json_fence_and_label(self):
        cases=[('```json\n'+json.dumps(BODY)+'\n```','FENCED_JSON_TEXT_EXACT'),
               ('JSON:\n'+json.dumps(BODY),'LABELLED_JSON_TEXT_EXACT'),
               (json.dumps(BODY,indent=2),'ENTIRE_JSON_TEXT_EXACT')]
        for body_text,expected in cases:
            with self.subTest(expected=expected):
                e,_=check(source(),text(body_text));self.assertEqual(e['text_carrier'],expected)

    def test_unlabelled_prose_with_json_is_uncertified(self):
        e,_=check(source(),text('The payload might be '+json.dumps(BODY)+' but I did not send it'))
        self.assertEqual(e['body_recovery'],'UNVERIFIED_TEXT')
        self.assertEqual(e['body_loss_claim'],'NO_EXACT_INFORMATION_LOSS_PROVEN')

    def test_duplicate_keys_ambiguity_is_not_certified(self):
        j=json.dumps(BODY)
        e,_=check(source(),text('{"status":422,"status":422,"data":'+j+'}'))
        self.assertEqual(e['body_recovery'],'UNVERIFIED_TEXT')

    def test_nonfinite_output_is_not_certified(self):
        e,_=check(source(),text('{"data":'+json.dumps(BODY)+',"metric":NaN}'))
        self.assertEqual(e['body_recovery'],'UNVERIFIED_TEXT')
        e,_=check(source({'x':float('inf')}),{'structuredContent':{'x':float('inf')}})
        self.assertEqual(e['body_recovery'],'NOT_ASSESSED')

    def test_ambiguous_envelopes_uncertified(self):
        e,_=check(source(),text(json.dumps({'data':BODY,'body':BODY})))
        self.assertEqual(e['body_recovery'],'UNVERIFIED_TEXT')
        self.assertEqual(e['body_loss_claim'],'NO_EXACT_INFORMATION_LOSS_PROVEN')

    def test_integer_not_boolean_float_or_string(self):
        s=source({'x':1},status=200,content_type='application/json')
        for wrong in ({'x':True},{'x':1.0},{'x':'1'}):
            with self.subTest(wrong=wrong):
                e,_=check(s,{'structuredContent':wrong,'isError':False,
                             'content':[{'type':'text','text':json.dumps(wrong)}]})
                self.assertEqual(e['body_recovery'],'UNVERIFIED_TEXT')
        e,_=check(s,text(json.dumps({'x':1}),status=200))
        self.assertEqual(e['body_recovery'],'EXACT_JSON_TEXT')

    def test_value_or_field_missing_cannot_certify(self):
        a=copy.deepcopy(BODY);a['count']=999
        b=copy.deepcopy(BODY);b.pop('active')
        c=copy.deepcopy(BODY);c['errors'][0]['pointer']='#/items/2/name'
        for wrong in (a,b,c):
            with self.subTest(wrong=wrong):
                e,_=check(source(),text(json.dumps({'data':wrong})))
                self.assertNotIn(e['body_recovery'],('EXACT_MACHINE','EXACT_JSON_TEXT'))

    def test_proven_truncation_with_aligned_prefix_and_marker(self):
        big=dict(BODY)
        big['errors']=[{'pointer':'#/items/%d/value'%i,'detail':'invalid value'} for i in range(40)]
        prefix=json.dumps(big,separators=(',',':'))[:140]
        e,_=check(source(big),text(prefix+'… (truncated)'))
        self.assertEqual(e['body_recovery'],'PROVEN_TRUNCATED_PREVIEW')
        self.assertEqual(e['body_loss_claim'],'OBSERVED_TRUNCATED_PREVIEW')
        self.assertGreater(e['truncation']['omitted_min_chars'],0)
        self.assertNotIn('invalid value',json.dumps(e))

    def test_truncation_marker_alone_is_not_proof(self):
        for wrong in ['… (truncated)','other data ... (truncated)',json.dumps(BODY)+'… (truncated)']:
            with self.subTest(wrong=wrong[:30]):
                e,_=check(source(),text(wrong))
                self.assertNotEqual(e['body_recovery'],'PROVEN_TRUNCATED_PREVIEW')

    def test_json_text_fully_recoverable_even_with_marker_in_value(self):
        x={'errors':[{'pointer':'#/a','message':'… (truncated) original text'}],'count':1,'id':'foo'}
        e,_=check(source(x),text(json.dumps(x)))
        self.assertEqual(e['body_recovery'],'EXACT_JSON_TEXT')
        self.assertNotEqual(e['body_loss_claim'],'OBSERVED_TRUNCATED_PREVIEW')

    def test_status_conflicts_are_reported_independently(self):
        m=text(json.dumps({'status_code':409,'data':BODY}),
               extra={'_meta':{'observed_http_status':400}})
        e,_=check(source(),m)
        self.assertEqual(e['body_recovery'],'EXACT_JSON_TEXT')
        self.assertEqual(e['http_status'],'MACHINE_STATUS_CONFLICT')
        e,_=check(source(),text(json.dumps({'status_code':409,'data':BODY})))
        self.assertEqual(e['http_status'],'TEXT_STATUS_CONFLICT')

    def test_missing_body_not_equivalent_to_source_null(self):
        s=source(None,status=200,content_type='application/json')
        e,_=check(s,{'isError':False})
        self.assertEqual(e['body_recovery'],'NO_EXACT_CARRIER_OBSERVED')
        e,_=check(s,{'structuredContent':None,'isError':False})
        self.assertEqual(e['body_recovery'],'EXACT_MACHINE')

    def test_error_flag_only_nonjson_not_body(self):
        e,_=check(source('oops',status=404,content_type='text/plain'),{'isError':False})
        self.assertEqual(e['body_recovery'],'NOT_ASSESSED')
        self.assertEqual(e['error_flag'],'ERROR_FLAG_LOST')

    def test_deferred_and_consumer_scope_never_claim_whole(self):
        e,w=check(source(),{'resultType':'input_required'})
        self.assertEqual(e['body_recovery'],'DEFERRED')
        self.assertEqual(w['verdict'],'INPUT_REQUIRED')
        w=compare(source(),{'structuredContent':BODY,'isError':True},
                  error_profile='json-errors',required_paths=['/title'])
        self.assertEqual(w['evidence_v1']['reason'],'CONSUMER_SCOPED_CHECK')

    def test_no_creds_or_source_values_in_diagnostic_report(self):
        secret='SENSITIVE_SYNTHETIC_VALUE_NEVER_PRINT_'+('X'*50)
        s=source({'token':secret,'ok':False})
        e,_=check(s,text(json.dumps({'data':{'token':secret+'-wrong','ok':False}})))
        self.assertNotIn(secret,json.dumps(e))
        self.assertEqual(e['body_recovery'],'UNVERIFIED_TEXT')

    def test_success_extra_flag_is_independent(self):
        s=source({'code':200,'ok':True},status=200,content_type='application/json')
        e,_=check(s,{'structuredContent':s['body'],'isError':True})
        self.assertEqual(e['body_recovery'],'EXACT_MACHINE')
        self.assertEqual(e['error_flag'],'SPURIOUS_ERROR_FLAG')

    def test_seeded_metamorphic_mutation_150_pairs(self):
        rng=random.Random(3701)
        for i in range(150):
            body={'k':i,'enabled':i%2==0,'tags':[rng.randint(0,99) for _ in range(4)],
                  'payload':{'safe':str(rng.randint(0,10**9)),'marker':'R'+str(i)}}
            s=source(body,status=200,content_type='application/json')
            e,_=check(s,text(json.dumps({'data':body}),status=200))
            self.assertEqual(e['body_recovery'],'EXACT_JSON_TEXT')
            bad=copy.deepcopy(body);bad['payload']['marker']+='changed'
            e,_=check(s,text(json.dumps({'data':bad}),status=200))
            self.assertNotIn(e['body_recovery'],('EXACT_JSON_TEXT','EXACT_MACHINE'))

    def test_analysis_aggregates_both_legacy_and_calibrated_evidence(self):
        s=source();m=text(json.dumps({'data':BODY,'status_code':422}))
        report=analyze({'cases':[{'translator':'independent','id':'x','source':s,'mcp':m}]})
        self.assertEqual(report['summary']['LOSS'],1)
        self.assertEqual(report['evidence_summary']['EXACT_JSON_TEXT'],1)
        self.assertEqual(report['action_summary']['EMIT_STRUCTURED_CONTENT'],1)

    def test_version(self):
        self.assertEqual(VERSION,'0.9.3-experimental')

if __name__=='__main__':unittest.main(verbosity=2)
