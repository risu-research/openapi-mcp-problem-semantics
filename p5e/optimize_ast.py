"""P5-E optimize repeated AST walking without changing semantic predicates."""
from __future__ import annotations
import hashlib
from pathlib import Path

def patch(data: str) -> str:
    changes = [
      ('def _api_call_bindings(fn):\n',
       'def _api_call_bindings(fn, nodes=None):\n'),
      ('    for n in ast.walk(fn):\n        if not isinstance(n,(ast.Assign,ast.AnnAssign)):continue\n',
       '    for n in (ast.walk(fn) if nodes is None else nodes):\n        if not isinstance(n,(ast.Assign,ast.AnnAssign)):continue\n'),
      ('    helper_paths={path for path,tree in parsed for fn in _func_nodes(tree)\n',
       '    functions_by_path={path:_func_nodes(tree) for path,tree in parsed}\n'
       '    helper_paths={path for path,tree in parsed for fn in functions_by_path[path]\n'),
      ('        for fn in _func_nodes(tree):\n            bindings=_api_call_bindings(fn)\n            for n in ast.walk(fn):\n',
       '        for fn in functions_by_path[path]:\n'
       '            # One ordered AST walk reused by bindings, branches, slices and handlers.\n'
       '            fn_nodes=list(ast.walk(fn))\n'
       '            bindings=_api_call_bindings(fn, fn_nodes)\n'
       '            for n in fn_nodes:\n'),
      ("                for ret in ast.walk(fn):\n                    if not isinstance(ret,ast.Return) or not isinstance(ret.value,ast.BinOp)",
       "                for ret in fn_nodes:\n                    if not isinstance(ret,ast.Return) or not isinstance(ret.value,ast.BinOp)"),
      ("            for n in ast.walk(fn):\n                if not isinstance(n,ast.Subscript) or not isinstance(n.slice,ast.Slice):continue",
       "            has_error_context=None\n            for n in fn_nodes:\n                if not isinstance(n,ast.Subscript) or not isinstance(n.slice,ast.Slice):continue"),
      ("                context=(fn.name.lower().find('error')>=0 or fn.name=='make_api_request' or\n                         any(isinstance(x,(ast.ExceptHandler,ast.Raise)) for x in ast.walk(fn)))\n                if not context:continue",
       "                if has_error_context is None:\n"
       "                    has_error_context=(fn.name.lower().find('error')>=0 or fn.name=='make_api_request' or\n"
       "                         any(isinstance(x,(ast.ExceptHandler,ast.Raise)) for x in fn_nodes))\n"
       "                if not has_error_context:continue"),
      ("            for n in ast.walk(fn):\n                if not isinstance(n,ast.ExceptHandler) or not n.name:continue",
       "            for n in fn_nodes:\n                if not isinstance(n,ast.ExceptHandler) or not n.name:continue"),
    ]
    for i,(before,after) in enumerate(changes):
        matches=data.count(before)
        if matches!=1:
            raise RuntimeError(f'P5E_PATCH_ANCHOR_{i}_MISMATCH: {matches}')
        data=data.replace(before,after,1)
    return data

if __name__=='__main__':
    import argparse
    a=argparse.ArgumentParser()
    a.add_argument('--source',type=Path,required=True)
    a.add_argument('--dest',type=Path,required=True)
    v=a.parse_args()
    before=v.source.read_text()
    after=patch(before)
    v.dest.parent.mkdir(parents=True,exist_ok=True)
    v.dest.write_text(after)
    print('P5E_AST_WALK_OPTIMIZED',hashlib.sha256(before.encode()).hexdigest(),hashlib.sha256(after.encode()).hexdigest(),flush=True)
