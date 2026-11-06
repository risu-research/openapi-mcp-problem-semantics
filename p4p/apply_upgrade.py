"""P4-P SHA-pinned additive upgrade of v0.9.11 P4-O -> v0.9.12.

Do not modify comparator, source mapping evaluator, P4-J trust gate or
recovery rules. Only opt-in source coverage accounting and its CLI surfaces.
"""
import hashlib
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"dist"/"risu_v09_source"
PINS={
 "risu_analyze.py":"56081e051c6477e1942d2e455a8d785ea1e0f445a0f1179f9eb763d956ee931b",
 "risu_probe.py":"2548e269ad3b4e7a22465d19d86bfe497ea62d08cd73f10c9da1bf7b063dde90",
 "pyproject.toml":"95affb5f6f5e8662ac42a5f93328692fd38c59c7252f7f90ea15c9a0c80812a8",
 "risu_semantics.py":"4dc3d546a78edf0f09ea6891b5f9c50c7355fa9419fda31f85b41478822d4202",
 "risu_causality.py":"f29557787297c53662c2419f9a335beafa8d4ee2890070e843fd303b742e32bc",
}
for name,sha in PINS.items():
    got=hashlib.sha256((BASE/name).read_bytes()).hexdigest()
    assert got==sha,("P4P_FROZEN_P4O_BASE_MISMATCH",name,sha,got)

def patch(name,old,new):
    path=BASE/name
    value=path.read_text()
    assert value.count(old)==1,("P4P_BAD_ANCHOR",name,old,value.count(old))
    path.write_text(value.replace(old,new))

patch("risu_probe.py","VERSION = '0.9.11-experimental'","VERSION = '0.9.12-experimental'")
patch("pyproject.toml","0.9.11.dev0","0.9.12.dev0")
patch("pyproject.toml",'"risu_semantics"','"risu_semantics", "risu_coverage"')
patch("risu_analyze.py",
    "    p.add_argument('--semantic-map',type=Path,help='opt-in operator-declared observed field/lookup mappings; only native captures')",
    "    p.add_argument('--semantic-map',type=Path,help='opt-in operator-declared observed field/lookup mappings; only native captures')\n"
    "    p.add_argument('--field-coverage',action='store_true',help='count all original JSON leaves and mapping-verified source fields; requires --semantic-map')\n"
    "    p.add_argument('--fail-on-coverage-gap',action='store_true',help='exit 1 if any original source leaf lacks a verified declared mapping; requires --field-coverage')")
patch("risu_analyze.py",
    "            r['semantic_mapping_v1']=assess(payload,r,args.matrix if args.matrix.is_dir() else None,args.semantic_map)",
    "            r['semantic_mapping_v1']=assess(payload,r,args.matrix if args.matrix.is_dir() else None,args.semantic_map)\n"
    "        if args.field_coverage:\n"
    "            if args.semantic_map is None:raise ValueError('--field-coverage requires --semantic-map')\n"
    "            from risu_coverage import assess_coverage\n"
    "            r['field_coverage_v1']=assess_coverage(payload,r['semantic_mapping_v1'],args.semantic_map)")
patch("risu_analyze.py",
    "            if args.recovery and args.format=='markdown':",
    "            if args.field_coverage and args.format=='markdown':\n"
    "                from risu_coverage import render as render_coverage\n"
    "                rendered+='\\n## Observed source field coverage (not proof of complete preservation)\\n\\n'+render_coverage(r['field_coverage_v1'])+'\\n'\n"
    "            if args.recovery and args.format=='markdown':")
patch("risu_analyze.py",
    "            if args.recovery:\n                from risu_recovery import render as render_recovery",
    "            if args.field_coverage:\n"
    "                from risu_coverage import render as render_coverage\n"
    "                lines.extend(['',render_coverage(r['field_coverage_v1']).rstrip('\\n')])\n"
    "            if args.recovery:\n                from risu_recovery import render as render_recovery")
patch("risu_analyze.py",
    "        if args.fail_on_semantic_contradiction and args.semantic_map is None:",
    "        if args.fail_on_coverage_gap and not args.field_coverage:\n"
    "            raise ValueError('--fail-on-coverage-gap requires --field-coverage')\n"
    "        if args.fail_on_coverage_gap and any(c['full_source']['coverage_verified_units'] != c['full_source']['total_source_leaf_units'] or c['full_source']['total_source_leaf_units']==0 or c['rule_outcome']!='ALL_DECLARED_CHECKS_MATCH' for c in r['field_coverage_v1']['cases']):\n"
    "            return 1\n"
    "        if args.fail_on_semantic_contradiction and args.semantic_map is None:")
shutil.copyfile(ROOT/"p4p"/"overrides"/"risu_coverage.py",BASE/"risu_coverage.py")
# No side effects unless opt-in. SHA pinning prevents the upgrade running
# against a subtly changed upstream version.
assert 'field_coverage_v1' in (BASE/"risu_analyze.py").read_text()
assert hashlib.sha256((BASE/"risu_causality.py").read_bytes()).hexdigest()==PINS["risu_causality.py"]
assert hashlib.sha256((BASE/"risu_semantics.py").read_bytes()).hexdigest()==PINS["risu_semantics.py"]
print("P4P_SHA_PINNED_OBSERVED_SOURCE_COVERAGE_READY")
