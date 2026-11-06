"""P4-Q additive, source-hash-pinned v0.9.12 -> v0.9.13 upgrade.

Do NOT modify P4-P original field counting, P4-O semantic mapping, raw
comparator, or P4-J signed causal trust gate.
"""
from pathlib import Path
import hashlib
import shutil

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"dist"/"risu_v09_source"
PINS={
 "risu_analyze.py":"cddfb8ca48966609588449d5984cc404f1353fd4418c4355ea9c379e82215831",
 "risu_probe.py":"d7203728dabacdb5987a484044b4ec01b06827d9211d868d410ac95a50b8407b",
 "risu_coverage.py":"b7088dc4fc9b462172383e993b8069dd0ce88ff88bc1fde49b9dbad8f7920d5b",
 "risu_semantics.py":"4dc3d546a78edf0f09ea6891b5f9c50c7355fa9419fda31f85b41478822d4202",
 "risu_causality.py":"f29557787297c53662c2419f9a335beafa8d4ee2890070e843fd303b742e32bc",
}
for name,expected in PINS.items():
    got=hashlib.sha256((BASE/name).read_bytes()).hexdigest()
    assert got==expected,("P4Q_FROZEN_P4P_BASE_SHA_MISMATCH",name,expected,got)

def patch(name,old,new):
    path=BASE/name
    txt=path.read_text()
    if txt.count(old)!=1:
        raise ValueError("P4Q_BAD_SOURCE_ANCHOR "+name+" "+str(txt.count(old)))
    path.write_text(txt.replace(old,new))

patch("risu_probe.py","VERSION = '0.9.12-experimental'","VERSION = '0.9.13-experimental'")
patch("pyproject.toml","0.9.12.dev0","0.9.13.dev0")
patch("pyproject.toml",'"risu_coverage"','"risu_coverage", "risu_arraymatch"')
patch("risu_analyze.py",
 "    p.add_argument('--field-coverage',action='store_true',help='count all original JSON leaves and mapping-verified source fields; requires --semantic-map')",
 "    p.add_argument('--field-coverage',action='store_true',help='count all original JSON leaves and mapping-verified source fields; requires --semantic-map')\n"
 "    p.add_argument('--array-map',type=Path,help='explicit typed identity joins for observed arrays; requires --field-coverage and --semantic-map')\n"
 "    p.add_argument('--fail-on-array-contradiction',action='store_true',help='exit 1 for a contradicted declared array identity/field mapping')\n"
 "    p.add_argument('--fail-on-combined-coverage-gap',action='store_true',help='exit 1 if any original leaf is unverified after validated array matching')")
patch("risu_analyze.py",
 "            r['field_coverage_v1']=assess_coverage(payload,r['semantic_mapping_v1'],args.semantic_map)",
 "            r['field_coverage_v1']=assess_coverage(payload,r['semantic_mapping_v1'],args.semantic_map)\n"
 "        if args.array_map is not None:\n"
 "            if not args.field_coverage or args.semantic_map is None:\n"
 "                raise ValueError('--array-map requires --field-coverage and --semantic-map')\n"
 "            if args.format=='sarif':raise ValueError('array identity mapping is not available for SARIF')\n"
 "            from risu_arraymatch import assess_arrays, merge_coverage\n"
 "            r['array_identity_v1']=assess_arrays(payload,args.array_map,args.matrix)\n"
 "            r['source_coverage_with_arrays_v1']=merge_coverage(\n"
 "                r['field_coverage_v1'],r['array_identity_v1'],payload,r['semantic_mapping_v1'],args.semantic_map)")
patch("risu_analyze.py",
 "            if args.recovery and args.format=='markdown':",
 "            if args.array_map is not None and args.format=='markdown':\n"
 "                from risu_arraymatch import render as render_array\n"
 "                rendered+='\\n## Keyed array identity checks (operator-declared)\\n\\n'+render_array(r['array_identity_v1'])+'\\n'\n"
 "                rendered+='\\n## Combined original source field coverage\\n\\n'+str(r['source_coverage_with_arrays_v1']['summary'])+'\\n'\n"
 "            if args.recovery and args.format=='markdown':")
patch("risu_analyze.py",
 "            if args.recovery:\n                from risu_recovery import render as render_recovery",
 "            if args.array_map is not None:\n"
 "                from risu_arraymatch import render as render_array\n"
 "                lines.extend(['',render_array(r['array_identity_v1']).rstrip('\\n'),\n"
 "                    'Combined source coverage: '+str(r['source_coverage_with_arrays_v1']['summary'])])\n"
 "            if args.recovery:\n                from risu_recovery import render as render_recovery")
patch("risu_analyze.py",
 "        if args.fail_on_coverage_gap and not args.field_coverage:",
 "        if args.fail_on_array_contradiction and args.array_map is None:\n"
 "            raise ValueError('--fail-on-array-contradiction requires --array-map')\n"
 "        if args.fail_on_combined_coverage_gap and args.array_map is None:\n"
 "            raise ValueError('--fail-on-combined-coverage-gap requires --array-map')\n"
 "        if args.fail_on_array_contradiction and r['array_identity_v1']['summary']['contradicted_groups']:\n"
 "            return 1\n"
 "        if args.fail_on_combined_coverage_gap and r['source_coverage_with_arrays_v1']['summary']['combined_unverified']:\n"
 "            return 1\n"
 "        if args.fail_on_coverage_gap and not args.field_coverage:")
shutil.copyfile(ROOT/"p4q"/"overrides"/"risu_arraymatch.py",BASE/"risu_arraymatch.py")
for name in ("risu_causality.py","risu_coverage.py","risu_semantics.py"):
    assert hashlib.sha256((BASE/name).read_bytes()).hexdigest()==PINS[name]
assert "source_coverage_with_arrays_v1" in (BASE/"risu_analyze.py").read_text()
print("P4Q_SOURCE_HASH_PINNED_IDENTITY_GROUPS_READY",flush=True)
