"""P4-K preregistered cohort: unchanged P4-J analysis against third-party exact raw files.

Fetcher is networked during setup only; all CLI invocations are local. No
source executes, no raw HTTP/MCP content, URLs, headers, tokens in outputs.
"""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parent
FROZEN=json.loads((ROOT/'FROZEN_COHORT.json').read_text())
assert FROZEN['schema']=='risu-p4k-public-developer-capture-metrics-prereg-v1'
SOURCES=FROZEN['sources']
assert len(SOURCES)==19
assert len({x['id'] for x in SOURCES})==19

def blobsha(data):
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\\0'+data).hexdigest()

def fetch_source(s,cache):
    assert re.fullmatch('[0-9a-f]{40}',s['commit'])
    assert re.fullmatch('[0-9a-f]{40}',s['sha1'])
    assert re.fullmatch('[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',s['repo'])
    assert not any(seg in ('.','..') for seg in s['path'].split('/'))
    url='https://raw.githubusercontent.com/'+s['repo']+'/'+s['commit']+'/'+urllib.parse.quote(s['path'],safe='/')
    request=urllib.request.Request(url,headers={'User-Agent':'RISU-P4K-independent-corpus-audit'})
    with urllib.request.urlopen(request,timeout=50) as r:
        assert r.status==200
        raw=r.read(10_000_001)
    assert 0<len(raw)<=10_000_000
    assert blobsha(raw)==s['sha1'],('SOURCE_HASH_MISMATCH',s['id'])
    name=s['id']+('.har' if s['type']=='har' else '.jsonl')
    (cache/name).write_bytes(raw)
    return {'id':s['id'],'repo':s['repo'],'commit':s['commit'],
            'path':s['path'],'type':s['type'],'origin_label':s['origin_label'],
            'git_blob':blobsha(raw),'sha256':hashlib.sha256(raw).hexdigest(),
            'bytes':len(raw),'file':name}

def fetch_all(cache,out):
    cache.mkdir(parents=True,exist_ok=True)
    results=[]
    for i,s in enumerate(SOURCES):
        results.append(fetch_source(s,cache))
        print('SOURCE_AUTHENTICATED',i+1,len(SOURCES),s['id'],flush=True)
    (out/'source_manifest.json').write_text(json.dumps(results,indent=2,sort_keys=True)+'\\n')
    return results

def invoke(cli,input_path,output_path,trust=None):
    command=[cli,'analyze',str(input_path),'--recovery','--format','json','--out',str(output_path)]
    if trust is not None:command.extend(['--causal-trust-store',str(trust)])
    try:
        r=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            timeout=30,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
    except subprocess.TimeoutExpired:
        return {'status':'TIMEOUT','exit':None,'legacy_loss':None,'confirmed_loss':None,
                'conditional_mismatch':None,'report_shape':'none'}
    report=None
    if output_path.is_file():
        try:
            report=json.loads(output_path.read_text())
        except (ValueError,UnicodeError):pass
        output_path.unlink(missing_ok=True)
    if r.returncode in (0,1) and isinstance(report,dict) and 'causal_gate_v1' in report:
        summary=report['causal_gate_v1']['summary']
        legacy=report['summary']
        return {'status':'ANALYZED','exit':r.returncode,
            'legacy_loss':sum(legacy.get(k,0) for k in ('LOSS','LOSS_AND_INVENTED')),
            'confirmed_loss':summary.get('CONFIRMED_LOSS',0),
            'conditional_mismatch':summary.get('CONDITIONAL_MISMATCH',0),
            'conditional_match':summary.get('CONDITIONAL_MATCH',0),
            'witnessed_no_loss':summary.get('WITNESSED_NO_LOSS_IN_OBSERVED_FIELDS',0),
            'report_shape':'proof_gated_v1','verdicts':[{'causal':x['causal_v1']['outcome'],
                'legacy':x['verdict']} for x in report.get('results',[])]}
    if r.returncode==2 and report is None:
        # Intentionally do not export stderr because upstream public HAR may contain sensitive fields.
        return {'status':'REJECTED','exit':2,'legacy_loss':None,'confirmed_loss':None,
                'conditional_mismatch':None,'report_shape':'none'}
    return {'status':'ERROR','exit':r.returncode,'legacy_loss':None,'confirmed_loss':None,
            'conditional_mismatch':None,'report_shape':'bad'}

