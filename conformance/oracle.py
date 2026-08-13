#!/usr/bin/env python3
import argparse, copy, json
from pathlib import Path

ABOUT_BLANK = 'about:blank'


def is_problem(source):
    return source.get('content_type','').split(';',1)[0].strip().lower() == 'application/problem+json'


def get_path(obj, path):
    cur=obj
    for p in path:
        if not isinstance(cur, dict) or p not in cur: return None, False
        cur=cur[p]
    return cur, True


def body_from_obs(obs):
    m=obs.get('machine',{})
    if m.get('semantic_type') == 'rfc9457-problem':
        return m.get('body') if isinstance(m.get('body'),dict) else None
    return None


def effective_type(obs):
    b=body_from_obs(obs)
    if b is None: return None
    return b.get('type', ABOUT_BLANK)


def single_source(case):
    return {k: copy.deepcopy(case[k]) for k in ('http_status','content_type','content_language','body') if k in case}


def reference_translate(source):
    # Representation-neutral reference witness: preserve the typed source envelope.
    if is_problem(source):
        return {'machine': {'semantic_type':'rfc9457-problem','observed_http_status':source['http_status'],'content_type':source['content_type'],'body':copy.deepcopy(source['body'])}, 'diagnostic': None, 'claims': {}}
    return {'machine': {'semantic_type':'generic-http-json','observed_http_status':source['http_status'],'content_type':source.get('content_type'),'body':copy.deepcopy(source.get('body'))}, 'diagnostic': None, 'claims': {}}


def fastmcp_translate(source):
    # Pinned source witness: non-2xx JSON becomes diagnostic prose before the MCP result boundary.
    reason = {400:'Bad Request',403:'Forbidden',409:'Conflict',422:'Unprocessable Entity',429:'Too Many Requests',502:'Bad Gateway',503:'Service Unavailable'}.get(source['http_status'],'Error')
    return {'machine': {}, 'diagnostic': f"HTTP error {source['http_status']}: {reason} - {source.get('body')!r}", 'claims': {}}


def cnoe_translate(source):
    # Client template temporarily keeps `details`; generated tool template drops it.
    body=source.get('body') or {}
    msg=f"API request failed: {source['http_status']}"
    if isinstance(body,dict):
        if 'error' in body: msg += f" - {body['error']}"
        elif 'message' in body: msg += f" - {body['message']}"
    return {'machine': {'error': msg}, 'diagnostic': msg, 'claims': {}}


def openapi_to_mcp_translate(source):
    status=source['http_status']; body=source.get('body') or {}
    api_message = body.get('message') or body.get('detail') or f'HTTP {status}' if isinstance(body,dict) else f'HTTP {status}'
    if status==400: code, retry='api_bad_request',False
    elif status in (401,403): code,retry='api_authorization_failed',False
    elif status==404: code,retry='api_resource_not_found',False
    elif status==408: code,retry='api_request_timeout',True
    elif status==429: code,retry='api_rate_limited',True
    elif status in (500,502,503,504): code,retry='api_server_error',True
    else: code,retry='api_request_failed', status>=500
    meta={'code':code,'source':'upstream','retryable':retry,'httpStatus':status}
    return {'machine': {'error_meta': meta}, 'diagnostic': str(api_message), 'claims': {'retryable_true': retry} if retry else {}}

TRANSLATORS={'reference-lossless':reference_translate,'fastmcp-openapi-source-witness':fastmcp_translate,'cnoe-codegen-source-witness':cnoe_translate,'openapi-to-mcp-source-witness':openapi_to_mcp_translate}


def translate_case(case, fn):
    if 'pair' in case:
        return [fn(x) for x in case['pair']]
    return fn(single_source(case))


