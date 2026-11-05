"""Offline preflight before building third-party code."""
import base64,hashlib,io,json,tarfile
from pathlib import Path
b=Path('product')
meta=json.loads((b/'SOURCE_MANIFEST.json').read_text())
parts=sorted(b.glob('part_*.b64'))
assert [p.name for p in parts]==[f'part_{i:02d}.b64' for i in range(6)],'missing source parts'
archive=base64.b64decode(''.join(p.read_text().strip() for p in parts),validate=True)
assert hashlib.sha256(archive).hexdigest()==meta['module_tar_sha256']
with tarfile.open(fileobj=io.BytesIO(archive),mode='r:xz') as t:
    assert set(x.name for x in t.getmembers())==set(meta['modules_sha256'])
    for x in t.getmembers():
        assert x.isfile() and '/' not in x.name and x.size<100000
        assert hashlib.sha256(t.extractfile(x).read()).hexdigest()==meta['modules_sha256'][x.name]
print('PREFLIGHT PASS: exact original v0.8 module bytes authenticated',len(meta['modules_sha256']))
