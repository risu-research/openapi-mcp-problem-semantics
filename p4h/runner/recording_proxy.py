"""Byte-transparent stdio proxy; saves original JSONRPC bytes, no synthesis."""
import os, subprocess, sys, threading
from pathlib import Path
assert len(sys.argv)==4
logfile,server_script,base=sys.argv[1:]
assert base.startswith('http://127.0.0.1:')
proc=subprocess.Popen([sys.executable,'-B',server_script,base],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,bufsize=0)
lock=threading.Lock()
log=Path(logfile).open('ab',buffering=0)
def record(line):
    with lock:log.write(line)
def forward_request():
    try:
        while True:
            line=sys.stdin.buffer.readline()
            if not line:break
            record(line)
            proc.stdin.write(line);proc.stdin.flush()
    finally:
        try:proc.stdin.close()
        except Exception:pass
threading.Thread(target=forward_request,daemon=True).start()
try:
    while True:
        line=proc.stdout.readline()
        if not line:break
        record(line)
        sys.stdout.buffer.write(line);sys.stdout.buffer.flush()
finally:
    try:proc.terminate()
    except Exception:pass
    try:proc.wait(timeout=3)
    except Exception:proc.kill()
    log.close()