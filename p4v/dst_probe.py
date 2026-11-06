"""P4-V: actual published MCP server clock-injected DST-fold wire witness.

The only modification is an in-memory test clock. Installed wheel code stays intact.
"""
import asyncio,importlib.metadata,json,hashlib,sys,os,argparse
from pathlib import Path
WRAPPER=r"""
import asyncio
from datetime import datetime as DT
from zoneinfo import ZoneInfo
import mcp_server_time.server as s
class Frozen(DT):
    @classmethod
    def now(cls,tz=None):
        v=DT(2026,11,1,12,0,tzinfo=ZoneInfo('UTC'))
        return v.astimezone(tz) if tz is not None else v.replace(tzinfo=None)
s.datetime=Frozen
asyncio.run(s.serve('UTC'))
"""
async def run(version,out):
    assert importlib.metadata.version("mcp-server-time")==version
    env={k:v for k,v in os.environ.items() if k in ('PATH','HOME','LANG','SYSTEMROOT')}
    env.update(PYTHONUNBUFFERED='1',PYTHONDONTWRITEBYTECODE='1',TZ='UTC')
    p=await asyncio.create_subprocess_exec(sys.executable,'-c',WRAPPER,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,env=env)
    wires=[]
    async def req(obj):
        b=json.dumps(obj,ensure_ascii=False,separators=(',',':')).encode()+b'\n'
        p.stdin.write(b);await asyncio.wait_for(p.stdin.drain(),15);wires.append(b)
        if 'id' not in obj:return
        for i in range(10):
            line=await asyncio.wait_for(p.stdout.readline(),40)
            if not line or len(line)>2_000_000:raise RuntimeError('Missing/bad external MCP response')
            wires.append(line);response=json.loads(line)
            if response.get('id')==obj['id']:
                if 'error' in response:raise RuntimeError(str(response['error']))
                return response
        raise RuntimeError('Missing matching response id')
    try:
        init=await req({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'RISU-P4V-DST','version':'0'}}})
        assert init['result']['serverInfo']['version']==version
        await req({'jsonrpc':'2.0','method':'notifications/initialized'})
        listing=await req({'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}})
        assert any(x['name']=='convert_time' for x in listing['result']['tools'])
        response=await req({'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'convert_time','arguments':{'source_timezone':'America/New_York','target_timezone':'Europe/London','time':'01:30'}}})
        result=response['result']['structuredContent']
        assert response['result'].get('isError') is not True
        assert result['source']['datetime'].startswith('2026-11-01T01:30:00-04:00')
        later=result.get('later_occurrence')
        if version=='2026.11.4':
            assert isinstance(later,dict), 'Expected genuine non-null new anyOf branch'
            assert later['source']['datetime'].startswith('2026-11-01T01:30:00-05:00')
            assert set(later)=={'note','source','target','time_difference'}
            assert set(later['source'])=={'timezone','datetime','day_of_week','is_dst'}
        else:assert 'later_occurrence' not in result
    finally:
        p.stdin.close()
        try:await asyncio.wait_for(p.wait(),15)
        except asyncio.TimeoutError:p.kill();await p.wait()
        err=(await p.stderr.read()).decode('utf-8','replace')
        if p.returncode:raise RuntimeError('External server exited '+str(p.returncode)+' '+err[-2000:])
    out.mkdir(parents=True,exist_ok=True)
    raw=b''.join(wires)
    (out/'dst_real_stdio_wire.jsonl').write_bytes(raw)
    (out/'dst_actual_response.json').write_text(json.dumps(response,indent=2,sort_keys=True)+'\n')
    record={'version':version,'actual_external_mcp_wire':True,
      'clock_fixture_only':'2026-11-01 US fall-back, fixed in memory',
      'published_wheel_unmodified':True,
      'later_occurrence_nonnull':isinstance(later,dict),
      'wire_sha256':hashlib.sha256(raw).hexdigest(),
      'response_sha256':hashlib.sha256((out/'dst_actual_response.json').read_bytes()).hexdigest()}
    (out/'receipt.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    print('P4V_ACTUAL_DST_BRANCH_PASS',json.dumps(record,sort_keys=True))
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--version',required=True);a.add_argument('--out',required=True,type=Path)
    z=a.parse_args();asyncio.run(run(z.version,z.out))
