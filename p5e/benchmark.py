"""Ten pinned public repos: independent CLI timing and exact JSON diagnostics parity."""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,os,platform,statistics,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('risu_p5d_checkout_lib',ROOT/'p5d'/'benchmark.py')
if spec is None or spec.loader is None:raise RuntimeError('P5-D checkout implementation missing')
checkout_module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(checkout_module)
checkout=checkout_module.checkout

def normalized(report:dict)->dict:
    result=json.loads(json.dumps(report))
    result.pop('version',None)
    result.pop('performance',None)
    return result

def run(cli:Path,target:Path)->dict:
    start=time.perf_counter()
    p=subprocess.run([str(cli),'check',str(target),'--format','json'],
                     capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=110,
                     env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1'})
    elapsed=round((time.perf_counter()-start)*1000,3)
    if p.returncode!=0:raise RuntimeError(f'{target.name} CLI returned {p.returncode}: {p.stderr[-800:]}')
    report=json.loads(p.stdout)
    content=json.dumps(normalized(report),sort_keys=True,ensure_ascii=False).encode()
    return {'ms':elapsed,'report':report,'normalized_sha256':hashlib.sha256(content).hexdigest()}

def compare(sources:Path,checkouts:Path,old:Path,new:Path,out:Path,repeats:int):
    manifest=json.loads(sources.read_text())
    repos=manifest['repositories']
    if len(repos)!=10 or len({r['name'] for r in repos})!=10:raise ValueError('Expected original ten P5-D project pins')
    if not 2<=repeats<=8:raise ValueError('Repeat budget exceeded')
    paths={}
    checkouts.mkdir(parents=True,exist_ok=True)
    for row in repos:
        path=checkout(row,checkouts)
        paths[row['name']]=Path(path['local_path'])
    results=[]
    for row in repos:
        target=paths[row['name']]
        a=[];b=[]
        for i in range(repeats):
            # Alternating order reduces systematic warm-cache advantage.
            if i%2==0:x=run(old,target);y=run(new,target)
            else:y=run(new,target);x=run(old,target)
            if x['normalized_sha256']!=y['normalized_sha256']:
                before=normalized(x['report']);after=normalized(y['report'])
                differences=[key for key in sorted(set(before)|set(after)) if before.get(key)!=after.get(key)]
                raise RuntimeError('P5E_EXACT_DIAGNOSTIC_DRIFT '+row['name']+' '+repr(differences))
            a.append(x);b.append(y)
        r=a[0]['report']
        item={'name':row['name'],'repository':row['repository'],'commit':row['commit'],
              'baseline':{'first_ms':a[0]['ms'],'median_ms':round(statistics.median(x['ms'] for x in a),3)},
              'optimized':{'first_ms':b[0]['ms'],'median_ms':round(statistics.median(x['ms'] for x in b),3)},
              'baseline_samples_ms':[x['ms'] for x in a],
              'optimized_samples_ms':[x['ms'] for x in b],
              'full_diagnostic_payload_sha256':a[0]['normalized_sha256'],
              'status':r['status'],'python_parsed':r['summary']['python_parsed'],
              'openapi_parsed':r['summary']['openapi_parsed'],
              'suspected_findings':len(r['suspected']),
              'unverified':r['summary']['unverified'],
              'full_report_identical_except_display_version':True}
        results.append(item)
        print('P5E_EXACT_REPO_VERDICT_PASS',json.dumps({'name':row['name'],
            'digest':item['full_diagnostic_payload_sha256'],
            'baseline_ms':item['baseline']['median_ms'],
            'candidate_ms':item['optimized']['median_ms'],
            'findings':item['suspected_findings']}),flush=True)
    old_median=round(statistics.median(x['baseline']['median_ms'] for x in results),3)
    new_median=round(statistics.median(x['optimized']['median_ms'] for x in results),3)
    summary={'repo_count':len(results),'exact_full_verdict_matches':10,'different_verdicts':0,
             'baseline_median_of_repo_medians_ms':old_median,
             'optimized_median_of_repo_medians_ms':new_median,
             'speedup_ratio':round(old_median/new_median,3) if new_median else None,
             'individual_repos_faster':sum(x['optimized']['median_ms']<x['baseline']['median_ms'] for x in results)}
    result={'schema':'risu-p5e-cross-platform-exact-verdict-invariance-v1',
            'host_os':platform.system(),'python':platform.python_version(),
            'source_manifest_sha256':hashlib.sha256(sources.read_bytes()).hexdigest(),
            'repeats':repeats,'repositories':results,'summary':summary,
            'caveats':'Includes process startup+JSON; cache/runner load vary. Static scan is not a runtime behavior proof.'}
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+'\n')
    print('P5E_TEN_REPOS_FULL_DIAGNOSTIC_PARITY_PASS',json.dumps(summary,sort_keys=True),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--sources',type=Path,required=True)
    p.add_argument('--checkouts',type=Path,required=True)
    p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--repeat',type=int,default=3)
    a=p.parse_args();compare(a.sources,a.checkouts,a.baseline,a.candidate,a.output,a.repeat)