def check_case(case, ex, observation):
    losses=[]; inventions=[]
    if ex.get('expected_scope')=='NOT_APPLICABLE':
        obs_list=observation if isinstance(observation,list) else [observation]
        if any(o.get('machine',{}).get('semantic_type')=='rfc9457-problem' for o in obs_list):
            inventions.append('rfc9457_recognition')
        return {'verdict':'INVENTED' if inventions else 'NOT_APPLICABLE','losses':losses,'inventions':inventions}

    for chk in ex.get('checks',[]):
        k=chk['kind']
        if k=='problem_type':
            if effective_type(observation)!=chk['value']: losses.append(f"problem_type:{chk['value']}")
        elif k=='effective_problem_type':
            if effective_type(observation)!=chk['value']: losses.append(f"effective_problem_type:{chk['value']}")
        elif k=='instance':
            b=body_from_obs(observation); v=(b or {}).get('instance')
            if v!=chk['value']: losses.append(f"instance:{chk['value']}")
        elif k=='extension_path':
            b=body_from_obs(observation); v,ok=get_path(b or {},chk['path'])
            if (not ok) or v!=chk['value']: losses.append('extension:'+'.'.join(chk['path']))
        elif k=='detail':
            b=body_from_obs(observation); v=(b or {}).get('detail')
            if v!=chk['value']: losses.append('detail')
        elif k=='body_status':
            b=body_from_obs(observation); v=(b or {}).get('status')
            if v!=chk['value']: losses.append(f"body_status:{chk['value']}")
        elif k=='observed_status':
            m=observation.get('machine',{}); v=m.get('observed_http_status',m.get('error_meta',{}).get('httpStatus'))
            if v!=chk['value']: losses.append(f"observed_status:{chk['value']}")
        elif k=='statuses_distinct':
            b=body_from_obs(observation) or {}; m=observation.get('machine',{})
            observed=m.get('observed_http_status',m.get('error_meta',{}).get('httpStatus'))
            if b.get('status') is None or observed is None or b.get('status')==observed: losses.append('distinct_origin_and_observed_status')
        elif k=='pair_distinct_problem_types':
            if not isinstance(observation,list) or [effective_type(x) for x in observation] != chk['values']: losses.append('pair_distinct_problem_types')
        elif k=='pair_same_problem_type':
            if not isinstance(observation,list) or [effective_type(x) for x in observation] != [chk['value'],chk['value']]: losses.append('pair_same_problem_type')

    obs_list=observation if isinstance(observation,list) else [observation]
    for f in ex.get('forbid',[]):
        if f=='custom_problem_type':
            for o in obs_list:
                t=effective_type(o)
                if t not in (None,ABOUT_BLANK): inventions.append(f)
        elif f=='rfc9457_recognition':
            if any(o.get('machine',{}).get('semantic_type')=='rfc9457-problem' for o in obs_list): inventions.append(f)
        elif f=='retry_after_from_prose':
            if any('retryAfterMs' in json.dumps(o.get('machine',{})) for o in obs_list): inventions.append(f)
        else:
            if any(o.get('claims',{}).get(f) for o in obs_list): inventions.append(f)

    verdict='PRESERVED'
    if losses and inventions: verdict='LOSS+INVENTED'
    elif losses: verdict='LOSS'
    elif inventions: verdict='INVENTED'
    return {'verdict':verdict,'losses':losses,'inventions':inventions}


def run(cases_path, exec_path):
    corpus=json.loads(Path(cases_path).read_text())
    exmap={x['id']:x for x in json.loads(Path(exec_path).read_text())['cases']}
    reports={}
    for name,fn in TRANSLATORS.items():
        rows=[]
        for case in corpus['cases']:
            obs=translate_case(case,fn)
            res=check_case(case,exmap[case['id']],obs)
            rows.append({'id':case['id'],**res,'observation':obs})
        applicable=[r for r in rows if r['verdict']!='NOT_APPLICABLE']
        reports[name]={
            'summary':{
                'preserved':sum(r['verdict']=='PRESERVED' for r in applicable),
                'loss':sum('LOSS' in r['verdict'] for r in applicable),
                'invented':sum('INVENTED' in r['verdict'] for r in applicable),
                'not_applicable':sum(r['verdict']=='NOT_APPLICABLE' for r in rows),
                'conformant':all(r['verdict'] in ('PRESERVED','NOT_APPLICABLE') for r in rows)
            },
            'cases':rows
        }
    return {'profile':'OpenAPI→MCP Problem-Semantics Preservation Profile','oracle_version':'v0.1','reports':reports}

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--cases',default='cases.json'); p.add_argument('--expectations',default='cases.executable.json'); p.add_argument('--out',default='results.json')
    a=p.parse_args(); report=run(a.cases,a.expectations); Path(a.out).write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    for name,r in report['reports'].items():
        s=r['summary']; print(f"{name}: preserved={s['preserved']} loss={s['loss']} invented={s['invented']} n/a={s['not_applicable']} conformant={s['conformant']}")