def json_get_candidates(path):
    try:
        har=json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError,ValueError,UnicodeError):
        return []
    entries=har.get('log',{}).get('entries',[])
    if not isinstance(entries,list):return []
    good=[]
    for idx,e in enumerate(entries[:1000]):
        try:
            request=e['request'];response=e['response'];content=response['content']
            if request['method']!='GET' or response['status']!=200:continue
            if content.get('encoding') not in (None,''):continue
            if content.get('mimeType','').split(';')[0].strip().lower() not in ('application/json','application/problem+json'):continue
            if not isinstance(content.get('text'),str) or len(content['text'])>1000000:continue
            if not isinstance(json.loads(content['text']),dict):continue
            # Ensure P4-H parser header agreement when present.
            ct_headers=[h['value'].split(';')[0].strip().lower() for h in response.get('headers',[])
                        if isinstance(h,dict) and h.get('name','').lower()=='content-type']
            if len(ct_headers)>1 or ct_headers and ct_headers[0]!=content['mimeType'].split(';')[0].strip().lower():continue
            good.append(idx)
        except (TypeError,ValueError,KeyError,AttributeError):
            continue
    return good

def evaluate(cache,manifest,cli):
    if [x['id'] for x in manifest]!=[s['id'] for s in SOURCES]:
        raise ValueError('frozen inventory and recorded inventory disagree')
    hars=[x for x in manifest if x['type']=='har'];mcps=[x for x in manifest if x['type']=='mcp']
    assert len(hars)==9 and len(mcps)==10
    direct=[]
    for s in manifest:
        path=cache/s['file']
        with tempfile.TemporaryDirectory(prefix='p4k-direct-') as d:
            result=invoke(cli,path,Path(d)/'diagnostic.json')
        direct.append({'source':s['id'],**result})
    cross=[]
    # No symlinks: P4-I's symlink refusal would confound missing-pairs tests.
    with tempfile.TemporaryDirectory(prefix='p4k-cross-') as d:
        temp=Path(d)
        folder=temp/'input';folder.mkdir()
        for h,m in itertools.product(hars,mcps):
            shutil.copyfile(cache/h['file'],folder/'capture.har')
            shutil.copyfile(cache/m['file'],folder/'mcp.jsonl')
            (folder/'pairs.json').unlink(missing_ok=True)
            result=invoke(cli,folder,temp/'diagnostic.json')
            cross.append({'har':h['id'],'mcp':m['id'],**result})
        # Authored splice negative controls are NOT a field cohort or actual
        # HTTP-to-MCP conversion. Their falsity follows different projects.
        # Do not pass a key even if the operator's environment contains one.
        negative=[]
        preferred=[h for h in hars if h['id'] in
                   ('harvest_openmeteo','harvest_restcountries','harvest_hackernews')]
        ordered=preferred+[h for h in hars if h not in preferred]
        chosen_mcp=next(x for x in mcps if x['id']=='tekeskernel_mcp')
        count=0
        for h in ordered:
            candidates=json_get_candidates(cache/h['file'])
            if not candidates:continue
            idx=candidates[0]
            shutil.copyfile(cache/h['file'],folder/'capture.har')
            shutil.copyfile(cache/chosen_mcp['file'],folder/'mcp.jsonl')
            declaration={'schema':'risu-explicit-capture-pairing-v1',
               'pairs':[{'case_id':'KNOWN_UNRELATED_CROSS_PROJECT',
                         'target':'P4K_PROVEN_NONCAUSAL_NEGATIVE',
                         'http_entry':idx,'mcp_call_id':7,'tool':'echo'}]}
            (folder/'pairs.json').write_text(json.dumps(declaration)+'\\n')
            result=invoke(cli,folder,temp/'diagnostic.json')
            negative.append({'har':h['id'],'mcp':chosen_mcp['id'],
                 'ground_truth':'NO_HTTP_TO_MCP_CAUSAL_LINK_DIFFERENT_PROJECTS',
                 'manifest_authored_by_risu':True,**result})
            (folder/'pairs.json').unlink(missing_ok=True)
            count+=1
            if count==5:break
    direct_reject=sum(x['status']=='REJECTED' for x in direct)
    cross_reject=sum(x['status']=='REJECTED' for x in cross)
    field_accepted=[x for x in direct+cross if x['status']=='ANALYZED']
    counter_accepted=[x for x in negative if x['status']=='ANALYZED']
    counter_confirmed=sum(x['confirmed_loss'] or 0 for x in counter_accepted)
    internal_truth_pairs=0
    genuine_truth_negatives=0
    metrics={
        'external_files':len(manifest),
        'independent_repo_origins':len(set(x['repo'] for x in manifest)),
        'har_count':len(hars),'mcp_count':len(mcps),
        'direct_attempts':len(direct),'direct_rejections':direct_reject,
        'direct_analysis_success':sum(x['status']=='ANALYZED' for x in direct),
        'cross_unpaired_attempts':len(cross),'cross_unpaired_rejections':cross_reject,
        'cross_unpaired_analysis_success':sum(x['status']=='ANALYZED' for x in cross),
        'total_external_attempts':len(direct)+len(cross),
        'total_external_rejected':direct_reject+cross_reject,
        'total_external_analyzed':len(field_accepted),
        'external_rejection_rate':(direct_reject+cross_reject)/(len(direct)+len(cross)),
        'conditional_rate_given_external_analysis':(
           sum((x['conditional_mismatch'] or 0)+(x['conditional_match'] or 0) for x in field_accepted)/
           sum(len(x.get('verdicts',[])) for x in field_accepted)
           if sum(len(x.get('verdicts',[])) for x in field_accepted) else None),
        'confirmed_loss_external':sum(x['confirmed_loss'] or 0 for x in field_accepted),
        'independently_ground_truthed_external_pairs':internal_truth_pairs,
        'independent_external_true_negatives':genuine_truth_negatives,
        'field_false_positive_rate':None,
        'field_fpr_measurable':False,
        'known_unrelated_splice_attempts':len(negative),
        'known_unrelated_splice_analyzed':len(counter_accepted),
        'known_unrelated_splice_legacy_loss':sum(x['legacy_loss'] or 0 for x in counter_accepted),
        'known_unrelated_splice_confirmed_loss':counter_confirmed,
        'known_unrelated_splice_false_confirmation_rate':(
            counter_confirmed/len(counter_accepted) if counter_accepted else None)
    }
    if any(x['status'] not in ('REJECTED','ANALYZED') for x in direct+cross+negative):
        raise AssertionError('UNEXPECTED_CLI_ERROR_IN_CORPUS')
    assert len(direct)==19 and len(cross)==90
    assert direct_reject==19,('RAW_INPUT_UNEXPECTEDLY_ACCEPTED',direct)
    assert cross_reject==90,('UNPAIRED_INPUT_UNEXPECTEDLY_ACCEPTED',cross)
    assert not field_accepted
    assert len(negative)>0, 'no eligible third-party HTTP 200 JSON object to assess'
    assert counter_confirmed==0,('FALSE_CONFIRMED_LOSS_FOR_KNOWN_UNRELATED_RECORDS',negative)
    assert metrics['field_false_positive_rate'] is None
    return {'schema':'risu-p4k-independent-third-party-capture-metrics-v1',
       'frozen_protocol_sha256':hashlib.sha256((ROOT/'FROZEN_COHORT.json').read_bytes()).hexdigest(),
       'sources':manifest,'measurements':{'direct':direct,'unpaired_cross':cross,
            'provably_unrelated_adversarial':negative},
       'metrics':metrics,
       'limitations':[
         'No independently observed real third-party HTTP-to-MCP causal capture with adjudicated source/error truth in this cohort.',
         'Third-party public author-written fixtures are not necessarily production telemetry.',
         'Input refusal of unpaired single-sided evidence is a safe rejection, not a verified loss detector.',
         'Third-party HAR/MCP cross-splices are known false provenance tests, not true external conversions.',
         'Real-field false positive rate is undefined without ground-truthed true-negative pairs.',
         'A zero false-confirmation rate on designed negative controls cannot be generalized to field false-positive performance.'
       ]}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--fetch',action='store_true')
    parser.add_argument('--evaluate',action='store_true')
    parser.add_argument('--cache',type=Path,default=Path('p4k/results/private_raw_do_not_upload'))
    parser.add_argument('--out',type=Path,default=Path('p4k/results'))
    parser.add_argument('--cli',default='risu-probe')
    a=parser.parse_args()
    a.out.mkdir(exist_ok=True,parents=True)
    if a.fetch:
        fetch_all(a.cache,a.out)
    if a.evaluate:
        manifest=json.loads((a.out/'source_manifest.json').read_text())
        binary=shutil.which(a.cli) or a.cli
        report=evaluate(a.cache,manifest,binary)
        (a.out/'metrics.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\\n')
        print('P4K_EXTERNAL_COHORT_METRICS',json.dumps(report['metrics'],sort_keys=True),flush=True)

if __name__=='__main__':main()
