"""P4-S extract the exact SHA-verified 7 readable source files, no paths/symlinks."""
from __future__ import annotations
import base64, hashlib, io, tarfile, zlib
from pathlib import Path

HERE=Path(__file__).resolve().parent
encoded=(HERE/'packed'/'p4s_source.tar.zlib.b64').read_text().strip()
assert len(encoded)<30000
data=zlib.decompress(base64.b64decode(encoded,validate=True))
assert len(data)<120000
assert hashlib.sha256(data).hexdigest()=='175b32df17f0c6a00f30891f1cad07dc2fa860a06bb893ec265e5d6ba34866ef'
names={
 'p4s/overrides/risu_obligations.py','p4s/apply_upgrade.py','p4s/independent_audit.py',
 'p4s/tests/test_field_obligations.py','p4s/tests/test_cli_obligations.py',
 'p4s/fixtures/jpo_obligation_policy.json','p4s/fixtures/external_pinned_source.json'}
with tarfile.open(fileobj=io.BytesIO(data),mode='r:') as t:
    members=t.getmembers()
    assert {m.name for m in members}==names and len(members)==len(names)
    for m in members:
        assert m.isfile() and not m.issym() and not m.islnk() and m.size<80000
        p=HERE.parent/m.name
        assert p.resolve().is_relative_to(HERE.parent.resolve())
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(t.extractfile(m).read())
        assert p.stat().st_size==m.size
        print('P4S_FROZEN_HUMAN_READABLE_SOURCE',m.name,m.size,hashlib.sha256(p.read_bytes()).hexdigest(),flush=True)
print('P4S_SHA_VERIFIED_SOURCE_RESTORED',len(names))
