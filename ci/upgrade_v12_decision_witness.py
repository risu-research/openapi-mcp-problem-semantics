"""Fail-closed SHA-pinned v0.9.3 -> v0.9.4 P0 + Consumer Witness upgrade.

Run only AFTER ci/export_v09_source_portable.py, upgrade_v10_modules.py,
and upgrade_v11_semantics.py. The original research main remains untouched.
"""
from pathlib import Path
import hashlib,shutil

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'dist'/'risu_v09_source'
PINNED={
 'risu_probe.py':'29ecd65dac04df8de678ef9bd72e798a3ddff281704a77a295fa8d853c764956',
 'risu_analyze.py':'92251df302de8827f79ebd3c9dceaa3ab4a324dc6f342802397b07f9cb4517e0',
 'risu_report.py':'2187600c84f5050ab3652eeef468baa7b467f6b723a75f53f1efedfab64a83f8',
 'risu_verify.py':'f66f68e446d4fdaa3a09448587693273a3834baa42f35db227e3f8077a5d97b2',
 'risu_static.py':'08741d5ad8d90d76be49c32edeb34aa658e1877e2887e2e4b62d2cbd87381d90',
 'risu_onboarding.py':'869a55a2a1cc0ce3ede5a614b21f8fd888b5dc5ef3985bcdf91feadc2f7419a8',
 'risu_evidence.py':'dd6e1e6dbce835614fac45e8daa1ae5118bd36ea818c3b2c878d21327bba759a',
 'pyproject.toml':'b625df3e42a1c96db689aef7c73a343112b0e6b3a17c09918a017d86d0353e97'}
for name,pin in PINNED.items():
    path=SOURCE/name
    raw=path.read_bytes()
    canonical=raw.replace(b'\r\n',b'\n')
    assert b'\r' not in canonical,(name,'unexpected carriage return')
    assert hashlib.sha256(canonical).hexdigest()==pin,(name,'unexpected v0.9.3 base')
    path.write_bytes(canonical)

def replace(name,before,after):
    path=SOURCE/name
    text=path.read_text(encoding='utf-8')
    assert text.count(before)==1,(name,'missing or ambiguous patch anchor',before[:100])
    path.write_bytes(text.replace(before,after).encode('utf-8'))

def section(name,start,end,contents):
    path=SOURCE/name
    val=path.read_text(encoding='utf-8')
    assert val.count(start)==val.count(end)==1,(name,'section anchors missing')
    left=val.index(start);right=val.index(end,left)
    path.write_bytes((val[:left]+contents+'\n\n'+val[right:]).encode('utf-8'))

for name in ('risu_decision.py','risu_witness.py'):
    shutil.copy2(ROOT/'product_v12'/name,SOURCE/name)

# One policy governs every report serialization and CI-exit path.
replace('risu_probe.py',
 'from risu_evidence import assess as assess_evidence',
 'from risu_evidence import assess as assess_evidence\nfrom risu_decision import apply as apply_decisions, any_blocking, decide')
replace('risu_probe.py',"VERSION = '0.9.3-experimental'","VERSION = '0.9.4-experimental'")
replace('risu_probe.py',
 "def run_cases(cases, *, upstream=None, server_cmd=None, protocol='auto', allow_remote=False, recheck_source=False, verify_catalog=True, error_profile='problem-only'):",
 "def run_cases(cases, *, upstream=None, server_cmd=None, protocol='auto', allow_remote=False, recheck_source=False, verify_catalog=True, error_profile='problem-only', policy='calibrated'):")
replace('risu_probe.py',
 "    return {'tool':'RISU Probe','version':VERSION,'protocol':protocol,\n            'summary':summary,'diagnostic_summary':codes,'results':items}",
 "    return apply_decisions({'tool':'RISU Probe','version':VERSION,'protocol':protocol,\n            'summary':summary,'diagnostic_summary':codes,'results':items},policy)")
