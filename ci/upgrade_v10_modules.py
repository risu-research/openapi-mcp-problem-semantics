"""Exactly scoped v0.9 -> v0.9.1 experimental developer-preview upgrade.
Must run only after ci/export_v09_source_portable.py authenticates v0.9.
"""
from pathlib import Path
import hashlib
import shutil

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'dist'/'risu_v09_source'
assert SOURCE.is_dir()

def replace(name,before,after):
    path=SOURCE/name
    value=path.read_text(encoding='utf-8')
    assert value.count(before)==1,(name,'expected one occurrence',before[:90])
    path.write_bytes(value.replace(before,after).encode('utf-8'))

replace('risu_report.py',
    """        lines.append(f'| {esc(item.get("id", "?"))} | {esc(item.get("verdict", "?"))+scope+mark} | {esc(finding)}{(' [' + esc(found) + ']') if found else ''} |')""",
    """        diagnostic = ' [' + esc(found) + ']' if found else ''
        lines.append(f'| {esc(item.get("id", "?"))} | {esc(item.get("verdict", "?"))+scope+mark} | {esc(finding)}{diagnostic} |')""")
replace('risu_probe.py', 'import subprocess\n',
    'import subprocess\nfrom risu_process import spawn_stdio, stop_stdio, write_with_timeout\n')
replace('risu_probe.py',
    """        self.proc=subprocess.Popen(self.argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL,text=True,bufsize=1,env=self.env)""",
    """        self.proc=spawn_stdio(self.argv,env=self.env)""")
replace('risu_probe.py',
    """    def __exit__(self,*_):
        if self.proc:
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    self.proc.kill(); self.proc.wait(timeout=1.0)
            for x in (self.proc.stdin,self.proc.stdout):
                if x and not x.closed: x.close()
            self.proc=None
""",
    """    def __exit__(self,*_):
        if self.proc:
            proc, self.proc = self.proc, None
            stop_stdio(proc)
""")
replace('risu_probe.py',
    """    def _send(self, data):
        try:
            self.proc.stdin.write(json.dumps(data,separators=(',',':'))+'\\n')
            self.proc.stdin.flush()
        except (OSError, BrokenPipeError) as e:
            raise ProbeError('MCP process ended before request') from e
""",
    """    def _send(self, data, *, timeout=8.0):
        line=json.dumps(data,separators=(',',':'),ensure_ascii=False)+'\\n'
        try:
            write_with_timeout(self.proc, line, timeout)
        except TimeoutError as e:
            raise ProbeError('MCP subprocess stdin write timed out') from e
        except ValueError as e:
            raise ProbeError(str(e)) from e
        except (OSError, BrokenPipeError) as e:
            raise ProbeError('MCP process ended before request') from e
""")
replace('risu_probe.py',
    """        self._send({'jsonrpc':'2.0','id':rid,'method':method,'params':params})
""",
    """        deadline=time.monotonic()+timeout
        self._send({'jsonrpc':'2.0','id':rid,'method':method,'params':params},
                   timeout=max(0.01,deadline-time.monotonic()))
""")
replace('risu_probe.py',
    """        deadline=time.monotonic()+timeout
        while True:
""",
    """        while True:
""")
replace('risu_probe.py',
    """            if '_invalid_line' in resp:
""",
    """            if not isinstance(resp,dict):
                raise ProbeError('MCP server returned a non-object JSON response')
            if '_invalid_line' in resp:
""")
replace('risu_probe.py',
    """    if argv and argv[0]=='verify':
""",
    """    if not argv or argv[0]=='first-check':
        from risu_onboarding import first_check
        return first_check(argv[1:] if argv else [])
    if argv[0] in ('--version', '-V'):
        print('risu-probe '+VERSION)
        return 0
    if argv[0] in ('--help', '-h'):
        print('RISU Probe '+VERSION+'\\n\\nStart safely:  risu-probe first-check [directory]'
              +'\\nOffline scan:   risu-probe scan .'
              +'\\nLive fixture:   risu-probe verify --fixture PROJECT --allow-exec'
              +'\\nOther commands: check, plan, plan-auto, collect, analyze, compare, baseline'
              +'\\n\\nFirst check only reads source. Live commands require explicit execution approval.')
        return 0
    if argv and argv[0]=='verify':
""")
replace('risu_probe.py',"VERSION = '0.9.0-experimental'","VERSION = '0.9.1-experimental'")
for name in ('risu_process.py','risu_onboarding.py','pyproject.toml'):
    shutil.copy2(ROOT/'product_v10'/name,SOURCE/name)

print('RISU v0.9.1 experimental patch applied:')
for name in ('risu_probe.py','risu_report.py','risu_process.py','risu_onboarding.py'):
    print(name,hashlib.sha256((SOURCE/name).read_bytes()).hexdigest())
