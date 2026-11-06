"""SHA-pinned additive v0.9.7 -> P4G v0.9.8 CLI integration.

Only version string, risu_analyze.py and new risu_recovery.py are modified.
The rest of the qualified v0.9.7 source remains byte-identical.
"""
from pathlib import Path
import hashlib
import shutil

REPO=Path(__file__).resolve().parents[1]
BASE=REPO/'dist'/'risu_v09_source'
OVERRIDE=REPO/'p4g'/'overrides'
PINS={
 'risu_analyze.py':'c0d19ddd5b6660f7878d08684f1fb92365f042cc1d78e6528f1b5f0c7c19e75d',
 'risu_probe.py':'c81dde44945660c80503a9120c10964e85856267e2abd02025e735f90309c759',
 'pyproject.toml':'6361272430141da375042e756a331dc2ebc557a03a45ae21815d73ac016dc9e5',
}
for name, digest in PINS.items():
    raw=(BASE/name).read_bytes().replace(b'\r\n',b'\n')
    assert hashlib.sha256(raw).hexdigest()==digest,('UNQUALIFIED_BASE_CHANGED',name)
    (BASE/name).write_bytes(raw)

def single(name, old, new):
    f=BASE/name;s=f.read_text()
    assert s.count(old)==1,('UNEXPECTED_PATCH_ANCHOR',name,old)
    f.write_text(s.replace(old,new),encoding='utf-8')

single('risu_probe.py',"VERSION = '0.9.7-experimental'","VERSION = '0.9.8-experimental'")
single('pyproject.toml','0.9.7.dev0','0.9.8.dev0')
single('pyproject.toml','"risu_fixverify"','"risu_fixverify", "risu_recovery"')
shutil.copyfile(OVERRIDE/'risu_analyze.py', BASE/'risu_analyze.py')
shutil.copyfile(OVERRIDE/'risu_recovery.py', BASE/'risu_recovery.py')
assert 'recovery_v1' in (BASE/'risu_analyze.py').read_text()
assert '--recovery' in (BASE/'risu_analyze.py').read_text()
print('P4G_SHA_PINNED_MINIMAL_INTEGRATION_PASS')
for name in PINS:
    print('P4G_CHANGED_MODULE',name,hashlib.sha256((BASE/name).read_bytes()).hexdigest())