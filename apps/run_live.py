"""Actual pinned SDK + generated MCPGen contract failure, shrinking, patch proof.

No credentials, production endpoints or LLM calls. Minimized counterexamples
are re-run through genuine generated MCPGen -> synthetic localhost HTTP.
"""
import copy
import difflib
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from threading import Thread
import time

sys.path.insert(0,'/opt/risu/product')
sys.path.insert(0,'/opt/risu/apps')
from risu_probe import MCPClient,VERSION
from risu_repair import promote_text_json,read_structured
from risu_fixverify import prepare_consumer_result
from fixverify_controls import test_controls
from risu_minimize import minimize,canonical
from risu_diagnostics import _strict_same
from risu_witness import witness
from real_contracts import CONTRACTS,classify_real_sdk,contract_source

OUT=Path('/results')
ROOT=Path('/opt/risu')
SHA={'mcpgen':'30ee7cb9c2e923ce901e788b0d911f6547772866',
     'pygithub':'5aeb43916b197a0fe8016600817b868fc894af5a',
     'stripe':'d97a68e28ec6553c3545fdf7e5322e871559cfdb'}

def cmd(args,*,env=None,timeout=180,cwd='/tmp'):
    p=subprocess.run(args,env=env,cwd=cwd,text=True,capture_output=True,timeout=timeout)
    if p.returncode:
        raise RuntimeError('command failed '+str(args[:3])+' '+p.stderr[-2200:])
    return p.stdout

def create_files(folder,base):
    paths={}
    for key,c in CONTRACTS.items():
        paths[c['path']]={'get':{
          'operationId':c['operation'],'summary':'Synthetic '+key,
          'responses':{str(c['status']):{
             'description':'Synthetic local SDK error',
             'content':{'application/json':{'schema':{'type':'object'}}}}}}}
    spec=folder/'openapi.json'
    spec.write_text(json.dumps({
       'openapi':'3.1.0','info':{'title':'RISU real SDK contract replay','version':'1.0'},
       'paths':paths},indent=2)+'\n',encoding='utf-8')
    config=folder/'config.yaml'
    config.write_text(
       'max_tools: 5\nallowed_methods:\n  - GET\n'+
       'api_base_url: '+base+'\nexecution_mode: safe-execute\n'+
       'routing_mode: keyword\naudit_enabled: false\nmetrics_enabled: false\n'+
       'auth:\n  mode: none\nrate_limit:\n  enabled: false\n'+
       'mock:\n  enabled: false\nfailure_injection:\n  enabled: false\n',
       encoding='utf-8')
    return spec,config

def start_server(lookup):
    ctr={'total':0,'unexpected':0}
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in lookup:
                ctr['unexpected']+=1;self.send_error(404);return
            ctr['total']+=1
            status,body=lookup[self.path]
            data=canonical(body).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(data)))
            self.end_headers();self.wfile.write(data)
        def do_POST(self):ctr['unexpected']+=1;self.send_error(405)
        def do_PUT(self):ctr['unexpected']+=1;self.send_error(405)
        def do_DELETE(self):ctr['unexpected']+=1;self.send_error(405)
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    Thread(target=server.serve_forever,daemon=True).start()
    return server,ctr

def first_envelope(mcp):
    from risu_evidence import _parse_json
    chunks=mcp.get('content') or []
    txt=next((x.get('text') for x in chunks
              if isinstance(x,dict) and x.get('type')=='text'),None)
    assert isinstance(txt,str) and len(txt)<=1000000
    root=_parse_json(txt)
    assert isinstance(root,dict) and type(root.get('status_code')) is int
    assert isinstance(root.get('data'),dict)
    return root

def variant_mcp(mcp,new_body):
    # A model of the already-observed MCPGen envelope, not a second live call.
    out=copy.deepcopy(mcp)
    original=first_envelope(mcp)
    original['data']=copy.deepcopy(new_body)
    for item in out['content']:
        if item.get('type')=='text':
            item['text']=canonical(original)
            break
    return out

def classify(contract,mcp,status):
    payload=read_structured(mcp)
    return classify_real_sdk(contract,payload if isinstance(payload,dict) else {},status)

def prove(contract,c,mcp):
    native=classify_real_sdk(contract,c['body'],c['status'])
    broken=classify(contract,mcp,c['status'])
    repaired=prepare_consumer_result(mcp)
    fixed=classify(contract,repaired,c['status'])
    assert native==c['expected'],(contract,'original SDK classification changed',native)
    assert broken!=native,(contract,'structured-only consumer unexpectedly succeeded')
    assert fixed==native,(contract,'repair did not restore native SDK decision',fixed)
    root=first_envelope(mcp)
    assert root['status_code']==c['status']
    assert _strict_same(root['data'],c['body'])
    w=witness(contract_source(c),mcp,[c['required_path']],
              require_error_flag=True,require_http_status=True)
    assert w['models']['structured-only']['outcome']=='FAIL'
    assert w['models']['json-text-data']['outcome']=='PASS'
    return native,broken,fixed,w

