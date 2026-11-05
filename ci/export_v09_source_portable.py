"""Portable, fail-closed restoration of exact integrated RISU Probe v0.9 modules.
Runs on Windows and Linux with Python standard library only.
Never executes any recovered source during extraction.
"""
from __future__ import annotations
import base64
import hashlib
import io
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "product"
OUT = ROOT / "dist" / "risu_v09_source"
BASE = json.loads((BUNDLE / "SOURCE_MANIFEST.json").read_text(encoding="utf-8"))
PARTS = [BUNDLE / ("part_%02d.b64" % i) for i in range(6)]
assert all(path.is_file() for path in PARTS), "missing authenticated source part"
raw = base64.b64decode("".join(p.read_text(encoding="ascii").strip() for p in PARTS), validate=True)
assert hashlib.sha256(raw).hexdigest() == BASE["module_tar_sha256"], "source archive checksum mismatch"
OUT.mkdir(parents=True, exist_ok=True)
with tarfile.open(fileobj=io.BytesIO(raw), mode="r:xz") as archive:
    members = archive.getmembers()
    assert {m.name for m in members} == set(BASE["modules_sha256"]), "unexpected source files"
    for member in members:
        assert member.isfile() and "/" not in member.name and "\\" not in member.name and member.size < 100_000
        data = archive.extractfile(member).read()
        assert hashlib.sha256(data).hexdigest() == BASE["modules_sha256"][member.name], member.name
        (OUT / member.name).write_bytes(data)

fix = {
    "risu_verify.py": [
        ("with MCPClient(cmd,protocol='auto',env=env) as client:",
         "with MCPClient(cmd,protocol='legacy',env=env) as client:"),
        ("server_cmd=cmd,protocol='auto')",
         "server_cmd=cmd,protocol='legacy')"),
        ("matrix=capture(plan['cases'],base,cmd,protocol='auto',recheck_source=True,",
         "matrix=capture(plan['cases'],base,cmd,protocol='legacy',recheck_source=True,"),
        ("interpreter=str(exe.resolve())",
         "interpreter=str(exe.absolute())"),
        ("from risu_probe import MCPClient\n",
         "from risu_probe import MCPClient, VERSION\n"),
        ("label='v08-cnoe-fixture'", "label='v09-cnoe-fixture'"),
        ("'probe_version':'0.8.0-experimental'", "'probe_version':VERSION"),
    ],
    "risu_probe.py": [
        ("VERSION = '0.8.0-experimental'", "VERSION = '0.9.0-experimental'"),
    ],
}
expected = {
    "risu_probe.py": "d2a9af2b19a17d33925d64f2ced8b0e52442577fcecba020bdcccd360bb070f1",
    "risu_verify.py": "4bdbae7da26ea308333f45d668176a65cfacb890f9bc30e0ca4a9ca583f612b0",
}
for filename, edits in fix.items():
    path = OUT / filename
    value = path.read_text(encoding="utf-8")
    for before, after in edits:
        assert value.count(before) == 1, (filename, before)
        value = value.replace(before, after)
    path.write_bytes(value.encode("utf-8"))
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected[filename], filename

print("EXACT v0.9 RESTORED", len(BASE["modules_sha256"]), "modules", OUT)
