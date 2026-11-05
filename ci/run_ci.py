"""Run byte-identical original RISU Probe v0.8 against freshly generated CNOE.

The Docker runtime must be --network none, read-only, non-root and secret-free.
"""
import errno,hashlib,json,os,pathlib,shutil,subprocess,sys,tempfile

BASE=pathlib.Path('/opt/risu')
OUT=pathlib.Path('/results')
CNOE_SHA='8c2b065497cf32ecbb7cf7e28dad3a99c6706c3f'

def command(args, *,cwd=None,environment=None,log=None,timeout=150):
    p=subprocess.run(args,cwd=cwd,env=environment,capture_output=True,text=True,timeout=timeout)
    if log:
        (OUT/log).write_text('STDOUT:\n'+p.stdout+'\nSTDERR:\n'+p.stderr+'\n')
    if p.returncode:
        raise RuntimeError(f'{args[:3]} returned {p.returncode}: {p.stderr[-400:]}')
    return p

def isolated():
    assert os.geteuid()==65534, 'container must run non-root'
    lines=pathlib.Path('/proc/net/route').read_text().splitlines()[1:]
    assert not any(len(x.split())>2 and x.split()[1]=='00000000' for x in lines), 'network default route detected'
    try: (BASE/'unexpected-write').write_text('x')
    except OSError as exc:
        if exc.errno not in {errno.EROFS, errno.EACCES, errno.EPERM}: raise
    else:raise RuntimeError('root filesystem is writable')

def subprocess_env():
    return {'PATH':os.environ['PATH'],'HOME':'/tmp','TMPDIR':'/tmp',
            'PYTHONUNBUFFERED':'1','PYTHONDONTWRITEBYTECODE':'1',
            'XDG_CACHE_HOME':'/tmp/cache','PYTHONPATH':str(BASE/'product'),
            'PYTHON_DOTENV_DISABLED':'1'}

def make_openapi(inp):
    inp.mkdir(parents=True,exist_ok=True)
    responses={}
    for status, mime in ((200,'application/json'),(400,'application/json'),
                         (409,'application/problem+json'),(422,'application/problem+json')):
        responses[str(status)]={'description':'synthetic fixture',
                                'content':{mime:{'schema':{'type':'object'}}}}
    spec={'openapi':'3.1.0','info':{'title':'Risucheck API','version':'1.0.0'},
          'paths':{'/orders/{id}':{'get':{
              'operationId':'get_order','description':'Read a synthetic order',
              'parameters':[{'name':'id','in':'path','required':True,
                             'schema':{'type':'string'}}],'responses':responses}}}}
    (inp/'openapi.json').write_text(json.dumps(spec,indent=2)+'\n')
    (inp/'config.yaml').write_text("""title: risucheck
description: Synthetic read-only localhost API
author: RISU Institute
version: 0.0.0
license: Apache-2.0
python_version: 3.13
headers:
  Accept: application/json
poetry_dependencies: |
  python = ">=3.13,<4.0"
  httpx = ">=0.24.0"
  python-dotenv = ">=1.0.0"
  pydantic = ">=2.0.0"
  mcp = ">=1.9.0"
""")
    shutil.copy2(inp/'openapi.json',OUT/'SOURCE_OPENAPI.json')
    shutil.copy2(inp/'config.yaml',OUT/'GENERATOR_CONFIG.yaml')

