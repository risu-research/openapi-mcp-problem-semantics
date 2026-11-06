"""Read-only count of externally documented OpenAPI contracts.

This is an independent *spec inventory*, NOT a finding of a real bug,
consumer-code mismatch, MCP protocol violation, or observed API behavior.
Never dereference remote $ref links; never execute or call target servers.
"""
import json
from pathlib import Path
import sys

def inspect(file:Path):
    data=file.read_bytes()
    text=data.decode('utf-8')
    if file.suffix.lower()=='.json':
        source=json.loads(text)
    elif file.suffix.lower() in ('.yaml','.yml'):
        import yaml
        source=yaml.safe_load(text)
    else:
        raise ValueError('UNSUPPORTED_FILE_SUFFIX')
    if not isinstance(source,dict):
        raise ValueError('OPENAPI_ROOT_NOT_MAPPING')
    version=source.get('openapi',source.get('swagger'))
    if not isinstance(version,str):
        raise ValueError('NO_DECLARED_OPENAPI_VERSION')
    paths=source.get('paths')
    if not isinstance(paths,dict):
        raise ValueError('PATHS_NOT_MAPPING')
    total_get=0
    get_with_4xx=0
    get_with_5xx=0
    get_with_any_error=0
    get_with_json_error=0
    get_with_explicit_example=0
    get_without_error=0
    get_with_2xx=0
    documented_examples=0
    sample=[]
    for raw_path,path_record in paths.items():
        if not isinstance(raw_path,str) or not isinstance(path_record,dict):
            continue
        operation=path_record.get('get')
        if not isinstance(operation,dict):
            continue
        total_get+=1
        responses=operation.get('responses',{})
        if not isinstance(responses,dict):
            responses={}
        statuses=[str(code) for code in responses]
        codes_4=[x for x in statuses if x.startswith('4') and len(x)==3 and x.isdigit()]
        codes_5=[x for x in statuses if x.startswith('5') and len(x)==3 and x.isdigit()]
        has_default='default' in statuses
        if codes_4:get_with_4xx+=1
        if codes_5:get_with_5xx+=1
        if any(x[0:1] in ('4','5') and len(x)==3 and x.isdigit()
               for x in statuses) or has_default:
            get_with_any_error+=1
        else:
            get_without_error+=1
        if any(x.startswith('2') and len(x)==3 and x.isdigit() for x in statuses):
            get_with_2xx+=1
        any_json=False
        example=False
        for key,response in responses.items():
            key=str(key)
            if key!='default' and not (len(key)==3 and key[0] in '45' and key.isdigit()):
                continue
            if not isinstance(response,dict):
                continue
            content=response.get('content',{})
            if not isinstance(content,dict):continue
            for mime,data_info in content.items():
                if not isinstance(mime,str) or not isinstance(data_info,dict):
                    continue
                if 'json' not in mime.lower():continue
                any_json=True
                if 'example' in data_info or isinstance(data_info.get('examples'),dict):
                    example=True
                    documented_examples+=1
        if any_json:get_with_json_error+=1
        if example:get_with_explicit_example+=1
        if len(sample)<3 and (codes_4 or codes_5 or has_default):
            sample.append({'method':'GET','path':raw_path,'error_response_keys':[
                k for k in statuses if k in (*codes_4,*codes_5,'default')][:7]})
    return {
      'kind':'EXTERNAL_OPENAPI_DECLARATIONS_ONLY',
      'declared_version':version,
      'title_present':isinstance(source.get('info'),dict) and
                      isinstance(source['info'].get('title'),str),
      'paths_total':len(paths),
      'get_operations':total_get,
      'get_with_documented_2xx':get_with_2xx,
      'get_with_explicit_4xx':get_with_4xx,
      'get_with_explicit_5xx':get_with_5xx,
      'get_with_any_error_or_default':get_with_any_error,
      'get_without_error_or_default':get_without_error,
      'get_with_json_error_response_content':get_with_json_error,
      'get_with_explicit_json_error_example':get_with_explicit_example,
      'error_json_example_declarations':documented_examples,
      'representative_error_get_declarations':sample,
      'actual_error_data_observed':False,
      'actual_MCP_call_executed':False,
      'real_consumer_source_examined':False,
      'confirmed_consumer_contract_mismatch':False
    }

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Usage: inventory.py FILE')
    try:
        print(json.dumps({'status':'PARSED','inventory':inspect(Path(sys.argv[1]))}))
    except (OSError,ValueError,TypeError,UnicodeError,RecursionError,
            MemoryError) as exc:
        print(json.dumps({'status':'INCOMPLETE','reason':type(exc).__name__}))
        raise SystemExit(0)
