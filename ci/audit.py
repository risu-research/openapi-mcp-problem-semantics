"""Fail-closed independent audit; does not run CNOE or product code."""
import base64,hashlib,io,json,sys,tarfile,zipfile
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
# Independent exact-delta audit. Rebuild the original authenticated v0.8
# module from the checked-out upload and require exactly three replacements.
patch=load('V09_PATCH_MANIFEST.json')
assert patch['changed_file']=='risu_verify.py'
assert patch['status']=='AUTHENTICATED_BASE_PLUS_EXACT_FOUR_REPLACEMENTS'
assert patch['original_sha256']==meta['modules_sha256']['risu_verify.py']
assert len(patch['replacements'])==4
pieces=[(root.parent/'product'/f'part_{i:02d}.b64').read_text().strip() for i in range(6)]
tar_bytes=base64.b64decode(''.join(pieces),validate=True)
assert hashlib.sha256(tar_bytes).hexdigest()==meta['module_tar_sha256']
with tarfile.open(fileobj=io.BytesIO(tar_bytes),mode='r:xz') as tar:
    original=tar.extractfile('risu_verify.py').read()
assert hashlib.sha256(original).hexdigest()==patch['original_sha256']
expected=original.decode('utf-8')
for change in patch['replacements']:
    assert expected.count(change['before'])==1
    expected=expected.replace(change['before'],change['after'])
    if "protocol='auto'" in change['before']:
        assert change['before'].count("protocol='auto'")==1
        assert change['after'].count("protocol='legacy'")==1
    else:
        assert change['before']=='interpreter=str(exe.resolve())'
        assert change['after']=='interpreter=str(exe.absolute())'
assert hashlib.sha256(expected.encode('utf-8')).hexdigest()==patch['patched_sha256']==status['protocol_fix_sha256']
integrated=load('V09_INTEGRATION_MANIFEST.json')
assert integrated['status']=='AUTHENTICATED_INTEGRATED_V09'
assert integrated['product_version']==status['integrated_product_version']=='0.9.0-experimental'
assert set(integrated['source_files'])=={'risu_probe.py','risu_verify.py'}
verify_before=expected
for change in integrated['source_files']['risu_verify.py']['additional_edits']:
    assert verify_before.count(change['before'])==1
    verify_before=verify_before.replace(change['before'],change['after'])
verify_source=(root/'V09_INTEGRATED_RISU_VERIFY.py').read_bytes()
assert verify_source==verify_before.encode('utf-8'), 'unexpected extra edit to integrated verifier'
assert hashlib.sha256(verify_source).hexdigest()==integrated['source_files']['risu_verify.py']['sha256']=='4bdbae7da26ea308333f45d668176a65cfacb890f9bc30e0ca4a9ca583f612b0'
with tarfile.open(fileobj=io.BytesIO(tar_bytes),mode='r:xz') as original_tar:
    original_probe=original_tar.extractfile('risu_probe.py').read()
assert hashlib.sha256(original_probe).hexdigest()==meta['modules_sha256']['risu_probe.py']
probe_before=original_probe.decode('utf-8')
for change in integrated['source_files']['risu_probe.py']['additional_edits']:
    assert probe_before.count(change['before'])==1
    probe_before=probe_before.replace(change['before'],change['after'])
probe_source=(root/'V09_INTEGRATED_RISU_PROBE.py').read_bytes()
assert probe_source==probe_before.encode('utf-8'), 'unexpected extra edit to integrated engine'
assert hashlib.sha256(probe_source).hexdigest()==integrated['source_files']['risu_probe.py']['sha256']=='d2a9af2b19a17d33925d64f2ced8b0e52442577fcecba020bdcccd360bb070f1'
assert status['integrated_source_sha256']=={n:v['sha256'] for n,v in integrated['source_files'].items()}
assert result['probe_version']=='0.9.0-experimental'

# v0.9 cross-server transport regression is from the same authenticated
# product engine, with modern targets installed in their own pinned venv.
transport=load('MULTI_SERVER_TRANSPORT.json')
assert transport['status']=='PASS'
assert transport['product_version']=='0.9.0-experimental'
assert transport['pinned_versions']=={'mcp':'2.3.0','fastmcp':'4.1.6','fastmcp-slim':'4.1.6'}
assert transport['cases_passed']==6 and transport['targets']==3
assert transport['virtualenv_symlink_preserved'] is True
assert transport['explicit_modern_to_legacy_rejected'] is True
cases=transport['cases']
assert len(cases)==6
assert {r['target'] for r in cases}=={'official-sdk2','fastmcp-4.1.6','stdlib-legacy'}
for row in cases:
    assert row['result']=='PRESERVED' and row['tool']=='echo'
    assert row['requested_mode'] in ('modern','auto','legacy')
    assert row['negotiated_mode']==('legacy' if row['target']=='stdlib-legacy' else 'modern')
    assert row['synthetic_value'].startswith('RISU_SYNTHETIC_ECHO_')
assert (root/'MULTI_SERVER_RUN_LOG.txt').is_file()

assert (root/'GENERATOR_LOG.txt').is_file() and (root/'PRODUCT_EXECUTION_LOG.txt').is_file()
finding={'verdict':'PASS','product':'RISU Probe v0.9 fully integrated source (exact authenticated build)',
         'generator_commit':status['actual_cnoe_generator_commit'],
         'source_wheel_sha256':meta['source_wheel_sha256'],
         'patched_adapter_sha256':patch['patched_sha256'],'patches':4,
         'integrated_source_sha256':status['integrated_source_sha256'],'metadata_updates':4,
         'server_implementations_tested':['CNOE/FastMCP3.4','official MCP SDK2.3','FastMCP4.1.6','stdlib legacy'],
         'transport_cases_passed':6,
         'case_count':len(checks),'error_losses':3,
         'generated_files_hashed':len(ledger),'module_files_hashed':len(meta['modules_sha256']),
         'limitations':'Synthetic localhost; not exact line coverage; container isolation not a kernel sandbox proof'}
(root/'AUDIT.json').write_text(json.dumps(finding,indent=2)+'\n')
print(json.dumps(finding,indent=2))
