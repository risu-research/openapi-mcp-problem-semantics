"""Apply the sole v0.9 compatibility delta after authenticating original v0.8 bytes; retain virtualenv executable path.

CNOE FastMCP 3.4 speaks the legacy initialize era. The original v0.8
CNOE adapter used auto discover and failed before tools/list. Do not modify
the generic MCPClient or any target-generated CNOE source.
"""
from pathlib import Path
import hashlib
import json

base=Path('/opt/risu')
product=base/'product'/'risu_verify.py'
manifest=json.loads((base/'product-bundle'/'SOURCE_MANIFEST.json').read_text())
original=product.read_bytes()
assert hashlib.sha256(original).hexdigest()==manifest['modules_sha256']['risu_verify.py']
text=original.decode('utf-8')
pairs=[
    ("with MCPClient(cmd,protocol='auto',env=env) as client:",
     "with MCPClient(cmd,protocol='legacy',env=env) as client:"),
    ("server_cmd=cmd,protocol='auto')",
     "server_cmd=cmd,protocol='legacy')"),
    ("matrix=capture(plan['cases'],base,cmd,protocol='auto',recheck_source=True,",
     "matrix=capture(plan['cases'],base,cmd,protocol='legacy',recheck_source=True,"),
    ("interpreter=str(exe.resolve())",
     "interpreter=str(exe.absolute())"),
]
for old,new in pairs:
    assert text.count(old)==1, f'Unexpected original source for {old!r}'
    text=text.replace(old,new)
assert "protocol='auto'" not in text, 'CNOE fixture still uses auto negotiation'
patched=text.encode('utf-8')
product.write_bytes(patched)
ledger={
    'patch_name':'RISU Probe v0.9 CNOE legacy-initialize compatibility fix',
    'status':'AUTHENTICATED_BASE_PLUS_EXACT_THREE_REPLACEMENTS',
    'source_product':'RISU Probe v0.8 original authenticated module bundle',
    'changed_file':'risu_verify.py',
    'original_sha256':hashlib.sha256(original).hexdigest(),
    'patched_sha256':hashlib.sha256(patched).hexdigest(),
    'replacements':[{'before':old,'after':new} for old,new in pairs],
    'scope':'CNOE fixture adapter only; generic MCPClient untouched',
}
(base/'product-bundle'/'V09_PATCH_MANIFEST.json').write_text(
    json.dumps(ledger,indent=2)+'\n',encoding='utf-8')
print('v0.9 product patch applied with 4 exact source changes; SHA:',
      ledger['patched_sha256'])
