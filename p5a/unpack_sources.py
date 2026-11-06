"""Restore complete P5-A readable source and tests from a tamper-checked archive."""
from __future__ import annotations
import base64
import hashlib
import io
from pathlib import Path
import tarfile
import zlib

ROOT=Path(__file__).resolve().parents[1]
FILE=ROOT/'p5a'/'packed'/'p5a_sources.tar.zlib.b64'
ALLOWED={
    'p5a/risu_nested_schema.py',
    'p5a/risu_compat.py',
    'p5a/risu_p5a_cli.py',
    'p5a/apply_upgrade.py',
    'p5a/tests/test_p5a.py',
    'p5a/tests/test_nested_legacy.py',
    'p5a/README_KO.md',
}
raw=base64.b64decode(FILE.read_text().strip(),validate=True)
data=zlib.decompress(raw)
if len(data)>100000 or hashlib.sha256(data).hexdigest()!='26e70a6a8fa16f0749130ebc115a0b1a81289171b47f87a7885afe08a3ae36a1':
    raise ValueError('P5A signed source bundle checksum mismatch')
with tarfile.open(fileobj=io.BytesIO(data),mode='r:') as tf:
    members=tf.getmembers()
    if len(members)!=len(ALLOWED) or {m.name for m in members}!=ALLOWED:
        raise ValueError('Unexpected P5A source archive inventory')
    for item in members:
        if not item.isfile() or item.issym() or item.islnk() or item.size>30000:
            raise ValueError('Unsafe P5A archive member')
        path=ROOT/item.name
        if not path.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError('Escaping P5A source path')
        contents=tf.extractfile(item).read()
        if path.exists() and path.read_bytes()!=contents:
            raise ValueError('P5A source file conflict: '+item.name)
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(contents)
        print('P5A_RESTORED_SOURCE',item.name,len(contents),hashlib.sha256(contents).hexdigest(),flush=True)
print('P5A_VERIFIED_SOURCES_RESTORED',len(ALLOWED),flush=True)
