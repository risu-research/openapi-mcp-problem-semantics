"""Fetch ONLY ten preregistered, exact GitHub raw source artifacts.

Source download is the only internet-enabled phase. This downloader never
executes repo code or accesses an API host. No credentials, tokens, or
environment-provided authorization headers are read or forwarded.
"""
import hashlib
import json
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler

BASE=Path(__file__).resolve().parent
FREEZE=json.loads((BASE/'FROZEN_PREREGISTRATION.json').read_text())
MAX_EACH=FREEZE['test_design']['max_spec_bytes']
MAX_ALL=FREEZE['test_design']['max_total_bytes']

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

def git_blob_sha(data):
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()

def download(output):
    output.mkdir(parents=True,exist_ok=True)
    opener=build_opener(NoRedirect())
    results=[]
    downloaded=0
    for target in FREEZE['fixed_targets']:
        started=time.monotonic()
        name=target['id']; path=target['path']; project=target['repository']
        assert path and not any(x in ('.','..','') for x in Path(path).parts)
        assert project.count('/')==1 and all(ch.isalnum() or ch in '-_./' for ch in project)
        url='https://raw.githubusercontent.com/'+project+'/'+target['commit']+'/'+quote(path,safe='/')
        parsed=urlparse(url)
        assert parsed.scheme=='https' and parsed.hostname=='raw.githubusercontent.com'
        record={'id':name,'repository':project,'commit':target['commit'],
                'path':path,'expected_bytes':target['expected_bytes'],
                'expected_git_blob':target['blob_sha1'],
                'source_url':url,'download_status':None,'actual_bytes':None,
                'sha256':None,'actual_git_blob':None,'download_seconds':None}
        try:
            if target['expected_bytes']>MAX_EACH:
                raise ValueError('PREDECLARED_PER_FILE_CAP')
            if downloaded+target['expected_bytes']>MAX_ALL:
                raise ValueError('PREDECLARED_TOTAL_CAP')
            request=Request(url,headers={'User-Agent':'RISU-P4A-readonly-spec-qualification/1.0',
                                         'Accept':'application/octet-stream'})
            with opener.open(request,timeout=35) as response:
                actual=urlparse(response.geturl())
                if actual.scheme!='https' or actual.hostname!='raw.githubusercontent.com':
                    raise ValueError('UNEXPECTED_RESPONSE_HOST')
                payload=response.read(target['expected_bytes']+1)
            if len(payload)!=target['expected_bytes']:
                raise ValueError('GIT_SOURCE_LENGTH_MISMATCH')
            blob=git_blob_sha(payload)
            if blob!=target['blob_sha1']:
                raise ValueError('GIT_BLOB_IDENTITY_MISMATCH')
            target_path=output/name/path
            target_path.parent.mkdir(parents=True,exist_ok=True)
            target_path.write_bytes(payload)
            downloaded+=len(payload)
            record.update(download_status='VERIFIED',actual_bytes=len(payload),
                          sha256=hashlib.sha256(payload).hexdigest(),actual_git_blob=blob)
        except (ValueError,HTTPError,URLError,OSError,TimeoutError) as exc:
            record['download_status']='FETCH_FAILED'
            # Never emit raw external exception strings (URLs could contain tokens).
            record['failure_type']=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
        record['download_seconds']=round(time.monotonic()-started,3)
        results.append(record)
        print('P4A_FETCH',name,record['download_status'],record.get('failure_type',''),
              flush=True)
    (output/'download_report.json').write_text(
        json.dumps({'schema':'risu-p4a-download-v1','preregistered_targets':len(results),
                    'verified':sum(x['download_status']=='VERIFIED' for x in results),
                    'downloaded_bytes':downloaded,'projects':results},indent=2)+'\n')
    print('RISU_P4A_FETCH_COMPLETE',sum(x['download_status']=='VERIFIED' for x in results))

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Usage: python p4a/fetch_frozen.py OUTPUT_DIRECTORY')
    download(Path(sys.argv[1]))
