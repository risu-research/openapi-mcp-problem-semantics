"""P4-R SHA-pinned opt-in v0.9.13 -> v0.9.14 source-residual disposition lens.

Preserves P4-J conformance/casual gate, P4-O mapping, P4-P coverage,
P4-Q identity joins, and all old default output/exit behavior.
"""
from pathlib import Path
import hashlib
import shutil

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'dist'/'risu_v09_source'
PINS={
 'risu_probe.py':'b413cc5e614b1a9672b95d660cda2a6a3b303181b813a1488badd2d7af677aff',
 'risu_analyze.py':'eb9dde7f22dc5fc5ac7ff0f5966bcc5e91b258af17bb4aeca3409433de414ac2',
 'pyproject.toml':'4e95dae170da9f1e9060612a8df7b681841600b3e2b53edb6850de82b4f2a37e',
 'risu_arraymatch.py':'759e12f869c6add6ba947f60650845431fcbbc003885438c484da0bfeb2937b1',
 'risu_coverage.py':'b7088dc4fc9b462172383e993b8069dd0ce88ff88bc1fde49b9dbad8f7920d5b',
 'risu_causality.py':'f29557787297c53662c2419f9a335beafa8d4ee2890070e843fd303b742e32bc',
 'risu_semantics.py':'4dc3d546a78edf0f09ea6891b5f9c50c7355fa9419fda31f85b41478822d4202'
}
for path,h in PINS.items():
    actual=hashlib.sha256((BASE/path).read_bytes()).hexdigest()
    assert actual==h,('P4R_BASE_SHA_CHANGED',path,h,actual)

def patch(name,old,new):
    p=BASE/name;s=p.read_text()
    assert s.count(old)==1,('BAD_P4R_PATCH_ANCHOR',name,old,s.count(old))
    p.write_text(s.replace(old,new))

patch('risu_probe.py',"VERSION = '0.9.13-experimental'","VERSION = '0.9.14-experimental'")
patch('pyproject.toml','0.9.13.dev0','0.9.14.dev0')
patch('pyproject.toml','"risu_arraymatch"','"risu_arraymatch", "risu_residual"')
patch('risu_analyze.py',
 "    p.add_argument('--array-map',type=Path,help='explicit typed identity joins for observed arrays; requires --field-coverage and --semantic-map')",
 "    p.add_argument('--array-map',type=Path,help='explicit typed identity joins for observed arrays; requires --field-coverage and --semantic-map')\n"
 "    p.add_argument('--residual-map',type=Path,help='classify previously-unverified original source leaves using explicitly declared evidence')\n"
 "    p.add_argument('--fail-on-residual-contradiction',action='store_true',help='exit 1 when a declared residual transformation is contradicted')\n"
 "    p.add_argument('--fail-on-residual-nonexposure',action='store_true',help='exit 1 for observed unexposed source envelope fields; not causal loss proof')\n"
 "    p.add_argument('--fail-on-residual-gap',action='store_true',help='exit 1 when original leaves remain unverified after residual classification')")
patch('risu_analyze.py',
 "            r['source_coverage_with_arrays_v1']=merge_coverage(\n                r['field_coverage_v1'],r['array_identity_v1'],payload,r['semantic_mapping_v1'],args.semantic_map)",
 "            r['source_coverage_with_arrays_v1']=merge_coverage(\n                r['field_coverage_v1'],r['array_identity_v1'],payload,r['semantic_mapping_v1'],args.semantic_map)\n"
 "        if args.residual_map is not None:\n"
 "            if args.array_map is None or args.semantic_map is None or not args.field_coverage:\n"
 "                raise ValueError('--residual-map requires --semantic-map --field-coverage --array-map')\n"
 "            if args.format=='sarif':raise ValueError('residual classification not supported with SARIF')\n"
 "            from risu_residual import assess_residual\n"
 "            r['residual_disposition_v1']=assess_residual(\n"
 "                payload,r['source_coverage_with_arrays_v1'],args.residual_map,args.matrix)")
patch('risu_analyze.py',
 "            if args.recovery and args.format=='markdown':",
 "            if args.residual_map is not None and args.format=='markdown':\n"
 "                from risu_residual import render as render_residual\n"
 "                rendered+='\\n## Remaining original source fields: remapped, normalized or unexposed\\n\\n'+render_residual(r['residual_disposition_v1'])+'\\n'\n"
 "            if args.recovery and args.format=='markdown':")
patch('risu_analyze.py',
 "            if args.recovery:\n                from risu_recovery import render as render_recovery",
 "            if args.residual_map is not None:\n"
 "                from risu_residual import render as render_residual\n"
 "                lines.extend(['',render_residual(r['residual_disposition_v1']).rstrip('\\n')])\n"
 "            if args.recovery:\n                from risu_recovery import render as render_recovery")
patch('risu_analyze.py',
 "        if args.fail_on_array_contradiction and args.array_map is None:",
 "        if (args.fail_on_residual_gap or args.fail_on_residual_nonexposure or args.fail_on_residual_contradiction) and args.residual_map is None:\n"
 "            raise ValueError('residual failure flags require --residual-map')\n"
 "        if args.fail_on_residual_contradiction and any(x['outcome']=='CONTRADICTED' for c in r['residual_disposition_v1']['cases'] for x in c['rules']):\n"
 "            return 1\n"
 "        if args.fail_on_residual_nonexposure and r['residual_disposition_v1']['summary']['observed_nonexposure']:\n"
 "            return 1\n"
 "        if args.fail_on_residual_gap and r['residual_disposition_v1']['summary']['remaining_unverified']:\n"
 "            return 1\n"
 "        if args.fail_on_array_contradiction and args.array_map is None:")
shutil.copyfile(ROOT/'p4r'/'overrides'/'risu_residual.py',BASE/'risu_residual.py')
for path in ('risu_arraymatch.py','risu_coverage.py','risu_causality.py','risu_semantics.py'):
    assert hashlib.sha256((BASE/path).read_bytes()).hexdigest()==PINS[path]
assert 'residual_disposition_v1' in (BASE/'risu_analyze.py').read_text()
print('P4R_SHA_PINNED_RESIDUAL_CLASSIFIER_READY',flush=True)
