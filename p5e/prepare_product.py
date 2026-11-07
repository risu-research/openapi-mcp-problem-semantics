"""Rebuild P5-E from exact OS-specific P5-D CI wheel. Only 3 modules change."""
from __future__ import annotations
import argparse,hashlib,json,zipfile
from pathlib import Path
from optimize_ast import patch

PINS={
 'Linux':'47864a6f73d77a1edd5f8047a7238f0545ef7d78af848d960053ade36e38bc72',
 'Windows':'c8ca5fb60ce98192224ae388a53c0c297ce36bb44b952354df7dfa45f10fb560',
}

def replace_exact(text,old,new):
    if text.count(old)!=1:raise ValueError('Unexpected source anchor '+old)
    return text.replace(old,new,1)

def prepare(wheel:Path,output:Path,os_name:str):
    original_hash=hashlib.sha256(wheel.read_bytes()).hexdigest()
    if original_hash!=PINS[os_name]:raise ValueError('Incorrect pinned P5-D wheel: '+original_hash)
    if output.exists() and any(output.iterdir()):raise ValueError('Refusing nonempty source directory')
    output.mkdir(parents=True,exist_ok=True)
    old={}
    with zipfile.ZipFile(wheel) as z:
        for inf in z.infolist():
            n=inf.filename
            if n.endswith('.py') and '/' not in n and n.startswith('risu_'):
                if n in old or inf.file_size>200_000:raise ValueError('Unexpected source inventory')
                old[n]=z.read(inf).decode('utf-8')
    for n in ('risu_static.py','risu_firstuse.py','risu_probe.py','risu_quickcheck.py','risu_p5d_cli.py'):
        if n not in old:raise ValueError('Missing old module '+n)
    after=dict(old)
    after['risu_static.py']=patch(old['risu_static.py'])
    after['risu_probe.py']=replace_exact(old['risu_probe.py'],
        "VERSION = '0.9.19-experimental'","VERSION = '0.9.20-experimental'")
    if old['risu_firstuse.py'].count('0.9.19')<2:raise ValueError('Missing P5-D display version')
    after['risu_firstuse.py']=old['risu_firstuse.py'].replace('0.9.19','0.9.20')
    changes={}
    for name,source in after.items():
        # Preserve exact wheel source bytes on Windows; write_text would translate LF.
        (output/name).write_bytes(source.encode('utf-8'))
        if (output/name).read_bytes()!=source.encode('utf-8'):
            raise RuntimeError('P5E_SOURCE_BYTE_IDENTITY_FAILED '+name)
        if source!=old[name]:
            changes[name]={'before':hashlib.sha256(old[name].encode()).hexdigest(),
                           'after':hashlib.sha256(source.encode()).hexdigest()}
    if set(changes)!={'risu_static.py','risu_firstuse.py','risu_probe.py'}:
        raise ValueError('Unexpected module change '+str(set(changes)))
    modules=sorted(x[:-3] for x in after)
    pyproject=('[build-system]\nrequires = ["setuptools>=61"]\nbuild-backend = "setuptools.build_meta"\n\n'
       '[project]\nname = "risu-probe-preview"\nversion = "0.9.20.dev0"\nrequires-python = ">=3.11"\n'
       'dependencies = ["PyYAML==6.0.2"]\n'
       'description = "Experimental offline-first HTTP-to-MCP preservation diagnostics"\nlicense = "Apache-2.0"\n\n'
       '[project.scripts]\nrisu-probe = "risu_p5d_cli:main"\n\n'
       '[tool.setuptools]\npy-modules = [\n'+''.join('  "'+m+'",\n' for m in modules)+']\n')
    (output/'pyproject.toml').write_text(pyproject,encoding='utf-8')
    result={'schema':'risu-p5e-build-source-provenance-v1','prior_wheel_sha256':original_hash,
        'os':os_name,'modules':len(after),'allowed_changed_modules':changes,'unchanged_modules':len(after)-len(changes)}
    (output.parent/'SOURCE_PROVENANCE.json').write_text(json.dumps(result,indent=2)+'\n')
    print('P5E_PINNED_P5D_REBUILD_PASS',json.dumps(result,sort_keys=True),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--wheel',type=Path,required=True)
    p.add_argument('--product',type=Path,required=True)
    p.add_argument('--os',choices=tuple(PINS),required=True)
    a=p.parse_args();prepare(a.wheel,a.product,a.os)
