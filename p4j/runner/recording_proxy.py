"""Byte-transparent SDK stdio proxy plus monotonic receipt of observed frames."""
import hashlib,json,os,subprocess,sys,threading,time
from pathlib import Path
assert len(sys.argv)==4
logfile,server_script,base=sys.argv[1:]
assert base.startswith('http://127.0.0.1:')
stderr=Path(logfile+'.server_stderr').open('wb',buffering=0)
proc=subprocess.Popen([sys.executable,'-B',server_script,base],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr,bufsize=0)
lock=threading.Lock();log=Path(logfile).open('ab',buffering=0)
events=Path(logfile+'.observed_events.jsonl').open('ab',buffering=0)
def canonical(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
def record(line):
    frame=json.loads(line)
    stamp=time.monotonic_ns()
    kind=('MCP_REQUEST' if frame.get('method')=='tools/call' else
          'MCP_RESPONSE' if ('result' in frame or 'error' in frame) else None)
    with lock:
        log.write(line)
        if kind and 'id' in frame:
            events.write((json.dumps({'kind':kind,'id':frame['id'],'t_ns':stamp,
               'sha256':hashlib.sha256(canonical(frame)).hexdigest()})+'\n').encode())
def forward_request():
    try:
        while True:
            line=sys.stdin.buffer.readline()
            if not line:break
            record(line);proc.stdin.write(line);proc.stdin.flush()
    finally:
        try:proc.stdin.close()
        except Exception:pass
threading.Thread(target=forward_request,daemon=True).start()
try:
    while True:
        line=proc.stdout.readline()
        if not line:break
        record(line);sys.stdout.buffer.write(line);sys.stdout.buffer.flush()
finally:
    try:proc.terminate()
    except Exception:pass
    try:proc.wait(timeout=3)
    except Exception:proc.kill()
    log.close();events.close();stderr.close()
    os._exit(proc.returncode if proc.returncode is not None else 0)
