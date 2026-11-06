"""Frozen 10-file third-party HAR/MCP corpus field trial; no credentials or vendor calls."""
from pathlib import Path
import argparse,hashlib,json,os,re,shutil,subprocess,tempfile,urllib.request

BASE=Path(__file__).resolve().parent
FROZEN=json.loads((BASE/'FROZEN_COHORT.json').read_text())

def blobsha(data):
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()

def download(out):
    out.mkdir(exist_ok=True,parents=True)
    manifest=[]
    for s in FROZEN['sources']:
        assert re.fullmatch('[0-9a-f]{40}',s['commit'])
        assert re.fullmatch('[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',s['repo'])
        assert s['path'] and '..' not in s['path'].split('/')
        url='https://raw.githubusercontent.com/'+s['repo']+'/'+s['commit']+'/'+s['path']
        request=urllib.request.Request(url,headers={'User-Agent':'RISU-P4I-public-source-audit'})
        with urllib.request.urlopen(request,timeout=40) as r:
            assert r.status==200
            data=r.read(10_000_001)
        assert 0<len(data)<=10_000_000
        assert blobsha(data)==s['sha1'],('PIN_MISMATCH',s['id'],blobsha(data))
        name=s['id']+('.har' if s['type']=='har' else '.jsonl')
        (out/name).write_bytes(data)
        manifest.append({'id':s['id'],'repo':s['repo'],'commit':s['commit'],
            'path':s['path'],'origin_label':s['label'],'type':s['type'],
            'git_blob':blobsha(data),'sha256':hashlib.sha256(data).hexdigest(),
            'bytes':len(data),'internal_name':name})
    return manifest