replace('risu_probe.py',
 "    losses='\\n'.join(item.get('losses',[]))",
 "    evidence=item.get('evidence_v1') or {}\n    if evidence.get('error_flag') in ('ERROR_FLAG_LOST','SPURIOUS_ERROR_FLAG'):\n        return 'Correct the MCP isError flag independently of body transport.'\n    if evidence.get('body_recovery')=='EXACT_JSON_TEXT':\n        return 'Original JSON was verified in text. Structured-only consumers still need structuredContent; avoid claiming actual body deletion.'\n    if evidence.get('machine_carrier')=='METADATA_ONLY_EXACT':\n        return 'Body exists only in _meta; confirm consumer access and contract before calling this preserved.'\n    losses='\\n'.join(item.get('losses',[]))")
replace('risu_probe.py',
 "        verdict=item['verdict']\n        lines.append(f'{verdict:18} {item[\"id\"]}' +",
 "        verdict=item['verdict']\n        decision=item.get('decision_v1') or decide(item)\n        lines.append(f\"{decision['outcome']:8} {item['id']} [legacy:{verdict} reason:{decision['reason']}]\" +")
replace('risu_probe.py',
 "            lines.append(f'  lost: {loss}')",
 "            lines.append(f'  strict-carrier finding: {loss}')")
replace('risu_probe.py',
 "    p.add_argument('--min-covered', type=int, default=1, help='minimum analyzed cases (default 1)')",
 "    p.add_argument('--min-covered', type=int, default=1, help='minimum analyzed cases (default 1)')\n    p.add_argument('--policy',choices=('calibrated','strict-carrier'),default='calibrated')\n    p.add_argument('--fail-on-review',action='store_true',help='opt into blocking uncertain or deferred cases')")
replace('risu_probe.py',
 "                         verify_catalog=True, error_profile=(args.error_profile or config.get('error_profile','problem-only')))",
 "                         verify_catalog=True, error_profile=(args.error_profile or config.get('error_profile','problem-only')),\n                         policy=args.policy)")
old="""        if args.fail_new_only:
            # Only acknowledged *semantic findings* may be tolerated. Missing
            # tools, source instability, errors and uncompleted results fail.
            return 1 if shortfall or any(
                r['verdict'] not in ('PRESERVED','NOT_APPLICABLE') and r.get('baseline') != 'known'
                for r in report['results']) else 0
        return 1 if shortfall or any(r['verdict'] not in ('PRESERVED', 'NOT_APPLICABLE')
                                     for r in report['results']) else 0"""
new="""        if args.fail_new_only:
            return int(shortfall or any_blocking(report,fail_review=args.fail_on_review,new_only=True))
        return int(shortfall or any_blocking(report,fail_review=args.fail_on_review))"""
replace('risu_probe.py',old,new)
# Two entrypoints share exactly the same policy.
replace('risu_probe.py',
 "    p.add_argument('--error-profile',choices=('problem-only','json-errors'),default='problem-only')\n    args=p.parse_args(argv)",
 "    p.add_argument('--error-profile',choices=('problem-only','json-errors'),default='problem-only')\n    p.add_argument('--policy',choices=('calibrated','strict-carrier'),default='calibrated')\n    args=p.parse_args(argv)")
replace('risu_probe.py',
 "        report={'tool':'RISU Probe','version':VERSION,'summary':s,'results':[entry]}",
 "        report=apply_decisions({'tool':'RISU Probe','version':VERSION,'summary':s,'results':[entry]},args.policy)")
replace('risu_probe.py',
 "        return 1 if entry['verdict'] not in ('PRESERVED','NOT_APPLICABLE') else 0",
 "        return int(any_blocking(report))")
replace('risu_probe.py',
 "    if argv and argv[0]=='analyze':\n        from risu_analyze import main as analyze_main\n        return analyze_main(argv[1:])",
 "    if argv and argv[0]=='analyze':\n        from risu_analyze import main as analyze_main\n        return analyze_main(argv[1:])\n    if argv and argv[0]=='witness':\n        from risu_witness import main as witness_main\n        return witness_main(argv[1:])")
replace('risu_probe.py',
 "    p.add_argument('--fail-on-loss',action='store_true',help='nonzero exit for LOSS/INVENTED/ERROR')",
 "    p.add_argument('--fail-on-loss',action='store_true',help='nonzero exit on calibrated FAIL')\n    p.add_argument('--fail-on-review',action='store_true')\n    p.add_argument('--policy',choices=('calibrated','strict-carrier'),default='calibrated')")
