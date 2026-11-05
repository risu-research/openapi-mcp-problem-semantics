#!/usr/bin/env python3
"""Fail-closed independent audit of fresh CNOE capture, synthetic fixture only."""
import hashlib,json,os,zipfile
from pathlib import Path

out=Path(os.environ['RISU_CNOE_OUTPUT'])
p=json.loads((out/'cnoe-current-matrix.json').read_text(encoding='utf-8'))
assert p['status']=='EXECUTED'
head=(out/'CNOE_HEAD.txt').read_text().strip() if (out/'CNOE_HEAD.txt').exists() else None
if head is not None:assert p['generator_commit']==head
assert p['generator']=='cnoe-io/openapi-mcp-codegen'
assert set(p['api_request_counts'])=={'normal','conflict','validation','generic'}
assert all(n==3 for n in p['api_request_counts'].values())
target=p['targets'][0]
rows=target['checks']
plan=p['catalog'].get('explicit_example_auto_mapping')
assert isinstance(plan,list) and len(plan)==4, 'auto mapping cases missing'
assert p['catalog'].get('planning_http_requests')==0, 'planner touched upstream'
assert [x['example_label'] for x in plan]==['normal','conflict','validation','generic']
for planned,captured in zip(plan,rows):
    name=planned['example_label']
    assert planned['tool']=='get_order'
    assert planned['http_method']=='GET'
    assert planned['source_path']=='/orders/'+name
    assert planned['arguments']=={'path_id':name}
    assert captured['check']['tool_arguments']==planned['arguments']
    assert captured['check']['http_path']==planned['source_path']
    assert captured['check']['mapping_source']=='OpenAPI examples + actual tools/list inputSchema'
assert [x['check']['id'] for x in rows]==['normal','conflict','validation','generic']
def sha(obj):
    s=json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'))
    return hashlib.sha256(s.encode('utf-8')).hexdigest()
stats={}
for r in rows:
    name=r['check']['id']
    orig=r['source_sample'];mcp=r['mcp_sample']
    assert sha(orig)==r['source_sha256'],name+' source hash'
    assert sha(mcp)==r['mcp_sha256'],name+' MCP hash'
    assert r['check']['mediated_http_requests']==1,name+' no actual MCP->HTTP call'
    expected={'normal':200,'conflict':409,'validation':422,'generic':400}[name]
    assert orig['status']==expected
    assert mcp.get('resultType') in ('complete',None)
    if name=='normal':
        assert mcp.get('isError') is False
        assert mcp.get('structuredContent')==orig['body']
    else:
        assert mcp.get('isError') is False
        assert mcp.get('structuredContent')!=orig['body']
    if name=='validation':
        assert len(orig['body']['errors'])==30
        assert orig['body']['critical_tail']=='RISU_CURRENT_CODEGEN_TAIL_7c6ab16f'
    stats[name]={'status':expected,'isError':mcp.get('isError'),'machine_exact':mcp.get('structuredContent')==orig['body']}
ledger=json.loads((out/'GENERATED_SHA256.json').read_text())
with zipfile.ZipFile(out/'generated-code.zip') as z:
    assert {n for n in z.namelist() if not n.endswith('/')}==set(ledger), 'generated sources missing'
    for name, digest in ledger.items():
        assert hashlib.sha256(z.read(name)).hexdigest()==digest, 'generated source hash mismatch '+name

# v0.8 design cross-check: inspect saved actual CNOE generated Python AST and
# link observed MCP result loss to the registered tool. This is NOT line coverage,
# and this runner is independent from the packaged v0.8 Python implementation.
import ast
with zipfile.ZipFile(out/'generated-code.zip') as z:
    tool_path='mcp_risucheck/tools/orders_id.py'
    api_path='mcp_risucheck/api/client.py'
    server_path='mcp_risucheck/server.py'
    tool_tree=ast.parse(z.read(tool_path).decode('utf-8'))
    api_tree=ast.parse(z.read(api_path).decode('utf-8'))
    server_tree=ast.parse(z.read(server_path).decode('utf-8'))
    tool_funcs=[f for f in ast.walk(tool_tree) if isinstance(f,(ast.FunctionDef,ast.AsyncFunctionDef)) and f.name=='get_order']
    assert len(tool_funcs)==1
    fn=tool_funcs[0]
    assert any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='make_api_request' for n in ast.walk(fn))
    suspicious=[]
    for n in ast.walk(fn):
        if not isinstance(n,ast.If) or not isinstance(n.test,ast.UnaryOp) or not isinstance(n.test.op,ast.Not):continue
        for ret in (r for s in n.body for r in ast.walk(s) if isinstance(r,ast.Return)):
            if not isinstance(ret.value,ast.Dict):continue
            keys=[k.value for k in ret.value.keys if isinstance(k,ast.Constant)]
            if keys==['error']:
                suspicious.append(ret.lineno)
    assert len(suspicious)==1, 'failed to locate exact error-only return path'
    helpers=[f for f in ast.walk(api_tree) if isinstance(f,(ast.FunctionDef,ast.AsyncFunctionDef)) and f.name=='make_api_request']
    assert len(helpers)==1
    assert any(isinstance(n,ast.Return) and isinstance(n.value,ast.Tuple)
               and len(n.value.elts)==2
               and isinstance(n.value.elts[0],ast.Constant) and n.value.elts[0].value is False
               and isinstance(n.value.elts[1],ast.Dict)
               and {'error','details'}<=set(k.value for k in n.value.elts[1].keys if isinstance(k,ast.Constant))
               for n in ast.walk(helpers[0]))
    assert any(isinstance(n,ast.Call) and len(n.args)==1
               and isinstance(n.func,ast.Call) and isinstance(n.func.func,ast.Attribute)
               and n.func.func.attr=='tool'
               and isinstance(n.args[0],ast.Attribute) and isinstance(n.args[0].value,ast.Name)
               and n.args[0].value.id=='orders_id' and n.args[0].attr=='get_order'
               for n in ast.walk(server_tree))
    assert stats['normal']['machine_exact'] is True
    assert all(stats[x]['machine_exact'] is False for x in ('conflict','validation','generic'))
    evidence_link={'classification':'BEHAVIORALLY_CORROBORATED_NOT_LINE_COVERAGE',
                   'static_path':tool_path,'rule_id':'RPY101',
                   'static_line':suspicious[0],
                   'producer':api_path,
                   'registered_tool':'get_order',
                   'captured_error_cases':['conflict','validation','generic'],
                   'positive_control':'normal',
                   'note':'Actual CNOE code generation and MCP execution; AST registration association; no Python line tracing'}
    (out/'STATIC_DYNAMIC_LINK.json').write_text(json.dumps(evidence_link,indent=2)+'\\n')

print(json.dumps({'verdict':'PASS','cases':stats,'generator_commit':p['generator_commit'],
                  'generated_files_hashed':len(ledger),'api_request_counts':p['api_request_counts']},indent=2))
