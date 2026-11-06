"""Replay two 1-minimal synthetic errors with original pinned SDK dispatchers.

Run with the exact external SDK revisions described by real_contracts.py, and
the RISU v0.9.5 product modules importable. No service/API calls.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
from real_contracts import CONTRACTS,classify_real_sdk

def load_bridge(path:Path):
    spec=importlib.util.spec_from_file_location('local_synthetic_consumer_bridge',str(path))
    if spec is None or spec.loader is None:raise RuntimeError('invalid bridge')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def replay(fixtures:Path,bridge_path:Path):
    bridge=load_bridge(bridge_path)
    rows=[]
    for name,c in CONTRACTS.items():
        obj=json.loads((fixtures/(name+'.json')).read_text(encoding='utf-8'))
        assert obj['contract']==name and obj['status']==c['status']
        native=classify_real_sdk(name,obj['source_body'],c['status'])
        consumed=classify_real_sdk(name,bridge.payload(obj['mcp_result']),c['status'])
        rows.append({'name':name,'expected':c['expected'],
                     'sdk_native':native,'sdk_after_bridge':consumed,
                     'consumer_contract_satisfied':consumed==native==c['expected']})
    return rows

def main():
    p=argparse.ArgumentParser()
    p.add_argument('fixtures',type=Path)
    p.add_argument('--bridge',type=Path,default=Path(__file__).parent/'consumer_bridge.py')
    p.add_argument('--expect',choices=('broken','repaired'),default='repaired')
    args=p.parse_args()
    rows=replay(args.fixtures,args.bridge)
    for row in rows:
        print(row['name'],row['sdk_native'],row['sdk_after_bridge'],
              'SATISFIED' if row['consumer_contract_satisfied'] else 'FAILED')
    want=args.expect=='repaired'
    assert all(row['consumer_contract_satisfied']==want for row in rows),(rows,want)
    print('RISU_REAL_SDK_REPLAY_'+args.expect.upper()+'_PASS')
if __name__=='__main__':
    main()
