"""Independent clean-venv install and very first use on Windows and Linux."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv

BASE=Path(__file__).resolve().parents[1]
wheels=sorted((BASE/'dist'/'wheels').glob('risu_probe_preview-*.whl'))
assert len(wheels)==1,wheels

with tempfile.TemporaryDirectory(prefix='risu first install ') as root:
    root=Path(root)
    env=root/'new-install'
    venv.EnvBuilder(with_pip=True).create(env)
    py=(env/'Scripts'/'python.exe') if os.name=='nt' else (env/'bin'/'python')
    def run(*args):
        proc=subprocess.run([str(py),*map(str,args)],capture_output=True,text=True,timeout=40)
        assert proc.returncode==0,(args,proc.returncode,proc.stdout,proc.stderr)
        return proc.stdout
    run('-m','pip','install','--disable-pip-version-check','--no-index','--no-deps',wheels[0])
    version=run('-c','import risu_probe; print(risu_probe.VERSION)')
    assert '0.9.1-experimental' in version
    project=root/'첫 검사 space'
    project.mkdir()
    (project/'never_import.py').write_text("raise RuntimeError('unsafe import')\n",encoding='utf-8')
    first=run('-c','import risu_probe,sys; sys.exit(risu_probe.main())','first-check',project,'--json')
    payload=json.loads(first)
    assert payload['execution']=='NONE' and payload['network_requests']==0,first
    assert payload['files_examined']==1,first
    startup=run('-c','import risu_probe,sys;sys.exit(risu_probe.main())','--help')
    assert 'first-check' in startup,startup
    cli=env/'Scripts'/'risu-probe.exe' if os.name=='nt' else env/'bin'/'risu-probe'
    assert cli.is_file(),cli
    entry=subprocess.run([str(cli),'--version'],capture_output=True,text=True,timeout=20)
    assert entry.returncode==0 and '0.9.1' in entry.stdout,entry
    print('CLEAN_INSTALL_PASS',sys.platform,'wheel=',wheels[0].name,
          'entrypoint=',str(cli.name),'offline_files=',payload['files_examined'])
