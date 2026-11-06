"""P4-J SHA-pinned narrow v0.9.9 -> v0.9.10 causal-evidence upgrade.

All original compare, decision, evidence and recovery logic is unchanged.
Only report labeling, opt-in trust verification and version are modified.
"""
from pathlib import Path
import hashlib,shutil
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'dist'/'risu_v09_source'
OVR=ROOT/'p4j'/'overrides'
PINS={
 'risu_analyze.py':'29bc022cb4f701d2a2adb54e35523f33fa05f0a8ce27251b5ffaab098614d338',
 'risu_capture.py':'700da87c53613657a12af970a973369c2a96872ab87571f84b3213e0f8cf874a',
 'risu_probe.py':'d5de4b79f666f0e97adc3d9d045ab4fd8574807a48bf46dd261467dee96f1032',
 'risu_recovery.py':'164482285f55efd4422490aca765c137637f29831664a3c30bc216b07034abe8',
}
for name,expected in PINS.items():
    original=(BASE/name).read_bytes()
    assert hashlib.sha256(original).hexdigest()==expected,('P4J_FROZEN_PRODUCT_SOURCE_MISMATCH',name)

def replace(name,old,new):
    p=BASE/name;s=p.read_text()
    assert s.count(old)==1,('P4J_BAD_UPGRADE_ANCHOR',name,old)
    p.write_text(s.replace(old,new))

replace('risu_probe.py',"VERSION = '0.9.9-experimental'","VERSION = '0.9.10-experimental'")
replace('risu_recovery.py','0.9.9-experimental-opt-in','0.9.10-experimental-opt-in')
replace('pyproject.toml','0.9.9.dev0','0.9.10.dev0')
replace('pyproject.toml','"risu_recovery", "risu_capture"',
                     '"risu_recovery", "risu_capture", "risu_causality"')
shutil.copyfile(OVR/'risu_analyze.py',BASE/'risu_analyze.py')
shutil.copyfile(OVR/'risu_causality.py',BASE/'risu_causality.py')
assert 'causal_gate_v1' in (BASE/'risu_analyze.py').read_text()
assert 'signature verification FAILED' in (BASE/'risu_causality.py').read_text()
print('P4J_SHA_PINNED_CAUSAL_TRUST_GATE_READY')
for name in ['risu_analyze.py','risu_causality.py','risu_probe.py','risu_recovery.py','pyproject.toml']:
    print('P4J_MODULE',name,hashlib.sha256((BASE/name).read_bytes()).hexdigest())
