"""No-network regression tests for Windows/Linux and v0.9.1 MCP subprocess safety."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'dist'/'risu_v09_source'
sys.path.insert(0,str(SOURCE))
from risu_probe import MCPClient, ProbeError, VERSION
from risu_process import spawn_stdio, stop_stdio

class PortableRegression(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='risu v091 ')
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def script(self,content):
        p=self.root/('테스트 server '+str(len(list(self.root.glob('*.py'))))+'.py')
        p.write_text(content,encoding='utf-8')
        return [sys.executable,str(p)]

    def test_zero_config_offline_no_execution(self):
        project=self.root/'프로젝트 space'
        project.mkdir()
        (project/'never-run.py').write_text("raise RuntimeError('must not import me')\n",encoding='utf-8')
        p=subprocess.run([sys.executable,str(SOURCE/'risu_probe.py'),'first-check',str(project),'--json'],
                          text=True,capture_output=True,timeout=8)
        self.assertEqual(p.returncode,0,p.stderr)
        obj=json.loads(p.stdout)
        self.assertEqual(obj['execution'],'NONE')
        self.assertEqual(obj['network_requests'],0)
        self.assertEqual(obj['files_examined'],1)

    def test_version_and_help(self):
        for flag in ('--version','--help'):
            p=subprocess.run([sys.executable,str(SOURCE/'risu_probe.py'),flag],
                             text=True,capture_output=True,timeout=8)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertIn('0.9.3',p.stdout)

    def test_modern_legacy_and_auto(self):
        program="""import json,sys
for line in sys.stdin:
    req=json.loads(line)
    if 'id' not in req: continue
    m=req['method']
    if m=='server/discover':
        payload={'supportedVersions':['2026-07-28']}
    elif m=='initialize':
        payload={'protocolVersion':'2025-11-25','capabilities':{},'serverInfo':{'name':'fixture','version':'0'}}
    elif m=='tools/list':
        payload={'tools':[{'name':'echo','inputSchema':{'type':'object'}}]}
    elif m=='tools/call':
        payload={'content':[{'type':'text','text':'ok'}],'isError':False}
    else:
        payload={}
    print(json.dumps({'jsonrpc':'2.0','id':req['id'],'result':payload}),flush=True)
"""
        argv=self.script(program)
        for protocol in ('modern','legacy','auto'):
            with self.subTest(protocol=protocol), MCPClient(argv,protocol=protocol) as client:
                self.assertIn('echo',client.list_tools())
                self.assertEqual(client.call('echo',{})['isError'],False)

    def test_broken_server_exits_without_hang(self):
        argv=self.script("import sys; sys.exit(7)\n")
        started=time.monotonic()
        with self.assertRaises(ProbeError):
            with MCPClient(argv,protocol='modern'): pass
        self.assertLess(time.monotonic()-started,4.0)

    def test_request_timeout_and_cleanup(self):
        argv=self.script("import sys,time\nfor line in sys.stdin: time.sleep(30)\n")
        client=MCPClient(argv,protocol='modern')
        client._spawn()
        p=client.proc
        started=time.monotonic()
        try:
            with self.assertRaises(ProbeError):
                client.request('test',{},timeout=0.3)
        finally:
            client.__exit__(None,None,None)
        self.assertLess(time.monotonic()-started,5.0)
        self.assertIsNotNone(p.poll())

    def test_blocked_stdin_write_has_timeout(self):
        argv=self.script("import sys,time\nsys.stdin.buffer.read(1); time.sleep(30)\n")
        client=MCPClient(argv,protocol='modern')
        client._spawn()
        p=client.proc
        try:
            with self.assertRaises(ProbeError):
                client._send({'jsonrpc':'2.0','payload':'z'*300000},timeout=0.5)
        finally:
            client.__exit__(None,None,None)
        self.assertIsNotNone(p.poll())

    def test_process_stop_is_bounded(self):
        argv=self.script("import time; time.sleep(50)\n")
        proc=spawn_stdio(argv)
        started=time.monotonic()
        stop_stdio(proc)
        self.assertIsNotNone(proc.poll())
        self.assertLess(time.monotonic()-started,6.0)

    def test_descendant_process_is_terminated(self):
        marker=self.root/'child-escaped.txt'
        child=f"import time,pathlib;time.sleep(2.4);pathlib.Path({str(marker)!r}).write_text('escaped')"
        parent=("import subprocess,sys,time\n"
                f"subprocess.Popen([sys.executable,'-c',{child!r}],"
                "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,"
                "stderr=subprocess.DEVNULL)\n"
                "print('READY',flush=True)\ntime.sleep(30)\n")
        proc=spawn_stdio(self.script(parent))
        try:
            self.assertEqual(proc.stdout.readline().strip(),'READY')
        finally:
            stop_stdio(proc)
        time.sleep(2.8)
        self.assertFalse(marker.exists(),'server descendant survived process-tree shutdown')
        self.assertIsNotNone(proc.poll())

    def test_source_version(self):
        self.assertEqual(VERSION,'0.9.3-experimental')

if __name__=='__main__':
    unittest.main(verbosity=2)
