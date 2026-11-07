"""Restore P5-C reviewed source from exact-hash bounded tar/zlib/base64 bundle."""
from __future__ import annotations
import base64,hashlib,io
from pathlib import Path
import tarfile,zlib
ROOT=Path(__file__).resolve().parents[1]
PACK=ROOT/'p5c/packed/p5c_source.tar.zlib.b64'
EXPECTED='0bd5b185a388e157275600f884d8504ca4e69e4e357e965199edc33ef9e9574f'
ALLOWED={'p5c/README_KO.md','p5c/apply_upgrade.py','p5c/prepare_base.py','p5c/risu_p5c_cli.py','p5c/risu_quickcheck.py','p5c/tests/test_quickcheck.py'}
data=PACK.read_text(encoding='ascii').strip()
if len(data)>25000:raise ValueError('oversize source pack')
raw=zlib.decompress(base64.b64decode(data,validate=True))
if len(raw)>80000 or hashlib.sha256(raw).hexdigest()!=EXPECTED:
 raise ValueError('P5C_SOURCE_BUNDLE_HASH_MISMATCH')
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:') as tf:
 members=tf.getmembers()
 if len(members)!=len(ALLOWED) or {m.name for m in members}!=ALLOWED:
  raise ValueError('unrecognized source inventory')
 for item in members:
  if not item.isfile() or item.issym() or item.islnk() or item.size>40000:
   raise ValueError('unsafe source archive member')
  dest=ROOT/item.name
  if not dest.resolve().is_relative_to(ROOT.resolve()):
   raise ValueError('source path escape')
  content=tf.extractfile(item).read()
  if dest.exists() and dest.read_bytes()!=content:
   raise ValueError('readable source does not match sealed bundle: '+item.name)
  dest.parent.mkdir(parents=True,exist_ok=True)
  dest.write_bytes(content)
print('P5C_BOUNDED_SOURCE_BUNDLE_SHA256_VERIFIED_AND_RESTORED_PASS',len(members))
