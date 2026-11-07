"""Extend P5-C source wheel without touching existing causal/static engines."""
from __future__ import annotations
from pathlib import Path
import hashlib, shutil
root=Path(__file__).resolve().parents[1]
product=root/'dist/risu_v09_source'
preserved=('risu_analyze.py','risu_causality.py','risu_coverage.py','risu_arraymatch.py',
 'risu_contract_history.py','risu_obligations.py','risu_nested_schema.py','risu_compat.py',
 'risu_p5a_cli.py','risu_static.py','risu_quickcheck.py','risu_p5c_cli.py')
original={p:hashlib.sha256((product/p).read_bytes()).hexdigest() for p in preserved}
def replace_once(filename,old,new):
 p=product/filename
 s=p.read_text(encoding='utf-8')
 if s.count(old)!=1:raise RuntimeError('P5D_VERSION_ANCHOR_MISMATCH '+filename+' '+old)
 p.write_text(s.replace(old,new),encoding='utf-8')
replace_once('risu_probe.py',"VERSION = '0.9.18-experimental'","VERSION = '0.9.19-experimental'")
replace_once('pyproject.toml','0.9.18.dev0','0.9.19.dev0')
replace_once('pyproject.toml','requires-python = ">=3.11"','requires-python = ">=3.11"\ndependencies = ["PyYAML==6.0.2"]')
replace_once('pyproject.toml','risu-probe = "risu_p5c_cli:main"','risu-probe = "risu_p5d_cli:main"')
replace_once('pyproject.toml','"risu_p5c_cli"','"risu_p5c_cli", "risu_firstuse", "risu_p5d_cli"')
for module in ('risu_firstuse.py','risu_p5d_cli.py'):
 shutil.copyfile(root/'p5d'/module,product/module)
assert {p:hashlib.sha256((product/p).read_bytes()).hexdigest() for p in preserved}==original
print('P5D_12_P5C_EXISTING_MODULES_BYTE_IDENTICAL_PASS')
