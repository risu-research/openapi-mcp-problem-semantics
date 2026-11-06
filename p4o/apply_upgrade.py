"""SHA-pinned opt-in v0.9.10 -> v0.9.11 semantic layer upgrade.

Comparator, calibrated policy, causal trust witness, and recovery stay unchanged.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'dist'/'risu_v09_source'
PINS={
 'risu_analyze.py':'ae419567b5f9d3f8f63b29205680bcef473e63acf311e1785948af6162c9b9fe',
 'risu_probe.py':'d74b81157c6a37d29fa2597dbc681e3c53b26bf00fac1d04a0139c37bef9b980',
 'pyproject.toml':'9c909ecf8f07836eb9ad90ef7822a9927d39302ecfe188aa8d5f0f2aec6e559d',
 'risu_causality.py':'f29557787297c53662c2419f9a335beafa8d4ee2890070e843fd303b742e32bc'
}
for name,expected in PINS.items():
    got=hashlib.sha256((BASE/name).read_bytes()).hexdigest()
    assert got==expected,('P4O_FROZEN_PRODUCT_SOURCE_MISMATCH',name,expected,got)

def patch(name,old,new):
    path=BASE/name
    text=path.read_text()
    assert text.count(old)==1,('P4O_BAD_ANCHOR',name,old)
    path.write_text(text.replace(old,new))

patch('risu_probe.py',"VERSION = '0.9.10-experimental'","VERSION = '0.9.11-experimental'")
patch('pyproject.toml','0.9.10.dev0','0.9.11.dev0')
patch('pyproject.toml','"risu_causality"','"risu_causality", "risu_semantics"')
patch('risu_analyze.py',
    "    p.add_argument('--fail-on-loss',action='store_true')",
    "    p.add_argument('--fail-on-loss',action='store_true')\n"
    "    p.add_argument('--semantic-map',type=Path,help='operator-declared mappings, native captures only')\n"
    "    p.add_argument('--fail-on-semantic-contradiction',action='store_true',help='exit 1 for contradicted declared mappings')")
patch('risu_analyze.py',
    "        if args.recovery:\n            if args.format=='sarif':",
    "        if args.semantic_map is not None:\n"
    "            if args.format=='sarif':\n"
    "                raise ValueError('semantic mapping is not supported with SARIF; use JSON, text or markdown')\n"
    "            from risu_semantics import assess\n"
    "            r['semantic_mapping_v1']=assess(payload,r,args.matrix if args.matrix.is_dir() else None,args.semantic_map)\n"
    "        if args.recovery:\n            if args.format=='sarif':")
patch('risu_analyze.py',
    "            if args.recovery and args.format=='markdown':",
    "            if args.semantic_map is not None and args.format=='markdown':\n"
    "                from risu_semantics import render as render_semantic\n"
    "                rendered+='\\n## Scoped semantic mapping checks (operator-declared)\\n\\n'+render_semantic(r['semantic_mapping_v1'])+'\\n'\n"
    "            if args.recovery and args.format=='markdown':")
patch('risu_analyze.py',
    "            if args.recovery:\n                from risu_recovery import render as render_recovery",
    "            if args.semantic_map is not None:\n"
    "                from risu_semantics import render as render_semantic\n"
    "                lines.extend(['',render_semantic(r['semantic_mapping_v1']).rstrip('\\n')])\n"
    "            if args.recovery:\n                from risu_recovery import render as render_recovery")
patch('risu_analyze.py',
    "        if args.fail_on_confirmed_loss and r['causal_gate_v1']['summary']['CONFIRMED_LOSS']:\n            return 1",
    "        if args.fail_on_confirmed_loss and r['causal_gate_v1']['summary']['CONFIRMED_LOSS']:\n"
    "            return 1\n"
    "        if args.fail_on_semantic_contradiction and args.semantic_map is None:\n"
    "            raise ValueError('--fail-on-semantic-contradiction requires --semantic-map')\n"
    "        if args.fail_on_semantic_contradiction and r['semantic_mapping_v1']['rules_summary']['CONTRADICTED']:\n"
    "            return 1")
shutil.copyfile(ROOT/'p4o'/'overrides'/'risu_semantics.py',BASE/'risu_semantics.py')
assert 'semantic_mapping_v1' in (BASE/'risu_analyze.py').read_text()
assert 'CONFIRMED_LOSS' in (BASE/'risu_causality.py').read_text()
print('P4O_SHA_PINNED_SEMANTIC_LENS_READY')