def bridge_files():
    old=("def payload(mcp):\n"
         "    return mcp.get('structuredContent') or {}\n")
    new=("from risu_fixverify import prepare_consumer_result\n"
         "from risu_repair import read_structured\n"
         "def payload(mcp):\n"
         "    normalized=prepare_consumer_result(mcp)\n"
         "    return read_structured(normalized) or {}\n")
    patch=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),
                       fromfile='consumer_bridge.py',tofile='consumer_bridge.py'))
    return old,new,patch

def bridge_classify(contract,txt,c,mcp):
    ns={}
    exec(compile(txt,'synthetic-bridge.py','exec'),ns)
    return classify_real_sdk(contract,ns['payload'](mcp),c['status'])

def main():
    assert VERSION=='0.9.6-experimental',VERSION
    os.chdir('/tmp')
    for key,path in [('mcpgen','/opt/mcpgen-source'),
                     ('pygithub','/opt/pygithub-source'),
                     ('stripe','/opt/stripe-source')]:
        head=cmd(['git','-c','safe.directory='+path,'-C',path,'rev-parse','HEAD']).strip()
        assert head==SHA[key],(key,head)
    for key,path,pin in (
      ('pygithub','/opt/pygithub-source/github/Requester.py',CONTRACTS['pygithub-404']['blob']),
      ('stripe','/opt/stripe-source/stripe/_api_requestor.py',CONTRACTS['stripe-rate-limit-400']['blob'])):
        base=str(Path(path).parent.parent)
        relative=str(Path(path).relative_to(base))
        assert cmd(['git','-c','safe.directory='+base,'-C',base,'hash-object',relative]).strip()==pin,key
    started=time.monotonic()
    OUT.mkdir(exist_ok=True)
    lookup={c['path']:(c['status'],copy.deepcopy(c['body'])) for c in CONTRACTS.values()}
    server,ctr=start_server(lookup)
    temp=Path(tempfile.mkdtemp(prefix='risu-app-repro-',dir='/tmp'))
    try:
        base='http://127.0.0.1:'+str(server.server_port)
        spec,config=create_files(temp,base)
        target=temp/'generated'
        cmd(['/opt/mcpgen/bin/mcpgen','generate','--from',str(spec),
             '--config',str(config),'--mode','mcp','--output',str(target)],timeout=90)
        found={x['name'] for x in json.loads((target/'tools.json').read_text())}
        assert found=={c['operation'] for c in CONTRACTS.values()},found
        env={k:v for k,v in os.environ.items() if k in
             ('PATH','HOME','TMPDIR','LANG','PYTHONUNBUFFERED')}
        env.update({'API_BASE_URL':base,'HOME':'/tmp','TMPDIR':'/tmp',
                    'XDG_CACHE_HOME':'/tmp/cache','PYTHONDONTWRITEBYTECODE':'1',
                    'PYTHON_DOTENV_DISABLED':'1','RUFF_CACHE_DIR':'/tmp/ruff-cache'})
        observed=[]
        with MCPClient(['/opt/mcpgen/bin/python','-u',str(target/'server.py')],
                       protocol='legacy',env=env) as client:
            assert client.list_tools()==found
            for name,c in CONTRACTS.items():
                previous=ctr['total']
                result=client.call(c['operation'],{})
                assert ctr['total']==previous+1
                native,broken,fixed,_=prove(name,c,result)
                def still_fails(body):
                    if not isinstance(body,dict):return False
                    if classify_real_sdk(name,body,c['status'])!=c['expected']:
                        return False
                    v=variant_mcp(result,body)
                    return (classify(name,v,c['status'])!=c['expected'] and
                            classify(name,promote_text_json(v),c['status'])==c['expected'])
                minim=minimize(c['body'],still_fails,max_checks=350)
                assert minim['minimality']=='ONE_MINIMAL_DELETIONS',(name,minim)
                assert minim['minimal_bytes']<minim['original_bytes']
                # Independent real MCP generated-server replay of the minimized body.
                lookup[c['path']]=(c['status'],copy.deepcopy(minim['minimal']))
                previous=ctr['total']
                reobserved=client.call(c['operation'],{})
                assert ctr['total']==previous+1
                min_contract={**c,'body':minim['minimal']}
                native2,broken2,fixed2,witness2=prove(name,min_contract,reobserved)
                assert (native2,broken2,fixed2)==(native,broken,fixed)
                observed.append({'name':name,'contract':c,
                    'original_mcp':result,'minimal_mcp':reobserved,
                    'minim':minim,'native':native,'broken':broken,
                    'fixed':fixed,'witness':witness2})
            # P3 independent positive controls: 4 real alternate error
            # decisions + 2 valid HTTP-200 responses, through same MCPGen.
            controls=test_controls(client,lookup,ctr,CONTRACTS,OUT/'repro_package')
        assert ctr=={'total':10,'unexpected':0},ctr
        assert len(controls)==6 and all(x['typed_passthrough_preserved'] for x in controls)
        old,new,patch=bridge_files()
        package=OUT/'repro_package'
        fixtures=package/'fixtures'
        fixtures.mkdir(parents=True,exist_ok=True)
        (package/'consumer_bridge.py').write_text(old,encoding='utf-8')
        (package/'consumer_bridge_fixed.py').write_text(new,encoding='utf-8')
        (package/'consumer_bridge.patch').write_text(patch,encoding='utf-8')
        shutil.copy2(ROOT/'apps'/'replay_generated.py',package/'replay_generated.py')
        shutil.copy2(ROOT/'apps'/'real_contracts.py',package/'real_contracts.py')
        summaries=[]
        mutants_killed=0
        for x in observed:
            name=x['name'];c=x['contract'];m=x['minim']
            # Deliberately remove the exact SDK-required discriminator from
            # the minimal body. A meaningful regression must fail this test.
            mutated=copy.deepcopy(m['minimal'])
            if name=='pygithub-404':
                mutated.pop('message')
            else:
                mutated['error'].pop('code')
            assert classify_real_sdk(name,mutated,c['status'])!=x['native']
            mutants_killed+=1
            assert bridge_classify(name,old,c,x['minimal_mcp'])==x['broken']
            assert bridge_classify(name,new,c,x['minimal_mcp'])==x['fixed']
            (fixtures/(name+'.json')).write_text(json.dumps({
              'contract':name,'status':c['status'],'source_body':m['minimal'],
              'mcp_result':x['minimal_mcp']},indent=2)+'\n',encoding='utf-8')
            summaries.append({
              'name':name,'repository':c['repo'],'commit':c['commit'],
              'source':c['file'],'source_blob_sha':c['blob'],
              'source_status':c['status'],'required_path':c['required_path'],
              'original_sdk_result':x['native'],
              'broken_bridge_result':x['broken'],
              'repaired_bridge_result':x['fixed'],
              'original_bytes':m['original_bytes'],'minimal_bytes':m['minimal_bytes'],
              'accepted_deletions':m['accepted_deletions'],
              'minimizer_checks':m['checks'],'minimality':m['minimality'],
              'first_mcp_sha256':hashlib.sha256(canonical(x['original_mcp']).encode()).hexdigest(),
              'minimized_real_mcp_sha256':hashlib.sha256(canonical(x['minimal_mcp']).encode()).hexdigest(),
              'real_mcp_witness':x['witness']
            })
        workspace=Path(tempfile.mkdtemp(prefix='risu-patch-',dir='/tmp'))
        (workspace/'consumer_bridge.py').write_text(old,encoding='utf-8')
        p=subprocess.run(['patch','-p0','--batch','--forward'],cwd=workspace,
                         input=patch,text=True,capture_output=True,timeout=10)
        assert p.returncode==0,(p.stdout,p.stderr)
        actual=(workspace/'consumer_bridge.py').read_text(encoding='utf-8')
        assert actual==new
        for x in observed:
            assert bridge_classify(x['name'],actual,x['contract'],x['minimal_mcp'])==x['fixed']
        (package/'REPLAY_GUIDE.md').write_text(
          '# Consumer contract repair: tested synthetic adapter patch\n\n'
          'Run the supplied replay_generated.py against fixtures after installing '
          'both exact pinned external SDKs and the RISU v0.9.5 package.\n'
          'Apply consumer_bridge.patch to the included consumer_bridge.py with '
          'patch -p0, then rerun replay_generated.py. '
          'This does not modify upstream MCPGen, PyGithub, or Stripe code.\n'
          'Intermediate deletion tests model an observed JSON envelope; '
          'final minimized cases were independently replayed by genuine generated MCPGen.\n'
          'All payloads are synthetic and read-only. No real payment or GitHub APIs used.\n'
          'One-minimality is local to recursive key/array deletion operations.\n',
          encoding='utf-8')
        result={'status':'PASS','product_version':VERSION,'consumers':summaries,
                'pinned_repos':SHA,'synthetic_http_get_count':ctr['total'],
                'unexpected_requests':ctr['unexpected'],
                'real_minimal_mcp_replays':2,
                'real_control_mcp_replays':len(controls),
                'control_results':controls,
                'typed_passthrough_cases':len(controls),
                'critical_field_mutants_killed':mutants_killed,
                'patch_applied_and_retested':True,
                'runtime_seconds':round(time.monotonic()-started,3),
                'scope':'Two actual pinned SDK error handlers; synthetic GET facade and real generated MCPGen; no provider APIs, no LLM'}
        (OUT/'REAL_APPS_SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print('RISU_EXTERNAL_CONSUMER_REPRO_PASS',json.dumps({
            'actual_sdk_consumers':2,'real_mcp_gets':ctr['total'],
            'controls':len(controls),'mutants_killed':mutants_killed,
            'patch':'PASS','sizes':{x['name']:x['minimal_bytes'] for x in summaries}}),flush=True)
    finally:
        server.shutdown();server.server_close()
        shutil.rmtree(temp,ignore_errors=True)

if __name__=='__main__':
    main()
