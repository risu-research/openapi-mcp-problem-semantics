"""SHA-frozen, narrowly scoped v0.9.8 -> v0.9.9 native capture gate."""
from pathlib import Path
import hashlib, shutil
REPO=Path(__file__).resolve().parents[1]
BASE=REPO/'dist'/'risu_v09_source'
OVR=REPO/'p4h'/'overrides'
PINS={
 'risu_analyze.py':'dc9ec209d31bd8b409fb3f4fc47a57ec2878a26c4eca3a7762fa66f172c193ef',
 'risu_probe.py':'de23e0b9d3c06c97e52d3820e2b7ea54bd050b663e6b786055ceee93a20714d9',
 'risu_recovery.py':'6e7fe4e09cefb452aad1390c71097e07293443468122a378d4e5da25cb1b7cab',
 'pyproject.toml':'86ee4c4929a71d1a94c5316f7f3e23d2ffe4c7f9a8fa014d46a6bf3822c60f8a',
}
for name,pin in PINS.items():
    f=BASE/name;data=f.read_bytes().replace(b'\r\n',b'\n')
    assert hashlib.sha256(data).hexdigest()==pin, ('P4H_UNQUALIFIED_INPUT_MODULE',name)
    f.write_bytes(data)

def rewrite(name,old,new):
    f=BASE/name;original=f.read_text()
    assert original.count(old)==1,('P4H_VERSION_ANCHOR',name,old)
    f.write_text(original.replace(old,new))

rewrite('risu_probe.py',"VERSION = '0.9.8-experimental'","VERSION = '0.9.9-experimental'")
rewrite('risu_recovery.py','0.9.8-experimental-opt-in','0.9.9-experimental-opt-in')
rewrite('pyproject.toml','0.9.8.dev0','0.9.9.dev0')
rewrite('pyproject.toml','"risu_recovery"','"risu_recovery", "risu_capture"')
shutil.copyfile(OVR/'risu_analyze.py',BASE/'risu_analyze.py')
shutil.copyfile(OVR/'risu_capture.py',BASE/'risu_capture.py')
assert 'load_capture_directory' in (BASE/'risu_analyze.py').read_text()
assert 'EXPLICIT_UNVERIFIED_DEVELOPER_PAIRS' in (BASE/'risu_capture.py').read_text()
print('P4H_SHA_PINNED_V099_NATIVE_CAPTURE_GATE_PASS')
for name in ['risu_analyze.py','risu_capture.py','risu_probe.py','risu_recovery.py','pyproject.toml']:
    print(name,hashlib.sha256((BASE/name).read_bytes()).hexdigest())