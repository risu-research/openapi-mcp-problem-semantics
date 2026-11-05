"""Promote authenticated v0.8+four-fix engine to the exact integrated v0.9 source.

Run after unpack_product.py and apply_protocol_fix.py, at Docker build time.
Every code edit is exact-match and the resulting source SHA-256 is fixed.
"""
from pathlib import Path
import hashlib,json

base=Path('/opt/risu')
source=base/'product'
bundle=base/'product-bundle'
base_meta=json.loads((bundle/'SOURCE_MANIFEST.json').read_text())
fix=json.loads((bundle/'V09_PATCH_MANIFEST.json').read_text())
assert fix['status']=='AUTHENTICATED_BASE_PLUS_EXACT_FOUR_REPLACEMENTS'
changes={
 'risu_probe.py':[
  ("VERSION = '0.8.0-experimental'","VERSION = '0.9.0-experimental'")
 ],
 'risu_verify.py':[
  ("from risu_probe import MCPClient\n","from risu_probe import MCPClient, VERSION\n"),
  ("label='v08-cnoe-fixture'","label='v09-cnoe-fixture'"),
  ("'probe_version':'0.8.0-experimental'","'probe_version':VERSION")
 ],
}
expected={'risu_probe.py':'d2a9af2b19a17d33925d64f2ced8b0e52442577fcecba020bdcccd360bb070f1',
          'risu_verify.py':'4bdbae7da26ea308333f45d668176a65cfacb890f9bc30e0ca4a9ca583f612b0'}
ledger={'status':'AUTHENTICATED_INTEGRATED_V09','product_version':'0.9.0-experimental',
        'base_wheel_sha256':base_meta['source_wheel_sha256'],
        'original_four_fix_sha256':fix['patched_sha256'],'source_files':{}}
for name,pairs in changes.items():
    p=source/name
    prior=p.read_bytes()
    base_digest=fix['patched_sha256'] if name=='risu_verify.py' else base_meta['modules_sha256'][name]
    assert hashlib.sha256(prior).hexdigest()==base_digest,name
    code=prior.decode('utf-8')
    for old,new in pairs:
        assert code.count(old)==1,(name,old)
        code=code.replace(old,new)
    raw=code.encode('utf-8')
    digest=hashlib.sha256(raw).hexdigest()
    assert digest==expected[name],(name,digest)
    p.write_bytes(raw)
    ledger['source_files'][name]={'starting_sha256':base_digest,'sha256':digest,
        'additional_edits':[{'before':old,'after':new} for old,new in pairs]}
(bundle/'V09_INTEGRATION_MANIFEST.json').write_text(json.dumps(ledger,indent=2)+'\n',encoding='utf-8')
print('Exact integrated v0.9 source verified:',expected)