def main():
    isolated()
    OUT.mkdir(exist_ok=True)
    sha=command(['git','-c','safe.directory=/opt/cnoe-source','-C','/opt/cnoe-source','rev-parse','HEAD']).stdout.strip()
    assert sha==CNOE_SHA
    meta=json.loads((BASE/'product-bundle'/'SOURCE_MANIFEST.json').read_text())
    for path,digest in meta['modules_sha256'].items():
        assert hashlib.sha256((BASE/'product'/path).read_bytes()).hexdigest()==digest
    (OUT/'SOURCE_MANIFEST.json').write_text(json.dumps(meta,indent=2)+'\n')
    (OUT/'CNOE_HEAD.txt').write_text(sha+'\n')
    shutil.copy2(BASE/'product-bundle'/'CNOE_DEPENDENCIES.txt',OUT/'CNOE_DEPENDENCIES.txt')
    with tempfile.TemporaryDirectory(prefix='risu-v09-',dir='/tmp') as td:
        root=pathlib.Path(td)
        inp=root/'input';generated=root/'generated'
        make_openapi(inp)
        command(['/opt/cnoe/bin/python','-m','openapi_mcp_codegen',
                 '--spec-file',str(inp/'openapi.json'),'--output-dir',str(generated),
                 '--log-level','warning'],cwd=root,environment=subprocess_env(),
                log='GENERATOR_LOG.txt',timeout=180)
        (generated/'openapi.json').write_bytes((inp/'openapi.json').read_bytes())
        assert (generated/'mcp_risucheck'/'server.py').is_file()
        hashes={p.relative_to(generated).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                for p in generated.rglob('*') if p.is_file()}
        (OUT/'GENERATED_SHA256.json').write_text(json.dumps(hashes,indent=2)+'\n')
        shutil.make_archive(str(OUT/'GENERATED_CNOE_SOURCES'),'zip',root_dir=generated)
        product=str(BASE/'product'/'risu_probe.py')
        # Actual original-product scan (no target import and no tool execution)
        r=command([sys.executable,'-B',product,'scan',str(generated),
                   '--format','json'],environment=subprocess_env(),log='SCAN_LOG.txt')
        scan=json.loads(r.stdout)
        assert any(x.get('rule_id')=='RPY101' for x in scan['findings'])
        (OUT/'STATIC_SCAN.json').write_text(json.dumps(scan,indent=2)+'\n')
        # Actual original-product preview (zero tool calls)
        r=command([sys.executable,'-B',product,'verify','--fixture',str(generated)],
                  environment=subprocess_env(),log='PREVIEW_LOG.txt')
        preview=json.loads(r.stdout)
        assert preview['status']=='UNVERIFIED' and preview['execution']=='NONE'
        assert len(preview['fixture_cases'])==4
        (OUT/'PREVIEW.json').write_text(json.dumps(preview,indent=2)+'\n')
        # THIS executes the original v0.8 product module, not a second verifier.
        command([sys.executable,'-B',product,'verify','--fixture',str(generated),
                 '--allow-exec','--python','/opt/cnoe/bin/python',
                 '--out',str(OUT/'V08_PRODUCT_VERIFICATION.json')],
                environment=subprocess_env(),log='PRODUCT_EXECUTION_LOG.txt',timeout=180)
        result=json.loads((OUT/'V08_PRODUCT_VERIFICATION.json').read_text())
        assert result['status']=='CORROBORATED_BEHAVIOR'
        assert result['counts']=={'planned':4,'captured':4,'fixture_gets':12,
                                  'unexpected_requests':0,'error_losses':3}
        assert result['positive_control']=='PRESERVED'
        assert {x['http_status']:x['verdict'] for x in result['evaluations']}=={
            200:'PRESERVED',400:'LOSS',409:'LOSS',422:'LOSS'}
        assert result['static_links'][0]['rule_id']=='RPY101'
        assert result['static_links'][0]['verdict']=='BEHAVIORALLY_CORROBORATED'
        (OUT/'EXECUTION_STATUS.json').write_text(json.dumps({
            'status':'PASS','product':'actual original RISU Probe v0.8 wheel modules',
            'source_wheel_sha256':meta['source_wheel_sha256'],
            'actual_cnoe_generator_commit':sha,
            'sandbox':{'nonroot':True,'network':'none','root_filesystem':'read-only',
                       'capabilities':'all dropped','credentials':'none'},
            'cases':result['counts']},indent=2)+'\n')
        print('ORIGINAL RISU PRODUCT ON REAL GENERATED CNOE PASS:',result['counts'])

if __name__=='__main__':main()
