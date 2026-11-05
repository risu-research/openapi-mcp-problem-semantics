"""Restore original RISU v0.8 module bytes; refuse checksum mismatches."""
from pathlib import Path
import base64,hashlib,io,json,tarfile
base=Path('/opt/risu/product-bundle')
meta=json.loads((base/'SOURCE_MANIFEST.json').read_text())
parts=sorted(base.glob('part_*.b64'))
assert [p.name for p in parts]==[f'part_{i:02d}.b64' for i in range(6)]
raw=base64.b64decode(''.join(p.read_text().strip() for p in parts),validate=True)
assert hashlib.sha256(raw).hexdigest()==meta['module_tar_sha256']
out=Path('/opt/risu/product')
out.mkdir(parents=True,exist_ok=True)
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:xz') as tar:
    members=tar.getmembers()
    assert set(m.name for m in members)==set(meta['modules_sha256'])
    for m in members:
        assert m.isfile() and '/' not in m.name and '\\' not in m.name and m.size<100_000
        content=tar.extractfile(m).read()
        assert hashlib.sha256(content).hexdigest()==meta['modules_sha256'][m.name],m.name
        (out/m.name).write_bytes(content)
print('Exact v0.8 modules authenticated:',len(members))
