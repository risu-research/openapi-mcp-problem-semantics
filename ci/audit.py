"""Fail-closed independent audit; does not run CNOE or product code."""
import hashlib,json,sys,zipfile
from pathlib import Path

root=Path(sys.argv[1] if len(sys.argv)>1 else 'results')
def load(name):return json.loads((root/name).read_text(encoding='utf-8'))
meta=load('SOURCE_MANIFEST.json')
result=load('V08_PRODUCT_VERIFICATION.json')
status=load('EXECUTION_STATUS.json')
static=load('STATIC_SCAN.json')
preview=load('PREVIEW.json')
assert status['status']=='PASS'
assert status['source_wheel_sha256']==meta['source_wheel_sha256']=='e9ebe383ff6453951150ad4050f401d3e207ac9d8a1df88dcbde1d05149c6b71'
assert status['actual_cnoe_generator_commit']=='8c2b065497cf32ecbb7cf7e28dad3a99c6706c3f'
assert (root/'CNOE_HEAD.txt').read_text().strip()==status['actual_cnoe_generator_commit']
assert preview['status']=='UNVERIFIED' and preview['execution']=='NONE'
assert result['status']=='CORROBORATED_BEHAVIOR' and result['execution']=='REAL_LOCALHOST_HTTP_AND_MCP'
assert result['counts']=={'planned':4,'captured':4,'fixture_gets':12,'unexpected_requests':0,'error_losses':3}
assert result['positive_control']=='PRESERVED'
assert result['static_links'][0]['rule_id']=='RPY101'
assert result['static_links'][0]['verdict']=='BEHAVIORALLY_CORROBORATED'
assert any(f['rule_id']=='RPY101' for f in static['findings'])
assert {row['http_status']:row['verdict'] for row in result['evaluations']}=={
    200:'PRESERVED',400:'LOSS',409:'LOSS',422:'LOSS'}
matrix=result['matrix']
assert matrix['status']=='EXECUTED' and matrix['captured_cases']==4 and not matrix['failures']
checks=matrix['targets'][0]['checks']
assert len(checks)==4
def sha(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False,
                                     separators=(',',':')).encode('utf-8')).hexdigest()
for check in checks:
    assert check['check']['tool']=='get_order'
    assert check['check']['source_method']=='GET'
    assert check['source_sha256']==sha(check['source_sample'])
    assert check['mcp_sha256']==sha(check['mcp_sample'])
assert {x['source_sample']['status'] for x in checks}=={200,400,409,422}
ledger=load('GENERATED_SHA256.json')
with zipfile.ZipFile(root/'GENERATED_CNOE_SOURCES.zip') as z:
    assert {n for n in z.namelist() if not n.endswith('/')}==set(ledger)
    for name,digest in ledger.items():
        assert hashlib.sha256(z.read(name)).hexdigest()==digest,name
assert (root/'GENERATOR_LOG.txt').is_file() and (root/'PRODUCT_EXECUTION_LOG.txt').is_file()
finding={'verdict':'PASS','product':'RISU Probe original v0.8 modules',
         'generator_commit':status['actual_cnoe_generator_commit'],
         'source_wheel_sha256':meta['source_wheel_sha256'],
         'case_count':len(checks),'error_losses':3,
         'generated_files_hashed':len(ledger),'module_files_hashed':len(meta['modules_sha256']),
         'limitations':'Synthetic localhost; not exact line coverage; container isolation not a kernel sandbox proof'}
(root/'AUDIT.json').write_text(json.dumps(finding,indent=2)+'\n')
print(json.dumps(finding,indent=2))
