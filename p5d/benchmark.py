"""Pinned multi-repository cross-OS first-use benchmark, no user code execution.

All checkouts are immutable public Git commit pins. Run timed installed CLI
subprocesses, not direct imports. Explicitly distinguish command exit from
coverage completeness. No claims of a representative market sample.
"""
from __future__ import annotations
import argparse,hashlib,json,os,platform,statistics,subprocess,time
from pathlib import Path


def checkout(repo:dict,root:Path)->dict:
    name=repo['name'];target=root/name
    url='https://github.com/'+repo['repository']+'.git'
    commit=repo['commit']
    if not (len(commit)==40 and all(ch in '0123456789abcdef' for ch in commit)):
        raise ValueError('Invalid pinned commit')
    if target.exists():raise RuntimeError('Refusing existing checkout '+str(target))
    target.mkdir(parents=True)
    commands=[['git','init','-q',str(target)],
              ['git','-C',str(target),'remote','add','origin',url],
              ['git','-c','core.hooksPath=/dev/null','-C',str(target),'fetch','--no-tags','--depth','1','origin',commit],
              ['git','-c','core.hooksPath=/dev/null','-C',str(target),'checkout','-q','--detach','FETCH_HEAD']]
    for cmd in commands:
        outcome=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180,text=True)
        if outcome.returncode:raise RuntimeError(f'Pinned Git checkout failed for {name}: '+outcome.stderr[-400:])
    head=subprocess.check_output(['git','-C',str(target),'rev-parse','HEAD'],text=True,timeout=10).strip()
    if head!=commit:raise RuntimeError('Pinned commit mismatch '+name)
    # Git metadata and _only_ source files; no dependency install, submodules or code execution.
    return {'name':name,'repository':repo['repository'],'commit':head,'local_path':str(target)}


def measure(cli:Path, directory:Path, repeat:int)->dict:
    rows=[]
    for trial in range(repeat):
        started=time.perf_counter()
        try:
            result=subprocess.run([str(cli),'check',str(directory),'--format','json'],
                                  stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                  text=True,encoding='utf-8',errors='replace',timeout=100,
                                  env={**os.environ,'PYTHONUTF8':'1','PYTHONDONTWRITEBYTECODE':'1'})
            elapsed_ms=round(1000*(time.perf_counter()-started),3)
            parsed=None;err=None
            try:parsed=json.loads(result.stdout)
            except (ValueError,UnicodeError):err=result.stderr[-1500:]+' '+result.stdout[-500:]
            summary=parsed.get('summary',{}) if parsed else {}
            eligible=int(summary.get('python_parsed',0))+int(summary.get('openapi_parsed',0))
            gaps=int(summary.get('unverified',0))
            complete=(result.returncode==0 and parsed is not None and eligible>0 and gaps==0)
            rows.append({'elapsed_ms':elapsed_ms,'returncode':result.returncode,
                         'status':parsed.get('status') if parsed else None,
                         'python_parsed':int(summary.get('python_parsed',0)),
                         'openapi_parsed':int(summary.get('openapi_parsed',0)),
                         'unverified':gaps,'complete_coverage':complete,
                         'cli_completed':result.returncode==0 and parsed is not None,
                         'error':err or (result.stderr[-500:] if result.returncode else None)})
        except subprocess.TimeoutExpired:
            rows.append({'elapsed_ms':100000.0,'returncode':None,'status':'TIMEOUT',
                         'python_parsed':0,'openapi_parsed':0,'unverified':0,
                         'complete_coverage':False,'cli_completed':False,'error':'Timed out after 100s'})
    if any(row['complete_coverage']!=rows[0]['complete_coverage'] or row['status']!=rows[0]['status'] or row['unverified']!=rows[0]['unverified'] for row in rows):
        raise RuntimeError('Non-deterministic scan classification between repeat runs')
    median=round(statistics.median(r['elapsed_ms'] for r in rows),3)
    return {'first_ms':rows[0]['elapsed_ms'],'median_ms':median,
            'min_ms':min(r['elapsed_ms'] for r in rows),
            'max_ms':max(r['elapsed_ms'] for r in rows),
            'repeat':repeat,'outcomes':rows}


