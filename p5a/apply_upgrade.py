"""Upgrade rebuilt P4-T v0.9.16 source to a single installed P5-A wheel.

Runs after P4-T's source patch; prevents changes to old core verdict paths.
"""
from pathlib import Path
import hashlib
import shutil
ROOT=Path(__file__).resolve().parents[1]
PRODUCT=ROOT/'dist'/'risu_v09_source'

def replace_once(relative,old,new):
    file=PRODUCT/relative
    s=file.read_text()
    if s.count(old)!=1:
        raise RuntimeError(f'Unexpected P4-T source version in {relative}: {old}')
    file.write_text(s.replace(old,new))

old={x:hashlib.sha256((PRODUCT/x).read_bytes()).hexdigest() for x in (
    'risu_analyze.py','risu_causality.py','risu_coverage.py','risu_arraymatch.py',
    'risu_contract_history.py','risu_p4t_cli.py','risu_obligations.py')}
replace_once('risu_probe.py',"VERSION = '0.9.16-experimental'","VERSION = '0.9.17-experimental'")
replace_once('pyproject.toml','0.9.16.dev0','0.9.17.dev0')
replace_once('pyproject.toml','risu-probe = "risu_p4t_cli:main"','risu-probe = "risu_p5a_cli:main"')
replace_once('pyproject.toml','"risu_p4t_cli"','"risu_p4t_cli", "risu_nested_schema", "risu_compat", "risu_p5a_cli"')
for f in ('risu_nested_schema.py','risu_compat.py','risu_p5a_cli.py'):
    shutil.copyfile(ROOT/'p5a'/f,PRODUCT/f)
assert all(hashlib.sha256((PRODUCT/x).read_bytes()).hexdigest()==h for x,h in old.items())
print('P5A_ONE_INSTALLABLE_WHEEL_P4T_CORE_VERDICT_BYTE_IDENTICAL_PASS',old,flush=True)