replace('risu_probe.py',
 "                         protocol=args.protocol,allow_remote=args.allow_remote,recheck_source=args.recheck_source,error_profile=args.error_profile)",
 "                         protocol=args.protocol,allow_remote=args.allow_remote,recheck_source=args.recheck_source,error_profile=args.error_profile,\n                         policy=args.policy)")
replace('risu_probe.py',
 "        if args.fail_on_loss and any(r['verdict'] not in ('PRESERVED','NOT_APPLICABLE') for r in report['results']):\n            return 1",
 "        if args.fail_on_loss and any_blocking(report,fail_review=args.fail_on_review):\n            return 1")
replace('risu_probe.py',
 "'\\nOther commands: check, plan, plan-auto, collect, analyze, compare, baseline'",
 "'\\nOther commands: check, plan, plan-auto, collect, analyze, witness, compare, baseline'")

# JSON, plain text, Markdown and SARIF get the same decision field.
replace('risu_analyze.py',
 "def analyze(payload, profile='json-errors'):",
 "def analyze(payload, profile='json-errors', policy='calibrated'):")
replace('risu_analyze.py',
 "    from risu_probe import compare, VERSION, ProbeError",
 "    from risu_probe import compare, VERSION, ProbeError\n    from risu_decision import apply as apply_decisions")
replace('risu_analyze.py',
 "    return {'tool':'RISU Probe','version':VERSION,'profile':profile,",
 "    return apply_decisions({'tool':'RISU Probe','version':VERSION,'profile':profile,")
replace('risu_analyze.py',
 "            'evidence_summary':evidence_summary,'action_summary':action_summary,'results':rows}",
 "            'evidence_summary':evidence_summary,'action_summary':action_summary,'results':rows},policy)")
replace('risu_analyze.py',
 "    p.add_argument('--fail-on-loss',action='store_true')",
 "    p.add_argument('--fail-on-loss',action='store_true')\n    p.add_argument('--fail-on-review',action='store_true')\n    p.add_argument('--policy',choices=('calibrated','strict-carrier'),default='calibrated')")
replace('risu_analyze.py',
 "        r=analyze(payload,args.profile)",
 "        r=analyze(payload,args.profile,args.policy)")
replace('risu_analyze.py',
 "                suffix=f\" | body={ev.get('body_recovery','NOT_ASSESSED')} flag={ev.get('error_flag','UNKNOWN')}\"",
 "                decision=e.get('decision_v1',{})\n                suffix=f\" | decision={decision.get('outcome')} reason={decision.get('reason')} body={ev.get('body_recovery','NOT_ASSESSED')} flag={ev.get('error_flag','UNKNOWN')}\"")
replace('risu_analyze.py',
 "            lines.append('Evidence calibrated: '+str(r['evidence_summary']))",
 "            lines.append('Evidence calibrated: '+str(r['evidence_summary']))\n            lines.append('Decision: '+str(r['decision_summary']))")
replace('risu_analyze.py',
 "        return int(args.fail_on_loss and any(e['verdict'] not in ('PRESERVED','NOT_APPLICABLE') for e in r['results']))",
 "        from risu_decision import any_blocking\n        return int(args.fail_on_loss and any_blocking(r,fail_review=args.fail_on_review))")

