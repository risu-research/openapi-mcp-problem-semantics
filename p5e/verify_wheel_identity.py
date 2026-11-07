"""CI gate: only the AST implementation and presentation-version modules may change."""
from __future__ import annotations
import argparse,hashlib,json,zipfile
from pathlib import Path
ALLOWED={'risu_static.py','risu_firstuse.py','risu_probe.py'}

def verify(before:Path,after:Path):
    with zipfile.ZipFile(before) as old,zipfile.ZipFile(after) as new:
        names={n for n in old.namelist() if n.endswith('.py') and '/' not in n and n.startswith('risu_')}
        candidate={n for n in new.namelist() if n.endswith('.py') and '/' not in n and n.startswith('risu_')}
        if names!=candidate or len(names)!=38:raise RuntimeError('Installed wheel source module inventory changed')
        changed={n for n in names if old.read(n)!=new.read(n)}
        if changed!=ALLOWED:raise RuntimeError('Unexpected changed code modules: '+str(sorted(changed)))
        for n in names-ALLOWED:
            if old.read(n)!=new.read(n):raise RuntimeError('Old analyzer module drift: '+n)
    print('P5E_INSTALLED_WHEEL_35_OLD_MODULES_BYTE_IDENTICAL_PASS',
          json.dumps({'original_sha256':hashlib.sha256(before.read_bytes()).hexdigest(),
                      'candidate_sha256':hashlib.sha256(after.read_bytes()).hexdigest(),
                      'unchanged_modules':len(names-ALLOWED),'changed':sorted(ALLOWED)}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--before',type=Path,required=True)
    p.add_argument('--after',type=Path,required=True)
    a=p.parse_args();verify(a.before,a.after)
