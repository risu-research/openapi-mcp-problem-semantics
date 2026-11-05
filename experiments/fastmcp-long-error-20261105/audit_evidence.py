#!/usr/bin/env python3
"""Independent, fail-closed check for recorded FastMCP experiment.

This audits SDK-decoded CallToolResult JSON, not original JSON-RPC wire bytes.
The assumptions about boundary loss are pinned to FastMCP 4.1.6.
"""
import copy
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CANARY = 'RISU_TAIL_CANARY_9f62b7c5_END'
IDS = ['boundary-999','boundary-1000','boundary-1001','boundary-1600',
       'boundary-5000','validation-40','unicode-1600','success']
MARKER = '… (truncated)'

def digest(o):
    raw=json.dumps(o,sort_keys=True,ensure_ascii=False,separators=(',',':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()

def source_json(o):
    return json.dumps(o,ensure_ascii=False)

def text_content(w):
    return '\n'.join(x.get('text','') for x in w.get('content',[]) if x.get('type')=='text')

def machine_objects(w):
    result=[]
    if 'structuredContent' in w: result.append(w['structuredContent'])
    for x in w.get('content',[]):
        if x.get('type')!='resource': continue
        res=x.get('resource') or {}
        mt=str(res.get('mimeType') or '').split(';')[0].lower()
        if mt!='application/problem+json': continue
        try: result.append(json.loads(res['text']))
        except (ValueError,KeyError,TypeError): pass
    return result

def audit(report):
    errors=[]
    def test(condition, message):
        if not condition: errors.append(message)
    test(report.get('status')=='EXECUTED','expected executed real MCP integration')
    test(report.get('synthetic_localhost') is True,'expected synthetic localhost only')
    test(report.get('versions')=={'mcp':'2.3.0','fastmcp':'4.1.6','fastmcp-slim':'4.1.6'},'version mismatch')
    targets={t.get('target'):t for t in report.get('targets',[])}
    test(set(targets)=={'fastmcp4','sdk2_control'},'wrong target set')
    by={}
    for name in ('fastmcp4','sdk2_control'):
        if name not in targets: continue
        t=targets[name]
        test(t.get('protocol_version')=='2026-07-28',name+': protocol mismatch')
        cases=t.get('cases',[])
        test([c.get('case') for c in cases]==IDS,name+': incomplete or reordered case list')
        by[name]={c.get('case'):c for c in cases}
        for case in cases:
            cid=case['case']; label=name+'/'+cid
            src=case.get('upstream',{}); w=case.get('mcp_wire',{})
            test(digest(src)==case.get('upstream_sha256'),label+': HTTP sample digest mismatch')
            test(digest(w)==case.get('mcp_sha256'),label+': MCP result digest mismatch')
            body=src.get('body')
            if not isinstance(body,dict):
                errors.append(label+': source body missing');continue
            ok=cid=='success'
            test(src.get('status')==(200 if ok else 422 if cid=='validation-40' else 409),label+': source status mismatch')
            test(src.get('content_type')==('application/json' if ok else 'application/problem+json'),label+': source MIME mismatch')
            serial=source_json(body)
            obs=case.get('observation',{})
            test(obs.get('source_json_chars')==len(serial),label+': JSON char count differs')
            test(obs.get('source_utf8_bytes')==len(serial.encode('utf-8')),label+': UTF-8 byte count differs')
            full=any(x==body for x in machine_objects(w))
            test(obs.get('machine_exact') is full,label+': machine observation incorrect')
            test(w.get('isError') is (not ok),label+': wrong isError')
            if not ok: test(body.get('critical_tail')==CANARY,label+': source canary missing')
            if name=='sdk2_control':
                test(full,label+': positive control lost source object')
                meta=(w.get('_meta') or {}).get('org.risu.reference.source_http',{})
                test(meta.get('observed_http_status')==src['status'],label+': control lost observed HTTP status')
            elif ok:
                test(full,label+': success should remain structured')
            else:
                txt=text_content(w)
                test(not full,label+': FastMCP unexpectedly preserved machine object')
                if len(serial)<=1000:
                    test(serial in txt,label+': untruncated body missing')
                    test(MARKER not in txt,label+': spurious truncation marker')
                else:
                    test(serial[:1000]+MARKER in txt,label+': exact Python-character prefix+marker missing')
                    test(serial not in txt,label+': full source JSON unexpectedly present')
                test((CANARY in txt)==obs.get('tail_canary_in_text'),label+': tail observation disagreement')
                if len(serial)>=1600: test(CANARY not in txt,label+': long body tail unexpectedly present')
    if len(by)==2:
        for cid in IDS:
            test(by['fastmcp4'][cid]['upstream']==by['sdk2_control'][cid]['upstream'],cid+': divergent source samples')
    details={}
    if 'fastmcp4' in by and 'validation-40' in by['fastmcp4']:
        row=by['fastmcp4']['validation-40']
        txt=text_content(row['mcp_wire'])
        found=sorted(set(map(int,re.findall(r'#/items/(\d+)/quantity',txt))))
        source=sorted(set(int(x['pointer'].split('/')[2]) for x in row['upstream']['body']['errors']))
        test(source==list(range(40)),'source 40-item population invalid')
        test(found==list(range(12)),'observed 12-item population changed')
        details={'source_pointer_count':len(source),'visible_complete_pointer_ids':found,
                 'missing_complete_pointer_count':len(set(source)-set(found)),
                 'partial_next_entry':txt.endswith('{"po'+MARKER)}
    return {'verdict':'PASS' if not errors else 'FAIL','errors':errors,'validation':details,
            'scope':'SDK-parsed and reserialized CallToolResult; synthetic localhost; not raw JSON-RPC bytes'}

def adversarial_controls(original):
    outcomes={}
    def run_mutation(key,mutator):
        obj=copy.deepcopy(original);mutator(obj)
        outcomes[key]=audit(obj)['verdict']=='FAIL'
    run_mutation('source_body_changed',lambda r:r['targets'][0]['cases'][0]['upstream']['body'].__setitem__('title','corrupted'))
    def corrupt_wire(r):
        c=r['targets'][0]['cases'][3]
        c['mcp_wire']['content'][0]['text']='corrupted with recomputed hash'
        c['mcp_sha256']=digest(c['mcp_wire'])
    run_mutation('wire_changed_and_rehashed',corrupt_wire)
    def drop_control(r):
        c=r['targets'][1]['cases'][3]
        c['mcp_wire']['content']=[{'type':'text','text':'content dropped'}]
        c['mcp_sha256']=digest(c['mcp_wire'])
    run_mutation('control_changed_and_rehashed',drop_control)
    return outcomes

def main():
    p=HERE/'results'/'evidence.json'
    r=json.loads(p.read_text(encoding='utf-8'))
    a=audit(r)
    a['adversarial_controls']=adversarial_controls(r)
    if not all(a['adversarial_controls'].values()):
        a['errors'].append('Auditor did not detect a deliberate mutation')
        a['verdict']='FAIL'
    out=HERE/'results'/'AUDIT.json'
    out.write_text(json.dumps(a,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(a,indent=2,ensure_ascii=False))
    if a['verdict']!='PASS':raise SystemExit(2)

if __name__=='__main__':main()