def run(cli,thing):
    p=subprocess.run([cli,'analyze',str(thing),'--recovery','--format','json'],
       capture_output=True,text=True,timeout=22,
       env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
    counts=None
    if p.returncode in (0,1):
        try:
            j=json.loads(p.stdout);counts=j.get('summary')
        except Exception:
            counts='BAD_DIAGNOSTIC_JSON'
    # Never export raw stderr, HTTP response text, headers, URLs or tool arguments.
    return {'exit':p.returncode,'summary':counts,
            'error_text_hash':hashlib.sha256(p.stderr.encode()).hexdigest()}

def sample_2xx(hars,cache):
    for src in hars:
        if src['id']=='har_tap_sample':continue
        h=json.loads((cache/src['internal_name']).read_bytes())
        for idx,entry in enumerate(h.get('log',{}).get('entries',[])):
            try:
                req=entry['request'];res=entry['response'];ct=res['content']
                if req['method']!='GET' or not 200<=res['status']<300:continue
                if ct.get('encoding'):continue
                mime=ct['mimeType'].split(';')[0].strip().lower()
                if mime not in ('application/json','application/problem+json'):continue
                if not isinstance(ct.get('text'),str) or len(ct['text'])>1000000:continue
                if not isinstance(json.loads(ct['text']),dict):continue
                return src,idx,res['status']
            except (ValueError,KeyError,TypeError):continue
    return None

def evaluate(cache,sources,cli):
    har=[s for s in sources if s['type']=='har']
    mcp=[s for s in sources if s['type']=='mcp']
    assert len(har)==len(mcp)==5
    direct=[{'source':s['id'],**run(cli,cache/s['internal_name'])} for s in sources]
    pairs=[]
    with tempfile.TemporaryDirectory(prefix='risu-p4i-public-') as tmp:
        tmp=Path(tmp)
        for h in har:
            for m in mcp:
                folder=tmp/(h['id']+'__'+m['id']);folder.mkdir()
                (folder/'capture.har').symlink_to((cache/h['internal_name']).resolve())
                (folder/'mcp.jsonl').symlink_to((cache/m['internal_name']).resolve())
                # Intentionally no pairs.json. Causality MUST NOT be inferred.
                pairs.append({'har':h['id'],'mcp':m['id'],**run(cli,folder)})
        chosen=sample_2xx(har,cache)
        counter={'kind':'NO_SUITABLE_HTTP_JSON_GET'}
        if chosen:
            h,index,http_status=chosen
            m=next(x for x in mcp if x['id']=='tekeskernel_mcp')
            folder=tmp/'known_unrelated';folder.mkdir()
            shutil.copyfile(cache/h['internal_name'],folder/'capture.har')
            shutil.copyfile(cache/m['internal_name'],folder/'mcp.jsonl')
            (folder/'pairs.json').write_text(json.dumps({
                'schema':'risu-explicit-capture-pairing-v1',
                'pairs':[{'case_id':'SPLICED_EXTERNAL_SOURCES','target':'PROVEN_UNRELATED',
                          'http_entry':index,'mcp_call_id':7,'tool':'echo'}]}))
            observed=run(cli,folder)
            anyloss=isinstance(observed['summary'],dict) and any(
                observed['summary'].get(k,0)>0 for k in ('LOSS','LOSS_AND_INVENTED'))
            counter={'kind':'KNOWN_FALSE_CAUSAL_PAIR','har_source':h['id'],
                'mcp_source':m['id'],'http_status':http_status,
                'causal_pair_ground_truth':False,'pairing_manifest_authored_by_risu':True,
                'any_unsupported_loss_claim':anyloss,**observed}
    direct_reject=sum(x['exit']==2 for x in direct)
    unpaired_reject=sum(x['exit']==2 for x in pairs)
    stats={'public_original_files':len(sources),
        'distinct_external_publishers':len(set(x['repo'] for x in sources)),
        'raw_file_input_refusal':direct_reject,
        'raw_file_analysis_success':len(direct)-direct_reject,
        'unpaired_directories':len(pairs),
        'unpaired_input_refusal':unpaired_reject,
        'unpaired_analysis_success':len(pairs)-unpaired_reject,
        'authentic_independently_paired_http_to_mcp_captures':0,
        'ground_truthed_normal_true_negatives':0,
        'false_positive_rate':None,
        'false_positive_rate_is_measurable':False,
        'counterfactual_false_join_loss':counter.get('any_unsupported_loss_claim')}
    result={'schema':'risu-p4i-independent-public-corpus-v1','sources':sources,
         'tests':{'raw_files':direct,'unpaired_cross_repo':pairs,
                  'deliberate_invalid_join':counter},
         'metrics':stats,
         'interpretation':'Public independent sources are single-sided, NOT causally paired. Correct rejection is not success at diagnosing a real external HTTP-to-MCP conversion. No true-negative denominator; FPR undefined. Invalid join is only an adversarial provenance test, excluded from FPR.'}
    assert len(sources)==10 and len(pairs)==25
    assert direct_reject==10,('UNEXPECTED_ACCEPTANCE_RAW',direct)
    assert unpaired_reject==25,('UNEXPECTED_UNATTESTED_PAIRING',pairs)
    assert counter['kind']=='KNOWN_FALSE_CAUSAL_PAIR',counter
    assert stats['false_positive_rate'] is None
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--fetch',action='store_true')
    p.add_argument('--evaluate',action='store_true')
    p.add_argument('--cli',default='risu-probe')
    p.add_argument('--output',type=Path,default=Path('p4i/results'))
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    cache=args.output/'raw_public_sources_DO_NOT_UPLOAD'
    if args.fetch:
        inv=download(cache)
        (args.output/'source_manifest.json').write_text(json.dumps(inv,indent=2)+'\n')
        print('P4I_ORIGINAL_THIRD_PARTY_SOURCES_SHA_VERIFIED',len(inv),flush=True)
    if args.evaluate:
        sources=json.loads((args.output/'source_manifest.json').read_text())
        cli=shutil.which(args.cli) or args.cli
        report=evaluate(cache,sources,cli)
        (args.output/'field_trial.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
        print('P4I_STUDY',json.dumps(report['metrics'],sort_keys=True),flush=True)
        print('P4I_QUANTITATIVE_AUDIT_PASS_INPUT_REFUSALS_35',flush=True)

if __name__=='__main__':main()
