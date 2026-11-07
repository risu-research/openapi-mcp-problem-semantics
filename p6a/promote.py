"""P6-A: byte-preserving promotion of the *verified* P5-E wheel to readable src/.

This is a one-time origin reconstruction, NOT a long-term build dependency.
Normal builds use risu-probe/src as their only product source.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import io
import json
from pathlib import Path
import zipfile

BASE_SHA = '56eb547c924c9b89d6d5a9fa760de99df95d7c8d4b872899a3fa70c4e45099d6'
REFERENCE = 'risu_probe_preview-0.9.20.dev0-py3-none-any.whl'

def promote(reference_wheel: Path, output: Path) -> dict:
    blob=reference_wheel.read_bytes()
    actual=sha256(blob).hexdigest()
    if actual!=BASE_SHA:raise ValueError(f'Wrong P5-E Linux CI wheel digest: {actual}')
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        entries=archive.namelist()
        modules=sorted(n for n in entries if n.endswith('.py'))
        if len(modules)!=38 or any('/' in n for n in modules) or len(set(modules))!=38:
            raise ValueError('Unexpected reference wheel source module inventory')
        package_info=next(x for x in entries if x.endswith('/METADATA'))
        metadata=archive.read(package_info).decode()
        if 'Name: risu-probe-preview\n' not in metadata or 'Version: 0.9.20.dev0\n' not in metadata:
            raise ValueError('Unexpected P5-E wheel metadata')
        src=output/'src';src.mkdir(parents=True,exist_ok=True)
        manifest={}
        for name in modules:
            data=archive.read(name)
            if b'\x00' in data or b'\r\n' in data:raise ValueError('Noncanonical LF source: '+name)
            path=src/name
            if path.exists() and path.read_bytes()!=data:
                raise ValueError('Refusing to overwrite existing divergent file: '+str(path))
            path.write_bytes(data)
            manifest[name]=sha256(data).hexdigest()
    docs=output/'P5E_SOURCE_PROVENANCE.json'
    provenance={
        'schema':'risu-p6a-product-source-origin-v1',
        'reference_ci_run':42330673704,
        'reference_os':'Linux',
        'reference_wheel_sha256':BASE_SHA,
        'reference_wheel_filename':REFERENCE,
        'reference_version':'0.9.20.dev0',
        'modules_sha256':manifest,
        'scope':'Exact module bytes promoted; no source changes, no reimplementation or source execution.',
        'historical_windows_note':'The P5-E Windows CI wheel had CRLF in three modules; canonical P6-A checked-in sources use LF on every OS.',
    }
    if docs.exists() and json.loads(docs.read_text())!=provenance:
        raise ValueError('Refusing to overwrite modified provenance manifest')
    docs.write_text(json.dumps(provenance,indent=2,sort_keys=True)+'\n')
    return provenance

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--reference-wheel',type=Path,required=True)
    p.add_argument('--output',type=Path,default=Path('risu-probe'))
    a=p.parse_args()
    q=promote(a.reference_wheel,a.output)
    print('P6A_PROMOTED_EXACT_CI_SOURCE',len(q['modules_sha256']),q['reference_wheel_sha256'])
