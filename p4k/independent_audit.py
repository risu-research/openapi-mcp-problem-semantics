"""Independent P4-K audit. Does not import the RISU Probe comparator or bridge."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
FROZEN=json.loads((ROOT/'FROZEN_COHORT.json').read_text())

def git_blob(data):
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()

def assert_report(r,manifest,cache,controls=None,check_files=True):
    assert r['schema']=='risu-p4k-independent-third-party-capture-metrics-v1'
    assert r['frozen_protocol_sha256']==hashlib.sha256((ROOT/'FROZEN_COHORT.json').read_bytes()).hexdigest()
    m=r['metrics'];tests=r['measurements']
    direct=tests['direct'];cross=tests['unpaired_cross'];negative=tests['provably_unrelated_adversarial']
    sources=FROZEN['sources']
    assert len(sources)==len(manifest)==19
    assert [s['id'] for s in sources]==[x['id'] for x in manifest]==[x['id'] for x in r['sources']]
    assert r['sources']==manifest, 'report source metadata was changed independently of authenticated manifest'
    assert len(set(x['id'] for x in manifest))==19
    assert len(set(x['repo'] for x in manifest))==14
    if check_files:
        for pin,observed in zip(sources,manifest):
            raw=(cache/observed['file']).read_bytes()
            assert len(raw)==observed['bytes']
            assert hashlib.sha256(raw).hexdigest()==observed['sha256']
            assert git_blob(raw)==observed['git_blob']==pin['sha1']
            assert observed['commit']==pin['commit'] and observed['path']==pin['path']
            assert observed['repo']==pin['repo'] and observed['type']==pin['type']
    hs=[x['id'] for x in manifest if x['type']=='har']
    ms=[x['id'] for x in manifest if x['type']=='mcp']
    assert len(hs)==9 and len(ms)==10
    assert len(direct)==19 and len(cross)==90
    assert [x['source'] for x in direct]==[x['id'] for x in manifest]
    assert len({(x['har'],x['mcp']) for x in cross})==90
    assert {(x['har'],x['mcp']) for x in cross}=={(h,m) for h in hs for m in ms}
    for record in direct+cross:
        assert record['status']=='REJECTED' and record['exit']==2
        assert record['confirmed_loss'] is None and record['legacy_loss'] is None
        assert record['report_shape']=='none'
    assert 1<=len(negative)<=5
    for n in negative:
        assert n['har'] in hs and n['mcp']=='tekeskernel_mcp'
        assert n['ground_truth']=='NO_HTTP_TO_MCP_CAUSAL_LINK_DIFFERENT_PROJECTS'
        assert n['manifest_authored_by_risu'] is True
        assert n['status'] in ('REJECTED','ANALYZED')
        if n['status']=='ANALYZED':
            assert n['exit']==0
            assert n['report_shape']=='proof_gated_v1'
            assert n['confirmed_loss']==0
            assert all(v['causal']!='CONFIRMED_LOSS' for v in n['verdicts'])
            assert all(v['causal'] in ('CONDITIONAL_MISMATCH','CONDITIONAL_MATCH','INSUFFICIENT_EVIDENCE') for v in n['verdicts'])
        else:
            assert n['exit']==2
    assert m['external_files']==19
    assert m['independent_repo_origins']==14
    assert m['har_count']==9 and m['mcp_count']==10
    assert m['direct_attempts']==19 and m['direct_rejections']==19 and m['direct_analysis_success']==0
    assert m['cross_unpaired_attempts']==90 and m['cross_unpaired_rejections']==90 and m['cross_unpaired_analysis_success']==0
    assert m['total_external_attempts']==109
    assert m['total_external_rejected']==109 and m['total_external_analyzed']==0
    assert m['external_rejection_rate']==1.0
    assert m['conditional_rate_given_external_analysis'] is None
    assert m['confirmed_loss_external']==0
    assert m['independently_ground_truthed_external_pairs']==0
    assert m['independent_external_true_negatives']==0
    assert m['field_false_positive_rate'] is None
    assert m['field_fpr_measurable'] is False
    assert m['known_unrelated_splice_attempts']==len(negative)
    accepted=[x for x in negative if x['status']=='ANALYZED']
    assert m['known_unrelated_splice_analyzed']==len(accepted)
    assert m['known_unrelated_splice_legacy_loss']==sum(x['legacy_loss'] or 0 for x in accepted)
    assert m['known_unrelated_splice_confirmed_loss']==0
    assert m['known_unrelated_splice_false_confirmation_rate']==(0.0 if accepted else None)
    if controls is not None:
        assert controls['positive']['causal_gate_v1']['summary']['CONFIRMED_LOSS']==1
        assert controls['positive']['causal_gate_v1']['summary']['WITNESSED_NO_LOSS_IN_OBSERVED_FIELDS']==1
        assert controls['untrusted']['causal_gate_v1']['summary']['CONFIRMED_LOSS']==0
        assert controls['untrusted']['causal_gate_v1']['summary']['CONDITIONAL_MISMATCH']==1
    return {'audit':'PASS','public_files_sha_authenticated':len(manifest),
       'repo_origins':m['independent_repo_origins'],
       'raw_rejections':m['direct_rejections'],
       'unpaired_rejections':m['cross_unpaired_rejections'],
       'negative_control_trials':len(negative),
       'accepted_negative_control_trials':len(accepted),
       'false_confirmed_loss_on_splices':0,
       'independent_field_fpr':None,
       'independent_field_fpr_reason':'NO_GROUND_TRUTHED_PAIRED_THIRD_PARTY_TRUE_NEGATIVES',
       'internal_positive_control':'PASS' if controls is not None else 'NOT_RUN'}

def mutation_tests(report,manifest,cache,controls):
    changes={
      'fake_external_confirmed':lambda x:x['metrics'].update(confirmed_loss_external=1),
      'invent_field_fpr':lambda x:x['metrics'].update(field_false_positive_rate=0),
      'invent_true_negative':lambda x:x['metrics'].update(independent_external_true_negatives=1),
      'erase_direct_rejection':lambda x:x['measurements']['direct'][0].update(status='ANALYZED'),
      'unpaired_hidden_success':lambda x:x['measurements']['unpaired_cross'][1].update(exit=0),
      'duplicate_cross_pair':lambda x:x['measurements']['unpaired_cross'][1].update(har=x['measurements']['unpaired_cross'][0]['har'],mcp=x['measurements']['unpaired_cross'][0]['mcp']),
      'fake_causal_splice':lambda x:x['measurements']['provably_unrelated_adversarial'][0].update(confirmed_loss=1,status='ANALYZED',exit=0,report_shape='proof_gated_v1'),
      'fake_source_repo':lambda x:x['sources'][0].update(repo='falsified/repo')
    }
    caught=[]
    for name,edit in changes.items():
        fake=copy.deepcopy(report)
        edit(fake)
        try:assert_report(fake,manifest,cache,controls,check_files=False)
        except (AssertionError,KeyError,ValueError,TypeError):caught.append(name)
        else:raise AssertionError('AUDIT_FAILED_TO_CATCH_MUTATION:'+name)
    assert len(caught)==len(changes)
    return caught

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--results',type=Path,default=Path('p4k/results'))
    p.add_argument('--cache',type=Path,default=Path('p4k/results/private_raw_do_not_upload'))
    a=p.parse_args()
    report=json.loads((a.results/'metrics.json').read_text())
    manifest=json.loads((a.results/'source_manifest.json').read_text())
    controls={'positive':json.loads((a.results/'positive_control.json').read_text()),
              'untrusted':json.loads((a.results/'untrusted_control.json').read_text())}
    audited=assert_report(report,manifest,a.cache,controls)
    audited['detected_adversarial_mutations']=mutation_tests(report,manifest,a.cache,controls)
    (a.results/'independent_audit.json').write_text(json.dumps(audited,sort_keys=True,indent=2)+'\n')
    print('P4K_INDEPENDENT_AUDIT_PASS',json.dumps(audited,sort_keys=True),flush=True)

if __name__=='__main__':main()
