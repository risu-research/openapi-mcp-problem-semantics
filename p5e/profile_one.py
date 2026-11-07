"""cProfile of actual installed RISU scanner on a pinned external checkout."""
from __future__ import annotations
import argparse,cProfile,json,pstats,platform
from pathlib import Path

def profile(repo:Path,out:Path):
    import risu_static
    profiler=cProfile.Profile();profiler.enable()
    report=risu_static.scan(repo)
    profiler.disable()
    stats=pstats.Stats(profiler)
    focus={}
    for (file,line,name),(primitive,total,self_time,cumulative,callers) in stats.stats.items():
        if name in ('_python_rules','_func_nodes','_api_call_bindings','walk','parse','_find_files','scan'):
            key=('ast.' if 'ast.py' in file else 'risu_static.')+name
            cell=focus.setdefault(key,{'calls':0,'self_s':0.0,'cumulative_s':0.0})
            cell['calls']+=total
            cell['self_s']+=self_time
            cell['cumulative_s']+=cumulative
    for v in focus.values():
        for key in ('self_s','cumulative_s'):v[key]=round(v[key],6)
    result={'python_files':report['summary']['python_parsed'],
        'eligible_files':report['summary']['eligible_files'],
        'status':report['status'],'profiled_function_stats':focus,
        'total_profile_calls':stats.total_calls,
        'total_profile_seconds':round(stats.total_tt,6),'os':platform.system()}
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print('P5E_INSTALLED_SCANNER_CPROFILE',
          json.dumps({'repo':repo.name,'ast.walk':focus.get('ast.walk'),
                      '_python_rules':focus.get('risu_static._python_rules')}),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--repo',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();profile(a.repo,a.out)
