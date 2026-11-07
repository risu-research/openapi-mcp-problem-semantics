"""Rebuild one pinned P5-C wheel; install baseline and successor on each CI OS."""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,os,platform,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE_SHA='6bdfa3cfc9fef675aa30cb94d30b546789b1f005a4c9f5df927def19b3e3c8d5'

def run(*args, env=None):
    print('RUN', ' '.join(str(x) for x in args),flush=True)
    p=subprocess.run([str(x) for x in args],check=False,cwd=ROOT,env=env,timeout=900)
    if p.returncode:raise RuntimeError('Step returned '+str(p.returncode)+': '+str(args))

def py_in(env):
    return env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')

def cli_in(env):
    return env/('Scripts/risu-probe.exe' if os.name=='nt' else 'bin/risu-probe')

def verify_sources(wheel:Path,candidate:Path):
    import zipfile
    core=['risu_analyze.py','risu_causality.py','risu_coverage.py','risu_arraymatch.py',
          'risu_contract_history.py','risu_obligations.py','risu_nested_schema.py','risu_compat.py',
          'risu_p5a_cli.py','risu_static.py','risu_quickcheck.py','risu_p5c_cli.py']
    with zipfile.ZipFile(wheel) as a,zipfile.ZipFile(candidate) as b:
        for n in core:
            if a.read(n)!=b.read(n):raise RuntimeError('Unexpected existing engine change: '+n)
    print('P5D_EXISTING_12_ENGINE_MODULES_UNCHANGED_ON_INSTALLED_WHEEL',flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--base-wheel',type=Path,required=True);p.add_argument('--repeat',type=int,default=3)
    a=p.parse_args();base=a.base_wheel.resolve()
    if hashlib.sha256(base.read_bytes()).hexdigest()!=BASE_SHA:raise RuntimeError('P5C_CI_VERIFIED_WHEEL_MISMATCH')
    run(sys.executable,'p5d/prepare_base.py','--wheel',base,'--output','dist/risu_v09_source')
    run(sys.executable,'p5d/apply_upgrade.py')
    run(sys.executable,'-m','pip','wheel','--no-deps','--no-build-isolation','--wheel-dir','p5d/wheels','dist/risu_v09_source')
    new=ROOT/'p5d/wheels/risu_probe_preview-0.9.19.dev0-py3-none-any.whl'
    if not new.exists():raise RuntimeError('Missing new wheel')
    verify_sources(base,new)
    ver={}
    for key,whl in [('baseline',base),('candidate',new)]:
        folder=ROOT/'p5d'/('env_'+key)
        run(sys.executable,'-m','venv',folder)
        run(py_in(folder),'-m','pip','install','--no-deps','--no-index',whl)
        cli=cli_in(folder)
        if not cli.exists():raise RuntimeError('Installed console script missing: '+str(cli))
        output=subprocess.run([str(cli),'--version'],capture_output=True,text=True,timeout=20,check=True).stdout.strip()
        assert ('0.9.18' if key=='baseline' else '0.9.19') in output,output
        ver[key]={'wheel':str(whl.relative_to(ROOT) if whl.is_relative_to(ROOT) else whl),'version':output,
                  'sha256':hashlib.sha256(whl.read_bytes()).hexdigest()}
    venv=ROOT/'p5d/env_candidate'
    run(py_in(venv),'-m','unittest','discover','-s','p5d/tests','-v')
    for command in ('scan','schema-compat','contract-history','analyze','reproduce','check','doctor'):
        p=subprocess.run([str(cli_in(venv)),command,'--help'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=20)
        if p.returncode!=0:raise RuntimeError('Previous command unavailable: '+command+' '+p.stderr[-500:])
    invalid=subprocess.run([str(cli_in(venv)),'check','P5D_DOES_NOT_EXIST'],capture_output=True,text=True,timeout=20)
    if invalid.returncode!=2 or 'RCHK101' not in invalid.stderr or 'Next:' not in invalid.stderr:
        raise RuntimeError('Missing path explanation is not actionable')
    diagnose=subprocess.run([str(cli_in(venv)),'doctor','--format','json'],capture_output=True,text=True,timeout=20,check=True)
    env_data=json.loads(diagnose.stdout)
    if env_data['platform']!=platform.system():raise RuntimeError('Wrong detected platform')
    # External repo checkouts and stopwatch subprocess runs happen only AFTER the installed CLI tests.
    run(sys.executable,'p5d/benchmark.py','--sources','p5d/external_repos.json',
        '--checkouts','p5d/external_sources','--baseline-cli',cli_in(ROOT/'p5d/env_baseline'),
        '--candidate-cli',cli_in(ROOT/'p5d/env_candidate'),
        '--output',ROOT/'p5d/results'/(platform.system().lower()+'.json'),'--repeat',a.repeat)
    result_path=ROOT/'p5d/results'/(platform.system().lower()+'.json')
    result=json.loads(result_path.read_text())
    before=result['summary']['baseline'];after=result['summary']['candidate']
    if after['commands_completed']<before['commands_completed'] or after['complete_source_scans']<before['complete_source_scans']:
        raise RuntimeError('P5D regressed overall project coverage or command success')
    # Only a generous regression gate. We do not promise a speed improvement.
    if after['median_repeated_ms'] > max(400, before['median_repeated_ms']*2.5):
        raise RuntimeError('P5D runtime regression beyond 2.5x median observed baseline')
    (ROOT/'p5d/results'/'installed_wheel_identity.json').write_text(json.dumps(ver,indent=2)+'\n')
    print('P5D_WINDOWS_LINUX_FIRST_USE_BENCHMARK_COMPLETE',json.dumps({
          'host_os':platform.system(),'baseline':before,'candidate':after,
          'same_old_modules':12,'new_regression_tests':13}),flush=True)

if __name__=='__main__':main()
