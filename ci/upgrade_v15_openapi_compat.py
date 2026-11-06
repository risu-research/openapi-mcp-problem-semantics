"""Fail-closed SHA-pinned v0.9.6 -> v0.9.7: bounded OpenAPI discovery only.

No modification of P0-P3 decisions, consumer witnesses, comparators, or live
execution. Keeps Python scanner limits unchanged. Reads only local OpenAPI
JSON/YAML descriptions, bounded by size, count, depth and total bytes.
"""
from pathlib import Path
import hashlib

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'dist'/'risu_v09_source'
PINS={
    'risu_static.py':'e94b67cdc999aaf91701ff5238bd308ebe40235ac44616a80a0445f159756cb0',
    'risu_onboarding.py':'92ae0d9c09c86a85e440d89fc0fea7fddbe3f823d9faee5ed265ea16ced4c47a',
    'risu_probe.py':'1b50c34c13e988f3a9f075ec596ee1453cc99e851b6d2ba438043d59b90a781d',
    'pyproject.toml':'d07fc6b071aefc9b70ae33dcef87b1b72acdb353188469cc37987e742f6b7812',
}
for name,pin in PINS.items():
    f=SOURCE/name
    raw=f.read_bytes().replace(b'\r\n',b'\n')
    assert hashlib.sha256(raw).hexdigest()==pin,(name,'unexpected v0.9.6 source')
    f.write_bytes(raw)

def replace(name,old,new):
    f=SOURCE/name
    raw=f.read_text(encoding='utf-8')
    count=raw.count(old)
    assert count==1,(name,'patch anchor',count,old[:110])
    f.write_bytes(raw.replace(old,new).encode('utf-8'))

replace('risu_static.py',
    'MAX_BYTES = 512 * 1024\nMAX_TOTAL_BYTES = 15 * 1024 * 1024',
    'MAX_BYTES = 512 * 1024  # Unchanged maximum for Python source\nMAX_SPEC_BYTES = 16 * 1024 * 1024  # One public OpenAPI description\nMAX_TOTAL_BYTES = 35 * 1024 * 1024  # Across accepted files\nMAX_SNIFF_BYTES = 16 * 1024')

newfunction='''def _has_openapi_header(path:Path):
    """True only for bounded JSON/YAML files with an apparent OpenAPI header.

    This identifies *candidates*, never proves a valid specification.
    Actual parser and _schema_gets determine whether the file is OpenAPI.
    """
    if path.suffix.lower() not in ('.json','.yaml','.yml'):
        return False
    try:
        if path.stat().st_size>MAX_SPEC_BYTES:
            # Too large to admit automatically, but include recognized names
            # so it is recorded as incomplete rather than silently omitted.
            return bool(OPENAPI_NAMES.search(path.name))
        with path.open('rb') as f:
            prefix=f.read(MAX_SNIFF_BYTES)
        if path.suffix.lower()=='.json':
            return bool(re.search(rb'"(?:openapi|swagger)"\\s*:',prefix))
        return bool(re.search(rb'(?m)^\\s*(?:openapi|swagger)\\s*:',prefix))
    except (OSError,ValueError):
        return False


'''
replace('risu_static.py','def _find_files(target:Path):',newfunction+'def _find_files(target:Path):')
replace('risu_static.py',
    "not d.startswith('.') and not (base/d).is_symlink()",
    "(not d.startswith('.') or d=='.schema') and not (base/d).is_symlink()")
replace('risu_static.py',
    "(OPENAPI_NAMES.search(name) or name in ('swagger.json','swagger.yaml','swagger.yml'))",
    "(OPENAPI_NAMES.search(name) or _has_openapi_header(path))")
replace('risu_static.py',
    "            if sz>MAX_BYTES:\n                incomplete.append({'path':label,'reason':f'file exceeds {MAX_BYTES} byte limit'});continue",
    "            limit=MAX_BYTES if file.suffix.lower()=='.py' else MAX_SPEC_BYTES\n            if sz>limit:\n                incomplete.append({'path':label,'reason':f'file exceeds {limit} byte limit'});continue")
replace('risu_static.py',"'version':'0.9.6-experimental'","'version':'0.9.7-experimental'")
replace('risu_static.py',"'version':'0.9.6','rules'","'version':'0.9.7','rules'")
replace('risu_onboarding.py',"'version':'0.9.6-experimental'","'version':'0.9.7-experimental'")
replace('risu_probe.py',"VERSION = '0.9.6-experimental'","VERSION = '0.9.7-experimental'")
replace('pyproject.toml','0.9.6.dev0','0.9.7.dev0')
print('RISU_V097_BOUNDED_OPENAPI_DISCOVERY_UPGRADE_VERIFIED')
for p in ('risu_static.py','risu_onboarding.py','risu_probe.py','pyproject.toml'):
    print(p,hashlib.sha256((SOURCE/p).read_bytes()).hexdigest())
