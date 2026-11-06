"""Bounded P4-V independent traversal of ACTUAL recorded MCP outputSchema.

Public verifiable check in GitHub CI. Full strict P4-V lens/test pack is in
the separate reproducible master artifact; this script checks live-run facts.
"""
import json,sys,hashlib,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'p4t'))
from risu_contract_history import create_snapshot,diff_snapshots
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
def inspect(schema):
    result={}
    unions={}
    def deref(node,chain):
        for i in range(33):
            if '$ref' not in node:return node,chain
            ref=node['$ref']
            if not isinstance(ref,str) or not ref.startswith('#/$defs/') or ref in chain:raise ValueError('Unresolved, external or cyclic ref')
            chain=chain+(ref,)
            refname=ref[len('#/$defs/'):].replace('~1','/').replace('~0','~')
            node=schema.get('$defs',{}).get(refname)
            if not isinstance(node,dict):raise ValueError('Unresolved local reference')
        raise ValueError('Depth budget')
    def typ(n,chain):
        n,_=deref(n,chain)
        if 'type' in n:return tuple(sorted([n['type']] if isinstance(n['type'],str) else n['type']))
        if 'properties' in n:return ('object',)
        if 'anyOf' in n:return tuple(sorted({t for x in n['anyOf'] for t in typ(x,chain)}))
        return ()
    def visit(n,path,guaranteed,guards,chain,depth):
        if depth>32 or len(result)>5000:raise ValueError('Complexity limit')
        n,chain=deref(n,chain)
        if any(k in n for k in ('allOf','not','if','then','else','patternProperties','$dynamicRef','dependentSchemas','prefixItems')):raise ValueError('Unsupported semantic composition')
        if 'anyOf' in n:
            items=n['anyOf']
            labs=[('type:'+'+'.join(typ(x,chain)),x) for x in items]
            if len(labs)>40 or len(set(x[0] for x in labs))!=len(labs):raise ValueError('Ambiguous anyOf branches')
            unions[path]=sorted(x[0] for x in labs)
            for label,arm in labs:visit(arm,path+'/@anyOf['+label+']',False,guards+1,chain,depth+1)
            return
        props=n.get('properties',{});req=n.get('required',[])
        if not isinstance(props,dict) or not isinstance(req,list) or len(req)!=len(set(req)) or not set(req)<=set(props):raise ValueError('Malformed required fields')
        for name,child in props.items():
            at=path+'/'+name.replace('~','~0').replace('/','~1')
            required=name in req
            result[at]={'types':typ(child,chain),'required_local':required,'unconditional':guaranteed and required and guards==0}
            visit(child,at,guaranteed and required,guards,chain,depth+1)
    visit(schema,'',True,0,(),0)
    return result,unions
def verify(root,out):
    versions=('2026.10.19','2026.11.4')
    for v in versions:
        d=root/v
        m=load(d/'capture_manifest.json')
        assert m['version']==m['server_reported_version']==v
        for name,k in [('mcp_stdio_wire.jsonl','wire_sha256'),('tools_list.json','tools_list_sha256'),('tool_calls.json','tool_calls_sha256')]:
            assert digest(d/name)==m[k]
        wire=[json.loads(x) for x in (d/'mcp_stdio_wire.jsonl').read_text().splitlines()]
        assert load(d/'tools_list.json') in wire
        for call in load(d/'tool_calls.json').values():assert call['response'] in wire
    def tool(v):
        entries=load(root/v/'tools_list.json')['result']['tools']
        return next(x['outputSchema'] for x in entries if x['name']=='convert_time')
    old,new=tool(versions[0]),tool(versions[1])
    a,au=inspect(old);b,bu=inspect(new)
    changes=sorted(set(b)-set(a));removed=sorted(set(a)-set(b))
    assert len(a)==11 and len(b)==24
    assert len(changes)==13 and not removed
    assert changes[0]=='/later_occurrence'
    assert '/later_occurrence/@anyOf[type:object]/source/timezone' in changes
    assert '/later_occurrence/@anyOf[type:object]/target/is_dst' in changes
    assert not any(b[x]['unconditional'] for x in changes)
    assert all(a[x]==b[x] for x in a),'Baseline required fields changed'
    assert bu['/later_occurrence']==['type:null','type:object']
    assert 'later_occurrence' not in load(root/versions[0]/'tool_calls.json')['convert_time']['response']['result']['structuredContent']
    assert load(root/versions[1]/'tool_calls.json')['convert_time']['response']['result']['structuredContent']['later_occurrence'] is None
    base=create_snapshot(str(root/versions[0]/'tools_list.json'),None,versions[0],'convert_time')
    next_snapshot=create_snapshot(str(root/versions[1]/'tools_list.json'),None,versions[1],'convert_time')
    assert diff_snapshots(base,next_snapshot)['summary']['direct_schema_events']==1
    dsta=load(root/'dst'/versions[0]/'receipt.json');dstb=load(root/'dst'/versions[1]/'receipt.json')
    assert not dsta['later_occurrence_nonnull'] and dstb['later_occurrence_nonnull']
    report={'source':'two published releases; actual stdio MCP tools/list + tools/call; date-injected DST branch',
            'old_fields':len(a),'new_fields':len(b),'new_direct_optional_fields':1,'conditional_nested_added':12,
            'unconditionally_required_new':0,'real_dst_non_null_branch':True,
            'no_operator_policy_provided':True,
            'limitation':'Declared schema change and synthetic fixed-clock runtime branch only, not third-party contract breach or production loss.'}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    print('P4V_TWO_REAL_PUBLISHED_MCP_REF_ANYOF_NESTED_VERIFIED',json.dumps(report,sort_keys=True))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--captures',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();verify(a.captures,a.out)
