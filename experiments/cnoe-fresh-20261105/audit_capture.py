#!/usr/bin/env python3
"""Fail-closed independent audit of fresh CNOE capture, synthetic fixture only."""
import hashlib,json,os,zipfile
from pathlib import Path

out=Path(os.environ['RISU_CNOE_OUTPUT'])
p=json.loads((out/'cnoe-current-matrix.json').read_text(encoding='utf-8'))
assert p['status']=='EXECUTED'
head=(out/'CNOE_HEAD.txt').read_text().strip() if (out/'CNOE_HEAD.txt').exists() else None
if head is not None:assert p['generator_commit']==head
assert p['generator']=='cnoe-io/openapi-mcp-codegen'
assert set(p['api_request_counts'])=={'normal','conflict','validation','generic'}
assert all(n==3 for n in p['api_request_counts'].values())
target=p['targets'][0]
rows=target['checks']
assert [x['check']['id'] for x in rows]==['normal','conflict','validation','generic']
def sha(obj):
    s=json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'))
    return hashlib.sha256(s.encode('utf-8')).hexdigest()
stats={}
for r in rows:
    name=r['check']['id']
    orig=r['source_sample'];mcp=r['mcp_sample']
    assert sha(orig)==r['source_sha256'],name+' source hash'
    assert sha(mcp)==r['mcp_sha256'],name+' MCP hash'
    assert r['check']['mediated_http_requests']==1,name+' no actual MCP->HTTP call'
    expected={'normal':200,'conflict':409,'validation':422,'generic':400}[name]
    assert orig['status']==expected
    assert mcp.get('resultType') in ('complete',None)
    if name=='normal':
        assert mcp.get('isError') is False
        assert mcp.get('structuredContent')==orig['body']
    else:
        assert mcp.get('isError') is False
        assert mcp.get('structuredContent')!=orig['body']
    if name=='validation':
        assert len(orig['body']['errors'])==30
        assert orig['body']['critical_tail']=='RISU_CURRENT_CODEGEN_TAIL_7c6ab16f'
    stats[name]={'status':expected,'isError':mcp.get('isError'),'machine_exact':mcp.get('structuredContent')==orig['body']}
ledger=json.loads((out/'GENERATED_SHA256.json').read_text())
with zipfile.ZipFile(out/'generated-code.zip') as z:
    assert set(z.namelist())==set(ledger), 'generated sources missing'
    for name, digest in ledger.items():
        assert hashlib.sha256(z.read(name)).hexdigest()==digest, 'generated source hash mismatch '+name
print(json.dumps({'verdict':'PASS','cases':stats,'generator_commit':p['generator_commit'],
                  'generated_files_hashed':len(ledger),'api_request_counts':p['api_request_counts']},indent=2))
