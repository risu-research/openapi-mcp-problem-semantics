"""P4-T opt-in wrapper upgrade from a fully rebuilt P4-S v0.9.15 source tree.

This patch leaves previous analyze/causal verdict logic byte-identical. Only the
entry point and version metadata are changed; two independent modules are added.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT / 'dist' / 'risu_v09_source'

def unique_replace(path, old, new):
    src = (PRODUCT / path)
    text = src.read_text(encoding='utf-8')
    if text.count(old) != 1:
        raise RuntimeError(f'P4T_PATCH_ANCHOR_MISMATCH {path} {old!r} count={text.count(old)}')
    src.write_text(text.replace(old, new), encoding='utf-8')

for filename in ('risu_probe.py', 'risu_analyze.py', 'pyproject.toml'):
    if not (PRODUCT / filename).is_file():
        raise RuntimeError('P4-S upstream product tree missing; build P4-S first')
old_analyze = hashlib.sha256((PRODUCT/'risu_analyze.py').read_bytes()).hexdigest()
old_causal = hashlib.sha256((PRODUCT/'risu_causality.py').read_bytes()).hexdigest()
unique_replace('risu_probe.py', "VERSION = '0.9.15-experimental'", "VERSION = '0.9.16-experimental'")
unique_replace('pyproject.toml', '0.9.15.dev0', '0.9.16.dev0')
unique_replace('pyproject.toml', 'risu-probe = "risu_probe:main"', 'risu-probe = "risu_p4t_cli:main"')
unique_replace('pyproject.toml', '"risu_obligations"', '"risu_obligations", "risu_contract_history", "risu_p4t_cli"')
for file in ('risu_contract_history.py','risu_p4t_cli.py'):
    shutil.copyfile(ROOT/'p4t'/file, PRODUCT/file)
assert old_analyze == hashlib.sha256((PRODUCT/'risu_analyze.py').read_bytes()).hexdigest()
assert old_causal == hashlib.sha256((PRODUCT/'risu_causality.py').read_bytes()).hexdigest()
print('P4T_WRAPPER_UPGRADE_V0916_AND_P4S_VERDICTS_BYTE_IDENTICAL_PASS',old_analyze,old_causal,flush=True)
