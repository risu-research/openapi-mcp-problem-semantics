"""P5-D reconstruct source from exact published P5-C CI wheel, preserving all modules."""
from __future__ import annotations
import argparse,hashlib,zipfile
from pathlib import Path,PurePosixPath
PIN='6bdfa3cfc9fef675aa30cb94d30b546789b1f005a4c9f5df927def19b3e3c8d5'
VERSION='0.9.18.dev0'
def run(wheel:Path, output:Path):
    b=wheel.read_bytes()
    if hashlib.sha256(b).hexdigest()!=PIN:raise ValueError('P5C_WHEEL_SHA256_MISMATCH')
    if output.exists() and any(output.iterdir()):raise ValueError('Nonempty target source directory')
    output.mkdir(parents=True,exist_ok=True)
    modules={}
    with zipfile.ZipFile(wheel) as z:
        for i in z.infolist():
            n=i.filename
            if PurePosixPath(n).as_posix()!=n or n.startswith('/') or '\\' in n or '..' in n.split('/'):
                raise ValueError('Unexpected wheel path')
            if n.endswith('.py') and '/' not in n:
                if not n.startswith('risu_') or i.file_size>100000 or n in modules:
                    raise ValueError('Unexpected module source')
                modules[n]=z.read(i)
    if len(modules)!=36 or 'risu_p5c_cli.py' not in modules:raise ValueError('P5C_WHEEL_MODULE_INVENTORY_MISMATCH '+str(len(modules)))
    if b"VERSION = '0.9.18-experimental'" not in modules['risu_probe.py']:raise ValueError('Unexpected P5C version')
    for n,b in modules.items():(output/n).write_bytes(b)
    names=',\n'.join('  "'+n[:-3]+'"' for n in sorted(modules))
    (output/'pyproject.toml').write_text('[build-system]\nrequires = ["setuptools>=61"]\nbuild-backend = "setuptools.build_meta"\n\n'+
       '[project]\nname = "risu-probe-preview"\nversion = "0.9.18.dev0"\nrequires-python = ">=3.11"\n'+
       'description = "Experimental offline-first HTTP-to-MCP preservation diagnostics"\nlicense = "Apache-2.0"\n\n'+
       '[project.scripts]\nrisu-probe = "risu_p5c_cli:main"\n\n[tool.setuptools]\npy-modules = [\n'+names+'\n]\n',encoding='utf-8')
    print('P5D_EXACT_PREVIOUS_WHEEL_REHYDRATED',len(modules),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wheel',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.wheel,a.output)
