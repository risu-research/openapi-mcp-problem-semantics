#!/usr/bin/env python3
from __future__ import annotations
import copy, json
from pathlib import Path
from carrier_neutral_adapter_v02 import raw_result_to_observation
from oracle import check_case
from reference_mapping_model import map_source_to_raw_call_tool_result

ROOT=Path(__file__).resolve().parent
corpus=json.loads((ROOT/'cases.json').read_text())
exmap={x['id']:x for x in json.loads((ROOT/'cases.executable.json').read_text())['cases']}

def source(c):
    return {k:copy.deepcopy(c[k]) for k in ('http_status','content_type','content_language','body') if k in c}

def evaluate_case(c):
    if 'pair' in c:
        obs=[]
        raws=[]
        for s in c['pair']:
            r=map_source_to_raw_call_tool_result(s); raws.append(r)
            obs.append(raw_result_to_observation(r,s))
    else:
        s=source(c); r=map_source_to_raw_call_tool_result(s); raws=r
        obs=raw_result_to_observation(r,s)
    return check_case(c,exmap[c['id']],obs), raws, obs

rows=[]
for c in corpus['cases']:
    verdict,raws,obs=evaluate_case(c)
    rows.append({'id':c['id'],**verdict,'raw':raws,'observation':obs})

assert [r['verdict'] for r in rows].count('PRESERVED') == 11, rows
assert [r['verdict'] for r in rows].count('NOT_APPLICABLE') == 1, rows
assert not any('LOSS' in r['verdict'] for r in rows), rows
assert not any('INVENTED' in r['verdict'] for r in rows), rows

# P11 must carry two distinct facts: body status=503 and observed transport=502.
p11=next(r for r in rows if r['id']=='P11-origin-status-survives-intermediary')
assert p11['observation']['machine']['body']['status']==503
assert p11['observation']['machine']['observed_http_status']==502

# P12 must not manufacture retryability.
p12=next(r for r in rows if r['id']=='P12-no-retryability-invention')
assert p12['observation']['claims']=={}

# Negative control: same P01 body demoted to plain TextContent must fail.
p01=next(c for c in corpus['cases'] if c['id']=='P01-explicit-type')
s=source(p01)
text_only={'content':[{'type':'text','text':json.dumps(s['body'])}], 'isError':True, '_meta':{'observed_http_status':s['http_status']}}
neg=check_case(p01,exmap[p01['id']],raw_result_to_observation(text_only,s))
assert neg['verdict']=='LOSS',neg

print('reference mapping model: PASS')
print('summary: preserved=11 loss=0 invented=0 n/a=1 conformant=True')
print('negative text-demotion control: PASS (LOSS)')
