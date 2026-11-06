"""Three independent OpenAPI-to-MCP implementations, one controlled local fixture.

Safety contract: only the fixed /orders/{id} GET on 127.0.0.1, synthetic payloads,
zero real credentials, exact pinned upstream commits, no network during execution.
Report contains hashes and diagnostic summaries, never raw server response bodies.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from threading import Thread

PRODUCT=Path('/opt/risu/product')
sys.path.insert(0,str(PRODUCT))
from risu_probe import compare, VERSION
from risu_evidence import assess as calibrated_assess
from risu_witness import witness
from risu_analyze import analyze
from risu_collect import capture, digest
from risu_verify import _server, prepare, verify_fixture

BASE=Path('/opt/risu')
RESULTS=Path('/results')
REPO_SHA={'cnoe':'8c2b065497cf32ecbb7cf7e28dad3a99c6706c3f',
          'mcpgen':'30ee7cb9c2e923ce901e788b0d911f6547772866'}
EXPECTED={200:'PRESERVED',400:'LOSS',409:'LOSS',422:'LOSS'}
ALLOWED_PROJECTS={'cnoe','fastmcp','mcpgen'}

def run(command, *,env=None,cwd=None,timeout=120):
    r=subprocess.run(command,env=env,cwd=cwd,capture_output=True,text=True,timeout=timeout)
    if r.returncode:
        raise RuntimeError(f"command {Path(command[0]).name} exited {r.returncode}; stdout={r.stdout[-2500:]}; stderr={r.stderr[-4000:]}")
    return r.stdout

def boot_diagnostic(name,cmd,env):
    """Synthetic server-only preflight. Captures stderr only on early boot failure."""
    p=subprocess.Popen(cmd,env=env,cwd='/tmp',stdin=subprocess.PIPE,
                       stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                       text=True)
    try:
        time.sleep(2)
        if p.poll() is not None:
            out,err=p.communicate(timeout=3)
            raise RuntimeError(f'{name} MCP server EXITED BEFORE INITIALIZE: '
                               f'exit={p.returncode}, stderr={err[-4500:]}, stdout={out[-900:]}')
    finally:
        if p.poll() is None:
            p.terminate()
            try:p.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill();p.communicate(timeout=3)

def interpreter_env(python_path=None, *, base=None,root=None):
    allowed=('PATH','HOME','TMP','TEMP','TMPDIR','LANG','LC_ALL','SYSTEMROOT','WINDIR','USERPROFILE')
    env={k:os.environ[k] for k in allowed if k in os.environ}
    env['HOME']='/tmp'
    env['TMPDIR']='/tmp'
    env['PYTHONUNBUFFERED']='1'
    env['PYTHONDONTWRITEBYTECODE']='1'
    env['PYTHON_DOTENV_DISABLED']='1'
    env['XDG_CACHE_HOME']='/tmp/cache'
    env['RUFF_CACHE_DIR']='/tmp/ruff-cache'
    env['PYTHONPATH']='/opt/risu/product'
    if base:env['API_BASE_URL']=base
    if root:env['PYTHONPATH']=str(root)
    return env

def create_spec(root):
    spec={
        'openapi':'3.1.0','info':{'title':'Risucheck API','version':'1.0.0'},
        'paths':{'/orders/{id}':{'get':{
           'operationId':'get_order','summary':'Read one synthetic order',
           'parameters':[{'name':'id','in':'path','required':True,
                          'schema':{'type':'string'}}],
           'responses':{str(n):{'description':'synthetic fixture',
             'content':{mime:{'schema':{'type':'object'}}}}
             for n,mime in ((200,'application/json'),(400,'application/json'),
                             (409,'application/problem+json'),(422,'application/problem+json'))}
        }}}
    }
    root.mkdir(parents=True,exist_ok=True)
    (root/'openapi.json').write_text(json.dumps(spec,indent=2)+'\n',encoding='utf-8')
    (root/'config.yaml').write_text(
        "title: risucheck\n"
        "description: Read-only synthetic fixture\n"
        "author: RISU Institute\nversion: 0.0.0\nlicense: Apache-2.0\n"
        "python_version: 3.13\nheaders:\n  Accept: application/json\n"
        "poetry_dependencies: |\n"
        '  python = ">=3.13,<4.0"\n'
        '  httpx = ">=0.24.0"\n'
        '  python-dotenv = ">=1.0.0"\n'
        '  pydantic = ">=2.0.0"\n'
        '  mcp = ">=1.9.0"\n',encoding='utf-8')
    return spec

def generate_cnoe(inp,out):
    run(['/opt/cnoe/bin/python','-m','openapi_mcp_codegen',
         '--spec-file',str(inp/'openapi.json'),'--output-dir',str(out),
         '--log-level','warning'],env=interpreter_env(),cwd=inp,timeout=150)
    (out/'openapi.json').write_bytes((inp/'openapi.json').read_bytes())
    assert (out/'mcp_risucheck'/'server.py').is_file()
    return out

def git_head(repo):
    return run(['git','-c',f'safe.directory={repo}','-C',repo,'rev-parse','HEAD'],timeout=10).strip()

def safe_controls(prep):
    positives={}
    for path,source in prep['source_cases'].items():
        n=source['status']
        mcp={'isError':n>=400,'structuredContent':source['body'],
             '_meta':{'observed_http_status':n},'content':[]}
        result=compare(source,mcp,'control-'+str(n),error_profile='json-errors')
        assert result['verdict']=='PRESERVED',(n,result)
        assert result['evidence_v1']['body_recovery']=='EXACT_MACHINE',(n,result)
        text_positive={'content':[{'type':'text','text':json.dumps(source['body'])}],
                       'isError':n>=400,'_meta':{'observed_http_status':n}}
        assert calibrated_assess(source,text_positive)['body_recovery']=='EXACT_JSON_TEXT'
        positives[str(n)]=result['verdict']
    assert set(positives)=={'200','400','409','422'}
    return positives

def evaluate_result(adapter,matrix,expected_paths,counters,unexpected,elapsed):
    assert not matrix['failures'],(adapter,matrix['failures'])
    assert matrix['captured_cases']==len(expected_paths)==4,adapter
    assert not unexpected,(adapter,unexpected)
    assert all(counters[x]==3 for x in expected_paths),(adapter,counters)
    report=analyze({'targets':matrix['targets']},profile='json-errors')
    source_by_id={r['check']['id']:r['source_sample'] for r in matrix['targets'][0]['checks']}
    items=[]
    meaningful=0
    metamorphic_rejections=0
    for row in report['results']:
        source=source_by_id[row['id']]
        status=source['status']
        loss=row['verdict'] in ('LOSS','LOSS_AND_INVENTED')
        meaningful+=int(loss)
        rec=next(r for r in matrix['targets'][0]['checks'] if r['check']['id']==row['id'])
        ev=row.get('evidence_v1')
        decision=row.get('decision_v1')
        assert decision and decision['schema']=='risu-decision-v1',(adapter,row)
        assert ev and ev['schema']=='risu-evidence-v1' and ev['scope']=='FULL_JSON_BODY',(adapter,row)
        altered=json.loads(json.dumps(source))
        body=altered['body']
        carrier=body if 'risu_fixture_marker' in body else body.get('details',{})
        assert isinstance(carrier,dict) and 'risu_fixture_marker' in carrier,(adapter,status)
        carrier['risu_fixture_marker']='RISU_COUNTERFACTUAL_NOT_PRESENT'
        rejected=calibrated_assess(altered,rec['mcp_sample'])
        assert rejected['body_recovery'] not in ('EXACT_MACHINE','EXACT_JSON_TEXT'),(adapter,status,rejected)
        metamorphic_rejections+=1
        proof=witness(source,rec['mcp_sample'],['/id'] if status==200 else ['/status'])
        assert proof['schema']=='risu-consumer-witness-v1'
        if adapter=='mcpgen':
            assert proof['models']['structured-only']['outcome']=='FAIL'
            assert proof['models']['json-text-data']['outcome']=='PASS'
            assert decision['outcome']=='REVIEW'
            assert ev['body_recovery']=='EXACT_JSON_TEXT',(adapter,status,ev)
            assert ev.get('envelope_path')=='/data',(adapter,status,ev)
            assert ev['http_status']=='TEXT_STATUS_RECOVERABLE',(adapter,status,ev)
        if adapter=='fastmcp' and status==200:
            assert ev['body_recovery']=='EXACT_MACHINE',(adapter,status,ev)
        items.append({'id':row['id'],'status':status,'verdict':row['verdict'],
                      'diagnostic_codes':sorted(set(x['code'] for x in row.get('diagnostics',[]))),
                      'losses':row.get('losses',[])[:5],
                      'evidence_v1':ev,'decision_v1':decision,'witness_v1':proof,
                      'source_sha256':rec['source_sha256'],'mcp_sha256':rec['mcp_sha256']})
    assert sorted(x['status'] for x in items)==[200,400,409,422],adapter
    assert meaningful>0,'No meaningful loss detection on selected target'
    assert elapsed<600,(adapter,elapsed)
    return {'project':adapter,'execution':'REAL_LOCALHOST_HTTP_AND_EXTERNAL_MCP',
            'version':VERSION,'seconds_after_dependencies_ready':round(elapsed,3),
            'cases':sorted(items,key=lambda x:x['status']),
            'observed_loss_count':meaningful,'counterfactual_rejections':metamorphic_rejections,
            'http_get_count':sum(counters.values()),
            'unexpected_http_requests':len(unexpected),
            'first_diagnosis_under_ten_minutes_after_dependencies_ready':True}

def main():
    os.chdir('/tmp')
    assert VERSION=='0.9.4-experimental',VERSION
    assert git_head('/opt/cnoe-source')==REPO_SHA['cnoe']
    assert git_head('/opt/mcpgen-source')==REPO_SHA['mcpgen']
    RESULTS.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='risu-triad-',dir='/tmp') as tmp:
        root=Path(tmp); inp=root/'input'; generated=root/'cnoe'
        spec=create_spec(inp)
        gen_start=time.monotonic()
        generate_cnoe(inp,generated)
        prep=prepare(generated)
        control=safe_controls(prep)
        # This same deterministic CNOE-generated specimen anchors all 3 observations.
        planned_statuses={item['status'] for item in prep['source_cases'].values()}
        assert planned_statuses==set(EXPECTED)
        results=[]
        cnoe_start=time.monotonic()
        cnoe=verify_fixture(generated,python='/opt/cnoe/bin/python',allow_exec=True)
        cnoe_elapsed=time.monotonic()-cnoe_start+(cnoe_start-gen_start)
        assert cnoe['status']=='CORROBORATED_BEHAVIOR' and cnoe['counts']['unexpected_requests']==0
        assert cnoe['counts']['fixture_gets']==12 and cnoe['positive_control']=='PRESERVED'
        cnoe_witness={r['check']['id']:witness(r['source_sample'],r['mcp_sample'],
                                               ['/id'] if r['source_sample']['status']==200 else ['/status'])
                      for r in cnoe['matrix']['targets'][0]['checks']}
        results.append({'project':'cnoe','execution':'REAL_LOCALHOST_HTTP_AND_EXTERNAL_MCP',
                        'version':VERSION,
                        'seconds_after_dependencies_ready':round(cnoe_elapsed,3),
                        'cases':[{'id':x['id'],'status':x['http_status'],'verdict':x['verdict'],
                                  'evidence_v1':x['evidence_v1'],
                                  'decision_v1':x['decision_v1'],
                                  'witness_v1':cnoe_witness[x['id']],
                                  'diagnostic_codes':x['diagnostic_codes']}
                                  for x in cnoe['evaluations']],
                        'observed_loss_count':cnoe['counts']['error_losses'],
                        'counterfactual_rejections':cnoe['counts']['counterfactual_rejections'],
                        'http_get_count':12,'unexpected_http_requests':0,
                        'first_diagnosis_under_ten_minutes_after_dependencies_ready':cnoe_elapsed<600})
        assert cnoe_elapsed<600
        paths=prep['source_cases'];cases=[{
            'id':'triad-'+str(src['status']),
            'source':{'method':'GET','path':path},
            'tool':'get_order',
            'arguments':{'id':path.split('/')[-1]},
        } for path,src in paths.items()]
        assert len(cases)==4 and all(c['source']['path'].startswith('/orders/risu-fixture-') for c in cases)
        for name,mode in (('fastmcp','modern'),('mcpgen','legacy')):
            started=time.monotonic()
            counters=Counter();unexpected=[]
            http=_server(paths,counters,unexpected)
            t=Thread(target=http.serve_forever,daemon=True);t.start()
            base=f'http://127.0.0.1:{http.server_port}'
            try:
                if name=='fastmcp':
                    script=BASE/'triad'/'fastmcp_openapi_server.py'
                    cmd=['/opt/fastmcp/bin/python','-u',str(script),str(inp/'openapi.json'),base]
                    env=interpreter_env(base=base)
                else:
                    config=root/'mcpgen-config.yaml'
                    config.write_text(
                        'max_tools: 5\nallowed_methods:\n  - GET\n'
                        f'api_base_url: {base}\nexecution_mode: safe-execute\n'
                        'routing_mode: keyword\naudit_enabled: false\nmetrics_enabled: false\n'
                        'auth:\n  mode: none\nrate_limit:\n  enabled: false\n'
                        'mock:\n  enabled: false\nfailure_injection:\n  enabled: false\n',
                        encoding='utf-8')
                    out=root/'mcpgen-generated'
                    run(['/opt/mcpgen/bin/mcpgen','generate','--from',str(inp/'openapi.json'),
                         '--config',str(config),'--mode','mcp','--output',str(out)],
                         env=interpreter_env(),timeout=90)
                    tools=json.loads((out/'tools.json').read_text())
                    assert [x['name'] for x in tools]==['get_order'],tools
                    cmd=['/opt/mcpgen/bin/python','-u',str(out/'server.py')]
                    env=interpreter_env(base=base)
                assert not counters and not unexpected,(name,'startup unexpectedly called HTTP')
                print('TRIAD_START',name,flush=True)
                boot_diagnostic(name,cmd,env)
                matrix=capture(cases,base,cmd,protocol=mode,recheck_source=True,
                               error_profile='json-errors',label=name,server_env=env)
                elapsed=time.monotonic()-started
                results.append(evaluate_result(name,matrix,paths,counters,unexpected,elapsed))
            finally:
                http.shutdown();http.server_close()
        calibrated_summary={}
        for project in results:
            for case in project['cases']:
                typ=case['evidence_v1']['body_recovery']
                calibrated_summary[typ]=calibrated_summary.get(typ,0)+1
        assert sum(calibrated_summary.values())==12
        decision_summary={}
        consumer_summary={reader:0 for reader in ('structured-only','json-text-data')}
        divergent=0
        for project in results:
            for case in project['cases']:
                state=case['decision_v1']['outcome']
                decision_summary[state]=decision_summary.get(state,0)+1
                proof=case['witness_v1']
                divergent+=int(proof['divergent_outcomes'])
                for reader in consumer_summary:
                    consumer_summary[reader]+=int(proof['models'][reader]['outcome']=='PASS')
        assert sum(decision_summary.values())==12
        assert divergent>=4
        assert consumer_summary['json-text-data']>=4
        assert sum(p['counterfactual_rejections'] for p in results)==12
        summary={'status':'PASS','fixture':'SYNTHETIC_GET_ONLY',
                 'network':'Docker --network none',
                 'original_product_sha256':hashlib.sha256((PRODUCT/'risu_probe.py').read_bytes()).hexdigest(),
                 'projects':results,'reference_controls':control,
                 'calibrated_summary':calibrated_summary,
                 'decision_summary':decision_summary,
                 'consumer_summary':consumer_summary,
                 'consumer_divergent_cases':divergent,
                 'counterfactual_rejections':sum(p['counterfactual_rejections'] for p in results),
                 'pinned_projects':{**REPO_SHA,'fastmcp':'4.1.6','mcp':'2.3.0'},
                 'claim_boundary':'Legacy LOSS refers to machine-carrier failures, not necessarily destroyed content. New evidence_v1 distinguishes exact JSON text recovery, flags and actual preview clipping.',
                 'evidence_privacy':'Only hashes, statuses, and limited loss descriptors exported; no raw bodies'}
        (RESULTS/'THREE_PROJECTS_SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
        for x in results:
            assert x['observed_loss_count']>0
        print('RISU_TRIAD_PASS',json.dumps({r['project']:{'seconds':r['seconds_after_dependencies_ready'],
                              'losses':r['observed_loss_count']} for r in results}))
if __name__=='__main__':
    main()
