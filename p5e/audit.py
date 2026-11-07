"""Independent cProfile + full diagnostic equivalence aggregate verifier."""
from __future__ import annotations
import argparse,json,statistics
from pathlib import Path

def audit(root:Path):
    data=json.loads((root/'benchmark.json').read_text())
    rows=data['repositories']
    if len(rows)!=10 or data['summary']['exact_full_verdict_matches']!=10:
        raise RuntimeError('Missing full ten-repo diagnostic audit')
    comparisons=[]
    for item in rows:
        name=item['name']
        old=json.loads((root/'profile'/'baseline'/f'{name}.json').read_text())
        new=json.loads((root/'profile'/'candidate'/f'{name}.json').read_text())
        if old['status']!=new['status'] or old['python_files']!=new['python_files']:
            raise RuntimeError('cProfile changed scan outcome: '+name)
        def get(obj,key,metric):
            return obj['profiled_function_stats'].get(key,{}).get(metric,0)
        old_walk=get(old,'ast.walk','calls')
        new_walk=get(new,'ast.walk','calls')
        if not old_walk or not new_walk:raise RuntimeError('Missing AST profile: '+name)
        if new_walk>old_walk:raise RuntimeError('AST traversal increase: '+name)
        old_rules=get(old,'risu_static._python_rules','cumulative_s')
        new_rules=get(new,'risu_static._python_rules','cumulative_s')
        comparisons.append({'name':name,'python_files':old['python_files'],
            'old_ast_walk_calls':old_walk,'new_ast_walk_calls':new_walk,
            'walk_reduction_pct':round(100*(old_walk-new_walk)/old_walk,2),
            'old_profiled_rules_ms':round(old_rules*1000,2),
            'new_profiled_rules_ms':round(new_rules*1000,2)})
    reduced=sum(x['new_ast_walk_calls']<x['old_ast_walk_calls'] for x in comparisons)
    if reduced<8:raise RuntimeError('Not enough repositories had fewer AST traversals: '+str(reduced))
    summary={'all_ten_full_diagnostic_reports_identical':True,
        'repos_reducing_ast_walk_calls':reduced,
        'median_ast_walk_call_reduction_pct':round(statistics.median(x['walk_reduction_pct'] for x in comparisons),2),
        'timed_cli_median_speedup_ratio':data['summary']['speedup_ratio'],
        'old_cli_median_ms':data['summary']['baseline_median_of_repo_medians_ms'],
        'new_cli_median_ms':data['summary']['optimized_median_of_repo_medians_ms'],
        'new_cli_faster_repo_count':data['summary']['individual_repos_faster']}
    result={'schema':'risu-p5e-cprofile-and-invariance-independent-audit-v1',
        'host_os':data['host_os'],'summary':summary,'repositories':comparisons,
        'interpretation':'cProfile includes profiler overhead. Normal CLI includes process startup; both are run on same runner but cache and load fluctuate.'}
    (root/'INDEPENDENT_AUDIT.json').write_text(json.dumps(result,indent=2)+'\n')
    print('P5E_TEN_REPOS_AST_PROFILE_AND_FULL_REPORT_PARITY_PASS',json.dumps(summary,sort_keys=True),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);a=p.parse_args()
    audit(a.results)