# SARIF: one actionable finding per non-PASS case, with the same severity as
# JSON, plain-text, CLI, and Markdown. No redundant conflicting legacy errors.
section('risu_report.py','def to_sarif(', 'def to_markdown(', """def to_sarif(report: dict, *, case_file: str='risu-probe.json') -> dict:
    from risu_decision import decide
    spec={
        'FAIL':('RISU201','Verified contract failure','error'),
        'REVIEW':('RISU202','Potential compatibility problem requires review','warning'),
        'DEFERRED':('RISU203','MCP tool is awaiting input','note'),
    }
    rules=[{'id':code,'name':state,'shortDescription':{'text':title},
            'defaultConfiguration':{'level':level}}
           for state,(code,title,level) in spec.items()]
    findings=[]
    for item in report.get('results',[]):
        decision=item.get('decision_v1') or decide(item,report.get('decision_policy','calibrated'))
        state=decision['outcome']
        if state not in spec:continue
        code,_,level=spec[state]
        finding={'ruleId':code,'level':level,
                 'message':{'text':f"{item.get('id','?')}: {state} ({decision['reason']}); legacy={item.get('verdict','unknown')}"},
                 'locations':[{'physicalLocation':{'artifactLocation':{'uri':case_file}}}],
                 'properties':{'caseId':item.get('id'),'decision':state,
                               'decisionReason':decision['reason'],
                               'legacyVerdict':item.get('verdict'),
                               'bodyRecovery':decision['body_recovery'],
                               'machineCarrier':decision['machine_carrier'],
                               'locationKind':'test-definition-only'}}
        if item.get('baseline') in ('known','new'):
            finding['baselineState']='unchanged' if item['baseline']=='known' else 'new'
        findings.append(finding)
    return {'version':'2.1.0',
            '$schema':'https://json.schemastore.org/sarif-2.1.0.json',
            'runs':[{'tool':{'driver':{'name':'RISU Probe',
                                      'version':report.get('version','unknown'),
                                      'informationUri':'https://github.com/risu-research/openapi-mcp-problem-semantics',
                                      'rules':rules}},
                     'results':findings}]}""")
section('risu_report.py','def to_markdown(', 'def emit(', """def to_markdown(report: dict) -> str:
    from risu_decision import decide
    lines=['# RISU Probe report','',
           '| Case | Decision | Legacy verdict | Body evidence | Reason |',
           '| --- | --- | --- | --- | --- |']
    esc=lambda value:str(value).replace('|',r'\\|').replace('\\n',' ')
    for item in report.get('results',[]):
        d=item.get('decision_v1') or decide(item,report.get('decision_policy','calibrated'))
        tag=(' [known]' if item.get('baseline')=='known' else
             ' [new]' if item.get('baseline')=='new' else '')
        lines.append(f"| {esc(item.get('id','?'))} | {d['outcome']}{tag} | {esc(item.get('verdict','?'))} | {d['body_recovery']} | {d['reason']} |")
    lines.extend(['','Policy: '+str(report.get('decision_policy','calibrated')),
                  'Decisions: '+str(report.get('decision_summary',{})),
                  'Cases checked: '+str(len(report.get('results',[]))),
                  '', '> Legacy carrier findings are independent of calibrated claims about body loss. No raw API bodies are included.'])
    return '\\n'.join(lines)+'\\n'""")

# Existing synthetic CNOE fixture keeps original strict-fidelity evidence,
# but exports decisions so CI gates never infer body deletion from legacy LOSS.
replace('risu_verify.py',
 "                                'evidence_v1':row.get('evidence_v1')})",
 "                                'evidence_v1':row.get('evidence_v1'),\n                                'decision_v1':row.get('decision_v1')})")
replace('risu_verify.py',
 "    p.add_argument('--fail-on-loss',action='store_true',help='opt-in CI failure when dynamic fixture confirms data loss')",
 "    p.add_argument('--fail-on-loss',action='store_true',help='CI fail on calibrated actual failures')\n    p.add_argument('--fail-on-review',action='store_true',help='optionally block review findings')")
replace('risu_verify.py',
 "        return 1 if a.fail_on_loss and report['status']=='CORROBORATED_BEHAVIOR' else 0",
 "        from risu_decision import any_blocking\n        return int(a.fail_on_loss and any_blocking({'results':report.get('evaluations',[])},\n                                                   fail_review=a.fail_on_review))")

replace('risu_onboarding.py',"'0.9.3-experimental'","'0.9.4-experimental'")
replace('risu_static.py',"'0.7.0-experimental'","'0.9.4-experimental'")
replace('risu_static.py',"'version':'0.7.0'","'version':'0.9.4'")
replace('pyproject.toml','0.9.3.dev0','0.9.4.dev0')
replace('pyproject.toml','"risu_onboarding", "risu_evidence"',
        '"risu_onboarding", "risu_evidence", "risu_decision", "risu_witness"')

print('RISU P0+Witness v0.9.4 SHA-pinned upgrade complete')
for n in ('risu_probe.py','risu_analyze.py','risu_verify.py','risu_report.py',
          'risu_decision.py','risu_witness.py','pyproject.toml'):
    print(n,hashlib.sha256((SOURCE/n).read_bytes()).hexdigest())
