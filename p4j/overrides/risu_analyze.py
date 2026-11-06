"""Analyze saved HTTP/MCP matrices from independent tools, without SDK dependencies."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from risu_report import emit


def _entries(payload):
    if isinstance(payload, dict) and isinstance(payload.get('targets'), list):
        for target in payload['targets']:
            label = str(target.get('target', 'unknown'))[:120]
            if isinstance(target.get('cases'),list):
                for row in target['cases']:
                    yield label, str(row['case'])[:120], row['upstream'],row['mcp_wire']
            elif isinstance(target.get('checks'),list):
                for row in target['checks']:
                    yield label,str(row['check']['id'])[:120], row['source_sample'],row['mcp_sample']
            else:
                raise ValueError('target must contain checks or cases')
    elif isinstance(payload, dict) and isinstance(payload.get('cases'),list):
        for row in payload['cases']:
            yield str(row.get('translator','unknown'))[:120],str(row['id'])[:120],row['source'],row['mcp']
    else:
        raise ValueError('expected a targets matrix or cases array; no real evidence is inferred')


def analyze(payload, profile='json-errors', policy='calibrated'):
    # Import here to let the CLI avoid creating multiple package entrypoints.
    from risu_probe import compare, VERSION, ProbeError
    from risu_decision import apply as apply_decisions
    rows=[]
    for target,case_id,src,mcp in _entries(payload):
        try:
            entry=compare(src,mcp,case_id,error_profile=profile)
        except ProbeError as exc:
            raise ValueError(f'malformed captured observation {target}/{case_id}: {exc}') from exc
        entry['target']=target
        rows.append(entry)
    if not rows or len(rows)>5000:
        raise ValueError('expected 1-5000 saved observations')
    summary={v:sum(x['verdict']==v for x in rows) for v in
             ('PRESERVED','LOSS','INVENTED','LOSS_AND_INVENTED','NOT_APPLICABLE','ERROR','INPUT_REQUIRED')}
    codes={}
    for row in rows:
        for d in row.get('diagnostics',[]):
            codes[d['code']]=codes.get(d['code'],0)+1
    evidence_summary={}
    action_summary={}
    for row in rows:
        evidence=row.get('evidence_v1') or {}
        recovery=evidence.get('body_recovery','NOT_ASSESSED')
        action=evidence.get('recommended_action','NONE')
        evidence_summary[recovery]=evidence_summary.get(recovery,0)+1
        action_summary[action]=action_summary.get(action,0)+1
    return apply_decisions({'tool':'RISU Probe','version':VERSION,'profile':profile,
            'evidence':'captured HTTP/MCP result pairs; no new upstream execution',
            'summary':summary,'diagnostic_summary':codes,
            'evidence_summary':evidence_summary,'action_summary':action_summary,'results':rows},policy)


def main(argv=None):
    p=argparse.ArgumentParser(description='Analyze saved HTTP-to-MCP matrices from multiple translators')
    p.add_argument('matrix',type=Path,help='matrix JSON from real captured calls; 10 MiB maximum')
    p.add_argument('--profile',choices=('problem-only','json-errors'),default='json-errors')
    p.add_argument('--format',choices=('json','text','markdown','sarif'),default='text')
    p.add_argument('--out',type=Path)
    p.add_argument('--recovery',action='store_true',help='include typed fields, text JSON recovery, missing errors and consumer observations (offline; no API calls)')
    p.add_argument('--causal-trust-store',type=Path,help='operator-selected trusted recorder public keys; must be outside the capture directory')
    p.add_argument('--fail-on-confirmed-loss',action='store_true',help='nonzero only when a trusted runtime witness confirms a loss')
    p.add_argument('--fail-on-loss',action='store_true')
    p.add_argument('--fail-on-review',action='store_true')
    p.add_argument('--policy',choices=('calibrated','strict-carrier'),default='calibrated')
    args=p.parse_args(argv)
    try:
        capture_metadata=None
        if args.matrix.is_dir():
            from risu_capture import load_capture_directory
            payload,capture_metadata=load_capture_directory(args.matrix)
            contents=None
        else:
            if args.matrix.stat().st_size > 10_000_000:
                raise ValueError('matrix exceeds 10 MB input limit')
            contents=args.matrix.read_text(encoding='utf-8')
        if contents is not None and args.recovery:
            from risu_recovery import reject_dupes
            def reject_constant(text):
                raise ValueError('nonfinite JSON constant rejected: '+text)
            payload=json.loads(contents,object_pairs_hook=reject_dupes,parse_constant=reject_constant)
        elif contents is not None:
            payload=json.loads(contents)
        r=analyze(payload,args.profile,args.policy)
        if capture_metadata is not None:
            r['capture_bridge_v1']=capture_metadata
        if args.causal_trust_store is not None and not args.matrix.is_dir():
            raise ValueError('trusted recorder evidence requires an original HAR/MCP capture directory')
        from risu_causality import gate as causal_gate
        r['causal_gate_v1']=causal_gate(r,payload,args.matrix if args.matrix.is_dir() else None,args.causal_trust_store)
        r['legacy_verdicts_are_not_causal_proof']=True
        if args.recovery:
            if args.format=='sarif':
                raise ValueError('--recovery is not supported with SARIF output; use --format json, text or markdown')
            from risu_recovery import analyze_saved
            r['recovery_v1']=analyze_saved(payload,r)
        if args.format=='json':
            rendered=json.dumps(r,ensure_ascii=False,indent=2)+'\n'
        elif args.format in ('markdown','sarif'):
            if args.format=='sarif' and args.matrix.is_dir():
                raise ValueError('native-capture SARIF requires proof-aware severity mapping and is disabled; use JSON or Markdown')
            rendered=emit(r,args.format,case_file=args.matrix.name)
            if capture_metadata is not None and args.format=='markdown':
                rendered+='\n*Input: native HAR + MCP JSON-RPC; pairing declared, not independently attested.*\n'
            if args.format=='markdown':
                from risu_causality import render_summary
                rendered+='\n## Causal evidence gate\n\n```text\n'+render_summary(r['causal_gate_v1'])+'```\n'
            if args.recovery and args.format=='markdown':
                from risu_recovery import render as render_recovery
                rendered+='\n## Recovery Lens (captured evidence only)\n\n```text\n'+render_recovery(r['recovery_v1'])+'```\n'
        else:
            lines=['RISU Probe differential observation (captured responses; no new live calls)']
            if capture_metadata is not None:
                lines.append('Native HAR/MCP capture: explicit pairing is user-declared and not independently attested.')
            for e in r['results']:
                codes=','.join(d['code'] for d in e.get('diagnostics',[]))
                ev=e.get('evidence_v1',{})
                decision=e.get('decision_v1',{})
                suffix=f" | decision={decision.get('outcome')} reason={decision.get('reason')} body={ev.get('body_recovery','NOT_ASSESSED')} flag={ev.get('error_flag','UNKNOWN')}"
                lines.append(f"{e['target']}/{e['id']}: {e['verdict']}"+(f' [{codes}]' if codes else '')+suffix)
            lines.append('Summary: '+str(r['summary']))
            lines.append('Diagnostics: '+str(r['diagnostic_summary']))
            lines.append('Evidence calibrated: '+str(r['evidence_summary']))
            lines.append('Decision (legacy P0; not independent causal proof): '+str(r['decision_summary']))
            from risu_causality import render_summary
            lines.extend(['',render_summary(r['causal_gate_v1']).rstrip('\n')])
            if args.recovery:
                from risu_recovery import render as render_recovery
                lines.extend(['',render_recovery(r['recovery_v1']).rstrip('\n')])
            rendered='\n'.join(lines)+'\n'
        if args.out:
            args.out.parent.mkdir(parents=True,exist_ok=True)
            args.out.write_text(rendered,encoding='utf-8')
        else:
            print(rendered,end='')
        from risu_decision import any_blocking
        if args.fail_on_confirmed_loss and r['causal_gate_v1']['summary']['CONFIRMED_LOSS']:
            return 1
        # Historical strict flag remains available; it may flag *conditional* loss.
        return int(args.fail_on_loss and any_blocking(r,fail_review=args.fail_on_review))
    except (OSError,ValueError,KeyError,TypeError,AssertionError) as e:
        print('RISU Probe analyze: '+str(e),file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())