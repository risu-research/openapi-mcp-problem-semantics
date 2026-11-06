"""Expand byte-pinned, zlib-compressed UTF-8 SOURCE payloads for CI.

The packed source preserves exact local validated code while avoiding a second
generated copy committed under a misleading provenance. We SHA-check the
unpacked human-readable files and include them in GitHub CI artifacts.
"""
import base64
import hashlib
from pathlib import Path
import zlib

ROOT=Path(__file__).resolve().parent
FILES={
    "coverage.py.zlib.b64":("overrides/risu_coverage.py","b7088dc4fc9b462172383e993b8069dd0ce88ff88bc1fde49b9dbad8f7920d5b"),
    "test_field_coverage.py.zlib.b64":("tests/test_field_coverage.py","55023132a0d21b61a6d72608ef6f86cfd4a8b54c80a41666d46fc4e5feb36d1a"),
    "independent_audit.py.zlib.b64":("independent_audit.py","f40d1585cab2e4632aeb5dda67f6f96e70f7c079b8d6b0be8ee69260dd530f82"),
}
for name,(dst,sha) in FILES.items():
    encoded=(ROOT/"packed"/name).read_text().strip()
    body=zlib.decompress(base64.b64decode(encoded,validate=True),max_length=0) if False else zlib.decompress(base64.b64decode(encoded,validate=True))
    assert len(body)<=20000,("P4P_UNPACK_TOO_LARGE",name)
    assert hashlib.sha256(body).hexdigest()==sha,("P4P_SOURCE_HASH_MISMATCH",name)
    output=ROOT/dst
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(body)
    print("P4P_EXACT_SOURCE_UNPACKED",dst,len(body),sha,flush=True)
