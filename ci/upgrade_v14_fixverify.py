"""SHA-verified RISU v0.9.5 -> v0.9.6 Fix Verification upgrade.

Build on ci/export_v09_source_portable.py and upgrade_v10..v13 in order.
Original research main and released experiment branches never modified.
"""
from pathlib import Path
import hashlib,shutil
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'dist'/'risu_v09_source'
PINS={
'risu_probe.py':'6239a3945063ef160d9144e8787c9c08f0d3c2194ca331b4256f0a46a28530cf',
'risu_static.py':'f579eea7fa6d576b7b53441501a9994569c9be3561ae2c2f39a258e49b3c8a30',
'risu_onboarding.py':'7bae7ef713c11589566e7d5b686c0cc778349cfaa085c27955e738f406e703bd',
'risu_repair.py':'cde4a80575d9798651d4c999bd3f1f7336d77fe563d855691bbc2a1b5bee65f8',
'risu_minimize.py':'a8bdf5ce2be9281eaa2c00b3975c3c173a20c40bb483f43c0e3962a6efdc6a2e',
'risu_reproduce.py':'ea6a552652576944cceba9afb51a4e3ba04defcfbe5ea7d2d45c77966384a55a',
'pyproject.toml':'48fb33fd20af9e2baa64246ed5e749046a78d65a45be7dc329097f163d81d374'
}
for name,pin in PINS.items():
    path=SOURCE/name
    canonical=path.read_bytes().replace(b'\r\n',b'\n')
    assert hashlib.sha256(canonical).hexdigest()==pin,(name,'BASELINE_SOURCE_UNEXPECTED')
    path.write_bytes(canonical)

def replace(name,old,new):
    f=SOURCE/name
    data=f.read_text('utf-8')
    assert data.count(old)==1,(name,'upgrade anchor count',data.count(old),old)
    f.write_bytes(data.replace(old,new).encode('utf-8'))

shutil.copy2(ROOT/'product_v14'/'risu_fixverify.py',SOURCE/'risu_fixverify.py')
replace('risu_probe.py',"VERSION = '0.9.5-experimental'","VERSION = '0.9.6-experimental'")
replace('risu_onboarding.py',"'0.9.5-experimental'","'0.9.6-experimental'")
replace('risu_static.py',"'0.9.5-experimental'","'0.9.6-experimental'")
replace('risu_static.py',"'version':'0.9.5'","'version':'0.9.6'")
replace('pyproject.toml','0.9.5.dev0','0.9.6.dev0')
replace('pyproject.toml','"risu_reproduce"','"risu_reproduce", "risu_fixverify"')
print('RISU_FIXVERIFY_V096_UPGRADE_SHA_VERIFIED',hashlib.sha256(
    (SOURCE/'risu_fixverify.py').read_bytes()).hexdigest())
