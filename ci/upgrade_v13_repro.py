"""Fail-closed RISU v0.9.4 -> v0.9.5 addon after the SHA-verified v0.9-v0.9.4 chain.

Never writes to research main, vendor SDK repositories, or older release
branches. Apply only on the fully restored working tree.
"""
from pathlib import Path
import hashlib
import shutil

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'dist'/'risu_v09_source'
PINS={
 'risu_probe.py':'d1b8eecbd72c4a84d2a2ad87ede796d6f103472f1ec3b3c5a1d149c81e06956a',
 'risu_onboarding.py':'58b031a3ab367ffe753ebf9991bd81aac3519d0d550974764cf55c4e681561e8',
 'risu_static.py':'67142dfa30ed3d4fd0988489b325a65b91a3c4167ffc0240b4bad96695e78a5b',
 'risu_report.py':'2b6231ed09075f7d6b9920b8f0eb1105188939f3bfb20653bab87ec11a831b8c',
 'risu_decision.py':'d186e6399a7ef2708078c34e0cbde67fe1a08bedcb0739172e0ed7325bbe5c88',
 'risu_witness.py':'0049482c2b61c85cd4c62584a3394c151e7796ffcf63b3c65a0c5a2c5cef92c3',
 'pyproject.toml':'b5c31257b7414b9f006736bcc778b5e00481f17ff5f032ba3eba13a86fbab46a'}
for name,expected in PINS.items():
    p=SRC/name
    raw=p.read_bytes().replace(b'\r\n',b'\n')
    actual=hashlib.sha256(raw).hexdigest()
    assert actual==expected,(name,'v0.9.4 anchor failed',expected,actual)
    p.write_bytes(raw)

def replace(name,before,after):
    p=SRC/name
    current=p.read_text(encoding='utf-8')
    assert current.count(before)==1,(name,'expected exactly one pinned string',before)
    p.write_bytes(current.replace(before,after).encode('utf-8'))

for name in ('risu_repair.py','risu_minimize.py','risu_reproduce.py'):
    shutil.copy2(ROOT/'product_v13'/name,SRC/name)

replace('risu_probe.py', "VERSION = '0.9.4-experimental'","VERSION = '0.9.5-experimental'")
replace('risu_probe.py',
 "              +'\\nOther commands: check, plan, plan-auto, collect, analyze, witness, compare, baseline'",
 "              +'\\nOther commands: check, plan, plan-auto, collect, analyze, witness, reproduce, compare, baseline'")
replace('risu_probe.py',
 "    if argv and argv[0]=='witness':\n        from risu_witness import main as witness_main\n        return witness_main(argv[1:])",
 "    if argv and argv[0]=='witness':\n        from risu_witness import main as witness_main\n        return witness_main(argv[1:])\n    if argv and argv[0]=='reproduce':\n        from risu_reproduce import main as reproduce_main\n        return reproduce_main(argv[1:])")
replace('risu_onboarding.py',"'0.9.4-experimental'","'0.9.5-experimental'")
replace('risu_static.py',"'0.9.4-experimental'","'0.9.5-experimental'")
replace('risu_static.py',"'version':'0.9.4'","'version':'0.9.5'")
replace('pyproject.toml','0.9.4.dev0','0.9.5.dev0')
replace('pyproject.toml',
 '"risu_decision", "risu_witness"',
 '"risu_decision", "risu_witness", "risu_repair", "risu_minimize", "risu_reproduce"')
print('RISU 0.9.5 P1 SDK contract reproducer addon verified:')
for name in ('risu_probe.py','risu_repair.py','risu_minimize.py','risu_reproduce.py','pyproject.toml'):
    print(name,hashlib.sha256((SRC/name).read_bytes()).hexdigest())