def report(sources:Path,checkouts:Path,old:Path,new:Path,output:Path,repeat:int=3):
    manifest=json.loads(sources.read_text());repos=manifest['repositories']
    if len(repos)!=10 or len({r['name'] for r in repos})!=len(repos):raise RuntimeError('Expected 10 independently pinned repositories')
    if repeat<2 or repeat>8:raise ValueError('Repeat count outside audit bounds')
    paths=[];checkouts.mkdir(parents=True,exist_ok=True)
    for row in repos:
        print('PINNED_CHECKOUT',row['name'],row['commit'],flush=True)
        paths.append((row,checkout(row,checkouts)))
    versions={}
    for name,cli in [('baseline',old),('candidate',new)]:
        result=subprocess.run([str(cli),'--version'],capture_output=True,text=True,timeout=20)
        if result.returncode:raise RuntimeError('CLI install validation failed: '+name)
        versions[name]=result.stdout.strip()
    results=[]
    for row,path in paths:
        result={'name':row['name'],'repository':row['repository'],'commit':row['commit'],'kind':row['kind']}
        for kind,cli in [('baseline',old),('candidate',new)]:
            result[kind]=measure(cli,Path(path['local_path']),repeat)
        results.append(result)
        print('PINNED_REPO_CHECK',row['name'],json.dumps({k:{'first_ms':result[k]['first_ms'],'median_ms':result[k]['median_ms'],
                'status':result[k]['outcomes'][0]['status'],'parsed':result[k]['outcomes'][0]['python_parsed'],
                'unverified':result[k]['outcomes'][0]['unverified']} for k in ('baseline','candidate')}),flush=True)
    aggregate={}
    for kind in ('baseline','candidate'):
        aggregate[kind]={
            'total_repositories':len(results),
            'commands_completed':sum(1 for r in results if r[kind]['outcomes'][0]['cli_completed']),
            'complete_source_scans':sum(1 for r in results if r[kind]['outcomes'][0]['complete_coverage']),
            'partial_or_unsupported':sum(1 for r in results if not r[kind]['outcomes'][0]['complete_coverage']),
            'median_first_ms':round(statistics.median(r[kind]['first_ms'] for r in results),3),
            'median_repeated_ms':round(statistics.median(r[kind]['median_ms'] for r in results),3),
        }
    result={'schema':'risu-p5d-cross-platform-first-use-v1',
            'host':{'os':platform.system(),'release':platform.release(),'machine':platform.machine(),
                    'python':platform.python_version()},
            'pinned_manifest_sha256':hashlib.sha256(sources.read_bytes()).hexdigest(),
            'versions':versions,'definitions':{
              'command_completed':'Exit 0 and parseable JSON',
              'complete_source_scan':'Command completed and parsed >=1 Python/OpenAPI file and reported 0 unverified entries',
              'first_diagnosis_ms':'Wall time of first complete CLI process launch+scan+JSON output after installation and checkout',
              'median_repeated_ms':'Median of all independent process launches (including the first); filesystem cache not controlled',
              'caveats':'Runner timings are descriptive, not comparable across runner types or representative of all software. Static scan cannot prove runtime preservation.'},
            'summary':aggregate,'repositories':results}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print('P5D_PINNED_REPO_BENCHMARK_COMPLETE',json.dumps(aggregate),flush=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--sources',type=Path,required=True)
    p.add_argument('--checkouts',type=Path,required=True);p.add_argument('--baseline-cli',type=Path,required=True)
    p.add_argument('--candidate-cli',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--repeat',type=int,default=3)
    a=p.parse_args();report(a.sources,a.checkouts,a.baseline_cli,a.candidate_cli,a.output,a.repeat)
