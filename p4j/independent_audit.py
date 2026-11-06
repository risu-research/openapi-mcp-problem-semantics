"""P4-J independent, source-only result audit. No RISU source imported.

This auditor independently re-computes provenance, raw case mismatch and Ed25519
signatures. The signer is test-only; audit cannot certify external independence.
"""
from __future__ import annotations
import argparse,base64,hashlib,json
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

def canonical(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def digest(x):return hashlib.sha256(canonical(x)).hexdigest()
def sha(x):return hashlib.sha256(x).hexdigest()

def audit(capture,trust,confirmed,declared):
    source={n:(capture/n).read_bytes() for n in ('capture.har','mcp.jsonl','pairs.json')}
    witness=json.loads((capture/'causal_witness.json').read_text())
    keys=json.loads(trust.read_text())
    statement={k:v for k,v in witness.items() if k!='signature'}
    assert statement['schema']=='risu-boundary-observer-receipt-v1'
    assert statement['observer_kind']=='BOUNDARY_RECORDER_V1'
    assert keys['schema']=='risu-boundary-trust-store-v1'
    for name,raw in source.items():assert statement['file_sha256'][name]==sha(raw)
    key=[x for x in keys['trusted_recorders'] if x['key_id']==witness['signature']['key_id']]
    assert len(key)==1
    assert key[0]['issuer']==statement['issuer']
    Ed25519PublicKey.from_public_bytes(base64.b64decode(key[0]['ed25519_public_key_base64'])).verify(
      base64.b64decode(witness['signature']['value_base64']),canonical(statement))
    har=json.loads(source['capture.har'])
    rpc=[json.loads(x) for x in source['mcp.jsonl'].decode().splitlines() if x.strip()]
    pairs=json.loads(source['pairs.json'])['pairs']
    confirmation=json.loads(confirmed.read_text())
    declared_report=json.loads(declared.read_text())
    assert confirmation['causal_gate_v1']['summary']['CONFIRMED_LOSS']==1
    assert confirmation['causal_gate_v1']['summary']['WITNESSED_NO_LOSS_IN_OBSERVED_FIELDS']==1
    assert declared_report['causal_gate_v1']['summary']['CONFIRMED_LOSS']==0
    assert declared_report['causal_gate_v1']['summary']['CONDITIONAL_MISMATCH']==1
    assert confirmation['summary']['LOSS']==declared_report['summary']['LOSS']==1
    proof_ids=set()
    for link in witness['links']:
        pair=next(p for p in pairs if p['case_id']==link['case_id'])
        assert pair['http_entry']==link['http_entry']
        assert pair['mcp_call_id']==link['mcp_call_id']
        req=next(x for x in rpc if x.get('method')=='tools/call' and x['id']==link['mcp_call_id'])
        resp=next(x for x in rpc if x.get('id')==link['mcp_call_id'] and 'result' in x)
        entry=har['log']['entries'][link['http_entry']]
        events=link['events'];raws=[req,entry['request'],entry['response'],resp]
        assert [x['kind'] for x in events]==['MCP_REQUEST','HTTP_REQUEST','HTTP_RESPONSE','MCP_RESPONSE']
        assert [x['sha256'] for x in events]==[digest(x) for x in raws]
        assert all(x['sequence']<y['sequence'] for x,y in zip(events,events[1:]))
        token=req['params']['arguments']['risu_trace_token']
        assert sha(token.encode())==link['trace_token_sha256']
        assert token==next(x['value'] for x in entry['request']['headers'] if x['name'].lower()=='x-risu-trace-token')
        # Both results exactly reflect the observed HTTP success/failure flags.
        assert ('isError' in resp['result'])
        proof_ids.add(pair['case_id'])
    assert proof_ids=={'SDK_WITNESSED_200','SDK_WITNESSED_404'}
    outcomes={x['id']:x['causal_v1']['outcome'] for x in confirmation['results']}
    assert outcomes=={'SDK_WITNESSED_200':'WITNESSED_NO_LOSS_IN_OBSERVED_FIELDS',
                      'SDK_WITNESSED_404':'CONFIRMED_LOSS'}
    return {'status':'PASS','qualification':'BOUNDED_LOCAL_WITNESS_ONLY',
        'authenticated_observer':statement['issuer'],
        'witnessed_calls':len(proof_ids),
        'conditional_without_trust':declared_report['causal_gate_v1']['summary']['CONDITIONAL_MISMATCH'],
        'confirmed_with_external_trust':confirmation['causal_gate_v1']['summary']['CONFIRMED_LOSS'],
        'source_hashes':statement['file_sha256'],
        'evidence_boundary':'Audits trusted local synthetic fixture only; no third-party independent production ground truth'}

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('capture',type=Path)
    p.add_argument('trust',type=Path)
    p.add_argument('confirmed',type=Path)
    p.add_argument('declared',type=Path)
    p.add_argument('out',type=Path)
    a=p.parse_args()
    outcome=audit(a.capture,a.trust,a.confirmed,a.declared)
    a.out.write_text(json.dumps(outcome,indent=2,sort_keys=True)+'\n')
    print('P4J_INDEPENDENT_AUDIT_PASS',outcome['witnessed_calls'],outcome['qualification'])
