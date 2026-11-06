"""Fail-closed v0.9.1 -> v0.9.3 evidence upgrade, after verified v0.9 restore."""
from pathlib import Path
import hashlib
import shutil

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'dist'/'risu_v09_source'
PINNED={
 'risu_probe.py':'9cdc63bb1f1b832260bf6459dabb1c7f47995cf95aa96a5eac88bf327818e5b4',
 'risu_analyze.py':'2d213dbb7faccc5a5c4895394572b1c46847d589f8c37471f3632dc5464be32d',
 'risu_verify.py':'4bdbae7da26ea308333f45d668176a65cfacb890f9bc30e0ca4a9ca583f612b0',
 'pyproject.toml':'47fd825b19f04826d1d98a4fe07cc67e98a600ebed44ae1e98e9a4642c3a6094'}
for name,expected in PINNED.items():
    actual=hashlib.sha256((SOURCE/name).read_bytes()).hexdigest()
    assert actual==expected,(name,'baseline unexpectedly changed',expected,actual)

def replace(name,before,after):
    path=SOURCE/name
    value=path.read_text(encoding='utf-8')
    assert value.count(before)==1,(name,'upgrade anchor missing or ambiguous',before[:80])
    path.write_text(value.replace(before,after),encoding='utf-8')

replace('risu_probe.py',
 'from risu_diagnostics import detect as detect_diagnostics',
 'from risu_diagnostics import detect as detect_diagnostics\nfrom risu_evidence import assess as assess_evidence')
replace('risu_probe.py',"VERSION = '0.9.1-experimental'","VERSION = '0.9.3-experimental'")
replace('risu_probe.py',
 "    if mcp.get('resultType') == 'input_required':\n        return {'id':case_id, 'verdict':'INPUT_REQUIRED'",
 "    if mcp.get('resultType') == 'input_required':\n        return {'evidence_v1':assess_evidence(source,mcp),\n                'id':case_id, 'verdict':'INPUT_REQUIRED'")
replace('risu_probe.py',
 "    if mcp.get('resultType') not in (None,'complete'):\n        return {'id':case_id, 'verdict':'ERROR'",
 "    if mcp.get('resultType') not in (None,'complete'):\n        return {'evidence_v1':assess_evidence(source,mcp),\n                'id':case_id, 'verdict':'ERROR'")
replace('risu_probe.py',
 "        return {'id':case_id, 'verdict':verdict, 'source_http_status':status, 'media_type':mime,\n                'losses':errors, 'inventions':invented, 'note':'error-flag only; non-Problem payload outside this profile'}",
 "        return {'id':case_id, 'verdict':verdict, 'source_http_status':status, 'media_type':mime,\n                'losses':errors, 'inventions':invented, 'note':'error-flag only; non-Problem payload outside this profile',\n                'evidence_v1':assess_evidence(source,mcp,consumer_scoped=(required_paths is not None or target_root is not None))}")
replace('risu_probe.py',
 "    if status >= 400 and (mime == PROBLEM or json_error) and verdict in ('LOSS','LOSS_AND_INVENTED'):\n        entry['diagnostics'] = detect_diagnostics(source,mcp,verdict=verdict)\n    return entry",
 "    if status >= 400 and (mime == PROBLEM or json_error) and verdict in ('LOSS','LOSS_AND_INVENTED'):\n        entry['diagnostics'] = detect_diagnostics(source,mcp,verdict=verdict)\n    entry['evidence_v1'] = assess_evidence(source,mcp,consumer_scoped=(required_paths is not None or target_root is not None))\n    return entry")
replace('risu_analyze.py',
 "    return {'tool':'RISU Probe','version':VERSION,'profile':profile,",
 "    evidence_summary={}\n    action_summary={}\n    for row in rows:\n        evidence=row.get('evidence_v1') or {}\n        recovery=evidence.get('body_recovery','NOT_ASSESSED')\n        action=evidence.get('recommended_action','NONE')\n        evidence_summary[recovery]=evidence_summary.get(recovery,0)+1\n        action_summary[action]=action_summary.get(action,0)+1\n    return {'tool':'RISU Probe','version':VERSION,'profile':profile,")
replace('risu_analyze.py',
 "'summary':summary,'diagnostic_summary':codes,'results':rows}",
 "'summary':summary,'diagnostic_summary':codes,\n            'evidence_summary':evidence_summary,'action_summary':action_summary,'results':rows}")
replace('risu_analyze.py',
 "                lines.append(f\"{e['target']}/{e['id']}: {e['verdict']}\"+(f' [{codes}]' if codes else ''))",
 "                ev=e.get('evidence_v1',{})\n                suffix=f\" | body={ev.get('body_recovery','NOT_ASSESSED')} flag={ev.get('error_flag','UNKNOWN')}\"\n                lines.append(f\"{e['target']}/{e['id']}: {e['verdict']}\"+(f' [{codes}]' if codes else '')+suffix)")
replace('risu_analyze.py',
 "            lines.append('Diagnostics: '+str(r['diagnostic_summary']))",
 "            lines.append('Diagnostics: '+str(r['diagnostic_summary']))\n            lines.append('Evidence calibrated: '+str(r['evidence_summary']))")
replace('risu_verify.py',
 "'loss_count':len(row.get('losses',[]))})",
 "'loss_count':len(row.get('losses',[])),\n                                'evidence_v1':row.get('evidence_v1')})")
replace('pyproject.toml','0.9.1.dev0','0.9.3.dev0')
replace('pyproject.toml','"risu_process", "risu_onboarding"',
 '"risu_process", "risu_onboarding", "risu_evidence"')
replace('risu_verify.py',
 "        analysis=analyze({'targets':matrix['targets']},profile='json-errors')",
 "        from risu_evidence import assess as calibrated_assess\n        counterfactual_rejections=0\n        for row in matrix['targets'][0]['checks']:\n            mutated=copy.deepcopy(row['source_sample'])\n            if not isinstance(mutated.get('body'),dict) or 'risu_fixture_marker' not in mutated['body']:\n                raise FixtureError('fixture body lacks synthetic marker for counterfactual')\n            mutated['body']['risu_fixture_marker']='RISU_COUNTERFACTUAL_NOT_PRESENT'\n            proof=calibrated_assess(mutated,row['mcp_sample'])\n            if proof['body_recovery'] in ('EXACT_MACHINE','EXACT_JSON_TEXT'):\n                raise FixtureError('counterfactual source was falsely certified as exact')\n            counterfactual_rejections+=1\n        analysis=analyze({'targets':matrix['targets']},profile='json-errors')")
replace('risu_verify.py',
 "'error_losses':len(confirmed)}",
 "'error_losses':len(confirmed),'counterfactual_rejections':counterfactual_rejections}")
shutil.copy2(ROOT/'product_v11'/'risu_evidence.py',SOURCE/'risu_evidence.py')
print('RISU 0.9.3 product restored from pinned v0.9.1:')
for name in (*PINNED,'risu_evidence.py'):
    print(name,hashlib.sha256((SOURCE/name).read_bytes()).hexdigest())
