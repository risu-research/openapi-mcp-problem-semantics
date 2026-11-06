"""RISU P4-A preregistered ten-repository offline-only qualification.

Input files are previously fetched and Git-blob-verified public OpenAPI
descriptions. Never imports project code, never invokes service endpoints,
never treats an OpenAPI response as observed consumer behavior.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
FROZEN=json.loads((ROOT/'p4a'/'FROZEN_PREREGISTRATION.json').read_text())
PRODUCT=ROOT/'dist'/'risu_v09_source'
DOWNLOAD=None
RESULT_DIR=None

def limits():
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS,(1500*1024*1024,1500*1024*1024))
        resource.setrlimit(resource.RLIMIT_CPU,(35,35))
        resource.setrlimit(resource.RLIMIT_FSIZE,(1024*1024,1024*1024))
    except ImportError:
        pass

def call(args,timeout=30):
    started=time.monotonic()
    env={k:v for k,v in os.environ.items() if k in
         ('PATH','LANG','LC_ALL','PYTHONPATH','PYTHONDONTWRITEBYTECODE',
          'PYTHONNOUSERSITE','HOME','TMPDIR')}
    env['PYTHONPATH']=str(PRODUCT)
    env['PYTHONNOUSERSITE']='1'
    env['PYTHONDONTWRITEBYTECODE']='1'
    try:
        p=subprocess.run([sys.executable,'-B',*args],
                         cwd='/tmp',env=env,capture_output=True,text=True,
                         timeout=timeout,preexec_fn=limits)
        if p.returncode==0:
            try:
                obj=json.loads(p.stdout)
                return {'status':'COMPLETE','payload':obj,
                        'exit_code':0,'seconds':round(time.monotonic()-started,3)}
            except (ValueError,TypeError):
                return {'status':'INVALID_JSON_OUTPUT','seconds':round(time.monotonic()-started,3)}
        return {'status':'NONZERO_EXIT','exit_code':p.returncode,
                'seconds':round(time.monotonic()-started,3)}
    except subprocess.TimeoutExpired:
        return {'status':'TIME_LIMIT','seconds':round(time.monotonic()-started,3)}
    except (OSError,ValueError) as e:
        return {'status':'EXECUTION_UNAVAILABLE','reason':type(e).__name__,
                'seconds':round(time.monotonic()-started,3)}

def qualified(inputs:Path,output:Path):
    global DOWNLOAD,RESULT_DIR
    DOWNLOAD=inputs
    RESULT_DIR=output
    output.mkdir(exist_ok=True,parents=True)
    download=json.loads((inputs/'download_report.json').read_text())
    by_id={record['id']:record for record in download['projects']}
    items=[]
    for t in FROZEN['fixed_targets']:
        started=time.monotonic()
        src=by_id[t['id']]
        record={'id':t['id'],'repository':t['repository'],'commit':t['commit'],
                'source_file':t['path'],
                'source_sha256':src.get('sha256'),
                'source_git_blob_verified':src['download_status']=='VERIFIED',
                'observed_runtime_mcp_calls':0,
                'external_consumer_calls':0,
                'confirmed_consumer_contract_mismatch':False}
        if src['download_status']!='VERIFIED':
            record['qualification']='FETCH_FAILED'
            record['reason']=src.get('failure_type','FETCH_FAILED')
            items.append(record)
            print('P4A_QUALIFICATION',t['id'],'FETCH_FAILED',flush=True)
            continue
        folder=inputs/t['id']
        # The original path/file name remains unchanged and is NOT renamed
        # to make the product scanner see it.
        filename=folder/t['path']
        if not filename.is_file() or filename.stat().st_size!=t['expected_bytes']:
            record.update(qualification='SOURCE_VERIFICATION_FAILED',
                          reason='UNEXPECTED_SOURCE_FILE')
            items.append(record)
            continue
        first=call([str(PRODUCT/'risu_probe.py'),'first-check',str(folder),'--json'],timeout=20)
        scan=call([str(PRODUCT/'risu_probe.py'),'scan',str(folder),
                   '--format','json'],timeout=30)
        inventory=call([str(ROOT/'p4a'/'inventory.py'),str(filename)],timeout=35)
        record['first_check_elapsed_seconds']=first['seconds']
        record['full_scan_elapsed_seconds']=scan['seconds']
        record['inventory_elapsed_seconds']=inventory['seconds']
        record['first_check_execution']=first['status']
        record['scan_execution']=scan['status']
        record['inventory_execution']=inventory['status']
        if first['status']=='COMPLETE':
            obj=first['payload']
            record['first_check']={k:obj.get(k) for k in
                ('version','status','execution','network_requests',
                 'files_examined','findings','incomplete')}
        if scan['status']=='COMPLETE':
            obj=scan['payload']
            record['static_status']=obj.get('status')
            record['static_summary']=obj.get('summary',{})
            record['static_findings']=[{'rule_id':f.get('rule_id'),
                                       'verdict':f.get('verdict'),
                                       'confidence':f.get('confidence')}
                                      for f in obj.get('findings',[])]
            record['static_incomplete']=[{'path':x.get('path'),
                                          'reason':x.get('reason')}
                                         for x in obj.get('incomplete',[])][:12]
        if inventory['status']=='COMPLETE':
            obj=inventory['payload']
            record['inventory_status']=obj.get('status')
            if obj.get('status')=='PARSED':
                record['declared_contract_inventory']=obj.get('inventory')
            else:
                record['inventory_reason']=obj.get('reason','PARSE_UNSUPPORTED')
        if any(x['status']!='COMPLETE' for x in (first,scan,inventory)):
            record['qualification']='INCOMPLETE_EXECUTION'
        elif record.get('inventory_status')!='PARSED':
            record['qualification']='SPEC_INVALID_OR_UNSUPPORTED'
        elif record.get('static_status') in ('PARTIAL','UNVERIFIED') or (
             record.get('static_summary',{}).get('incomplete_files',0)>0):
            record['qualification']='STATIC_UNVERIFIED_OR_PARTIAL'
        elif record.get('static_findings'):
            record['qualification']='STATIC_SUSPECTED_ONLY'
        else:
            record['qualification']='STATIC_NO_FINDINGS'
        record['project_analysis_seconds']=round(time.monotonic()-started,3)
        items.append(record)
        print('P4A_QUALIFICATION',t['id'],record['qualification'],
              'GET',record.get('declared_contract_inventory',{}).get('get_operations','-'),
              'RISU',record.get('static_summary',{}).get('openapi_parsed','-'),
              flush=True)
    expected={t['id'] for t in FROZEN['fixed_targets']}
    assert len(items)==10 and {x['id'] for x in items}==expected
    summary={}
    for i in items:summary[i['qualification']]=summary.get(i['qualification'],0)+1
    result={
      'schema':'risu-p4a-qualification-v1',
      'product_version':'0.9.6-experimental',
      'preregistered_project_count':10,
      'projects_in_denominator':len(items),
      'qualification_counts':summary,
      'verified_source_count':sum(i['source_git_blob_verified'] for i in items),
      'static_recognized_projects':sum(
         i.get('static_summary',{}).get('openapi_parsed',0)>0 for i in items),
      'total_declared_GET_operations_in_parsed_specs':sum(
         i.get('declared_contract_inventory',{}).get('get_operations',0) for i in items),
      'total_declared_GETs_with_error_or_default':sum(
         i.get('declared_contract_inventory',{}).get('get_with_any_error_or_default',0) for i in items),
      'confirmed_real_consumer_mismatches':0,
      'independent_developer_onboarding_measured':False,
      'claim_boundary':'Public committed OpenAPI declaration inventory and v0.9.6 offline scanner only. No vendor API, live MCP converter, actual SDK consumer, external developer, or new production defect was tested.',
      'projects':items
    }
    (output/'P4A_10_PROJECT_RESULTS.json').write_text(
        json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print('RISU_P4A_OFFLINE_COMPLETE',json.dumps({
        'projects':len(items),'verified_sources':result['verified_source_count'],
        'scanner_recognized':result['static_recognized_projects'],
        'real_consumer_mismatches':0}),flush=True)

if __name__=='__main__':
    if len(sys.argv)!=3:
        raise SystemExit('Usage: python run_offline.py VERIFIED_INPUT_DIR RESULT_DIR')
    qualified(Path(sys.argv[1]),Path(sys.argv[2]))
