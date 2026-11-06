"""Independent P4-I public origin field trial auditor; no RISU imports, no network."""
import argparse,copy,hashlib,json
from pathlib import Path
def audit(frozen,trial):
 p=frozen['sources']; s=trial['sources']; t=trial['tests']; m=trial['metrics']
 assert frozen['schema']=='risu-p4i-preregistered-independent-third-party-capture-study-v1'
 assert trial['schema']=='risu-p4i-independent-public-corpus-v1'
 assert len(p)==len(s)==10 and len({x['id'] for x in s})==10
 for a,b in zip(s,p):
  assert all(a[k]==b[k] for k in ('id','repo','commit','type','path'))
  assert a['git_blob']==b['sha1'] and a['origin_label']==b['label']
  assert len(a['sha256'])==64 and a['bytes']>0
 assert len({x['repo'] for x in s})==7
 h={x['id'] for x in s if x['type']=='har'}
 w={x['id'] for x in s if x['type']=='mcp'}
 assert len(h)==len(w)==5
 d=t['raw_files'];g=t['unpaired_cross_repo'];a=t['deliberate_invalid_join']
 assert len(d)==10 and {x['source'] for x in d}=={x['id'] for x in s}
 assert all(x['exit']==2 and x['summary'] is None for x in d)
 assert len(g)==25 and {(x['har'],x['mcp']) for x in g}=={(i,j) for i in h for j in w}
 assert all(x['exit']==2 and x['summary'] is None for x in g)
 assert m['public_original_files']==10 and m['distinct_external_publishers']==7
 assert m['raw_file_input_refusal']==10 and m['raw_file_analysis_success']==0
 assert m['unpaired_directories']==25 and m['unpaired_input_refusal']==25
 assert m['unpaired_analysis_success']==0
 assert m['authentic_independently_paired_http_to_mcp_captures']==0
 assert m['ground_truthed_normal_true_negatives']==0
 assert m['false_positive_rate'] is None and m['false_positive_rate_is_measurable'] is False
 assert a['kind']=='KNOWN_FALSE_CAUSAL_PAIR' and a['causal_pair_ground_truth'] is False
 assert a['pairing_manifest_authored_by_risu'] is True
 assert a['har_source'] in h and a['mcp_source'] in w
 ids={x['id']:x['repo'] for x in s}
 assert ids[a['har_source']]!=ids[a['mcp_source']]
 assert a['http_status']==200 and a['exit']==0
 assert a['summary']['LOSS']==1 and sum(a['summary'].values())==1
 assert a['any_unsupported_loss_claim'] is True and m['counterfactual_false_join_loss'] is True
 assert 'Authorization' not in json.dumps(trial)
 assert 'raw_http_body_utf8' not in json.dumps(trial)
 return {'status':'PASS_MEASUREMENT_NOT_REAL_WORLD_ACCURACY','sources':10,'publishers':7,
 'correct_incomplete_refusals':35,'counterfactual_invalid_join_accepted':True,
 'counterfactual_unsupported_loss':True,'actual_fpr':None,
 'report_sha256':hashlib.sha256(json.dumps(trial,sort_keys=True).encode()).hexdigest()}
def mutations(frozen,trial):
 cases={
 'alter_raw_rejection':lambda x:x['tests']['raw_files'][0].update(exit=0),
 'alter_unpaired_rejection':lambda x:x['tests']['unpaired_cross_repo'][0].update(exit=0),
 'forge_fpr':lambda x:x['metrics'].update(false_positive_rate=0.0),
 'forge_real_causal_pair':lambda x:x['metrics'].update(authentic_independently_paired_http_to_mcp_captures=1),
 'alter_repo':lambda x:x['sources'][0].update(repo='FAKE/repo'),
 'alter_source_sha':lambda x:x['sources'][1].update(git_blob='0'*40),
 'forge_join':lambda x:x['tests']['deliberate_invalid_join'].update(causal_pair_ground_truth=True),
 'hide_false_loss':lambda x:x['tests']['deliberate_invalid_join']['summary'].update(LOSS=0),
 'change_cartesian':lambda x:x['tests']['unpaired_cross_repo'][1].update(har='incorrect')}
 out=[]
 for name,f in cases.items():
  forged=copy.deepcopy(trial);f(forged)
  try:audit(frozen,forged)
  except (AssertionError,KeyError,ValueError,TypeError):out.append(name)
  else:raise RuntimeError('FAIL_NOT_CAUGHT:'+name)
 assert len(out)==len(cases)
 return out
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('frozen',type=Path);a.add_argument('trial',type=Path);a.add_argument('out',type=Path);v=a.parse_args()
 f=json.loads(v.frozen.read_text());t=json.loads(v.trial.read_text())
 r=audit(f,t);r['mutations_detected']=mutations(f,t)
 v.out.parent.mkdir(parents=True,exist_ok=True)
 v.out.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
 print('P4I_OFFLINE_INDEPENDENT_AUDIT_PASS_MUTATIONS',len(r['mutations_detected']))
