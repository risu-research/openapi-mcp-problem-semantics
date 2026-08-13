from __future__ import annotations
import hashlib, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent

def sha(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()

def load_json(rel: str):
    return json.loads((ROOT/rel).read_text())

def must(cond: bool, msg: str):
    if not cond:
        raise SystemExit(msg)

expected_frozen = {
    'conformance/cases.json': '2a34f7624b88905c6509a70ede7fe17508c0005129b815886c56c5372559255f',
    'conformance/cases.executable.json': '3efc5079560f12faae1948bd6dbfb689e290b324b125f3e65d6a4b70d803a053',
    'conformance/openapi.json': '8a1b643642143c8149f40b3d1b687776fb847b5069deca1d4a988c2b33ab98f1',
    'conformance/oracle.py': '1f7c203280febcae0523131fa61a98cc741d47c177d193259ee345f2efa9e456',
    'conformance/carrier_neutral_adapter_v02.py': 'db8ad3dc9cf39b8bd9ad922696e47773530ee05741a95a17f0b38c5ad7a248e5',
}
for rel, exp in expected_frozen.items():
    got = sha(ROOT/rel)
    must(got == exp, f'HASH FAIL {rel}: {got} != {exp}')

result_expectations = [
    ('evidence/results/E4_fastmcp_3.4.7.json', {'preserved':0,'loss':11,'invented':0,'not_applicable':1}),
    ('evidence/results/E5_cnoe.json', {'preserved':0,'loss':11,'invented':0,'not_applicable':1}),
    ('evidence/results/E6_openapi-to-mcp.json', {'preserved':0,'loss':11,'invented':0,'not_applicable':1}),
    ('evidence/results/E7_reference.json', {'preserved':11,'loss':0,'invented':0,'not_applicable':1}),
    ('evidence/results/RC1_cleanroom.json', {'preserved':11,'loss':0,'invented':0,'not_applicable':1}),
]
for rel, exp in result_expectations:
    d = load_json(rel)
    s = d['summary']
    got = {k:s[k] for k in exp}
    must(got == exp, f'RESULT FAIL {rel}: {got} != {exp}')

# Frozen corpus cardinality.
cases = load_json('conformance/cases.executable.json')['cases']
case_ids = [c['id'] for c in cases]
must(len(case_ids) == 12 and len(set(case_ids)) == 12, 'CORPUS FAIL: expected 12 unique case ids')

# RC1 provenance and fresh-dependency assertions.
prov = load_json('evidence/provenance/RC1_CLEANROOM_PROVENANCE.json')
clean = prov['cleanroom']
must(prov['classification'] == 'RC1_CLEANROOM_CONFIRMED', 'RC1 classification mismatch')
for key in ['copied_prior_node_modules','copied_prior_compiled_dist','copied_prior_raw_observations_into_primary_replay','prior_running_fixture_or_server_reused']:
    must(clean[key] is False, f'RC1 cleanroom negative control failed: {key}')
for key in ['new_empty_npm_cache_used_for_target_install','fresh_node_modules_materialized','fresh_fixture_process','fresh_server_process','fresh_client_process']:
    must(clean[key] is True, f'RC1 cleanroom positive control failed: {key}')
must(prov['fresh_observation']['protocol'] == '2026-07-28', 'RC1 protocol mismatch')
must(prov['fresh_observation']['protocol_era'] == 'modern', 'RC1 protocol era mismatch')
must(prov['oracle_result']['negative_text_demotion'] == 'PASS (oracle verdict LOSS)', 'negative demotion mismatch')

# Evidence-derived process/wire topology: do not trust a hard-coded boolean.
client = (ROOT/'evidence/rc1_cleanroom/bridge_src/reference-client.ts').read_text()
tee = (ROOT/'evidence/rc1_cleanroom/bridge_src/wire-tee.ts').read_text()
bridge = (ROOT/'evidence/rc1_cleanroom/bridge_src/reference-bridge.ts').read_text()
process_topology = {
    'client_uses_official_stdio_transport': 'StdioClientTransport' in client,
    'client_launches_wire_tee': 'wire-tee.js' in client and 'new StdioClientTransport' in client,
    'wire_tee_spawns_child': 'spawn(command, args' in tee and 'stdio: ["pipe", "pipe", "pipe"]' in tee,
    'bridge_serves_stdio': 'serveStdio(buildServer' in bridge,
    'bridge_rejects_legacy': 'legacy: "reject"' in bridge,
    'fresh_client_recorded': clean['fresh_client_process'] is True,
    'fresh_server_recorded': clean['fresh_server_process'] is True,
}
must(all(process_topology.values()), 'PROCESS TOPOLOGY FAIL: ' + json.dumps(process_topology, sort_keys=True))

# Exact dependency record.
deps = load_json('evidence/rc1_cleanroom/RC1_INSTALLED_DEPENDENCIES.json')
must(deps['fresh_install']['newly_materialized_dependency_tree'] is True, 'dependency tree not fresh')
must(deps['package_lock_unchanged_after_install'] is True, 'package-lock changed')
for pkg in ['@modelcontextprotocol/client','@modelcontextprotocol/core','@modelcontextprotocol/server']:
    must(deps['packages'][pkg]['version'] == '2.0.0', f'{pkg} version mismatch')

# Correct ledger terminology/counts: RC1 has 36 entries; E7's 39 is a distinct historical ledger.
runlog = (ROOT/'evidence/rc1_cleanroom/RC1_RUN_LOG.txt').read_text()
must('E7 internal SHA256SUMS: PASS (39 files)' in runlog, 'E7 39-file historical ledger evidence missing')
# The immutable RC1 archive's own ledger count was independently audited as 36; retain the forensic record.
forensic = (ROOT/'review/FORENSIC_AUDIT_RC1_CLEANROOM.md').read_text()
must('RC1 `SHA256SUMS` ledger independently verified here contains 36 files' in forensic, 'RC1 36-file ledger audit missing')

# Raw asset index: five distinct immutable historical archives, not embedded in main source ZIP.
asset_lines = [ln for ln in (ROOT/'evidence/RAW_EVIDENCE_ASSETS.sha256').read_text().splitlines() if ln.strip()]
must(len(asset_lines) == 5, f'expected 5 raw evidence asset hashes, got {len(asset_lines)}')
for ln in asset_lines:
    must(re.fullmatch(r'[0-9a-f]{64}  \S+\.zip', ln) is not None, f'bad asset hash line: {ln}')

# Public-source privacy hygiene: no machine-local absolute user paths or obvious live-secret prefixes in textual files.
for path in ROOT.rglob('*'):
    if not path.is_file() or path.name == 'MANIFEST.sha256':
        continue
    if path.suffix.lower() in {'.zip','.png','.jpg','.jpeg','.gif','.pdf'}:
        continue
    try:
        text = path.read_text(errors='strict')
    except Exception:
        continue
    must(('/'+'Users'+'/') not in text and ('C:'+'\\'+'Users'+'\\') not in text, f'PUBLIC PATH HYGIENE FAIL: {path.relative_to(ROOT)}')
    must(re.search(r'\bsk-[A-Za-z0-9_-]{16,}', text) is None, f'POSSIBLE SECRET FAIL: {path.relative_to(ROOT)}')
    must(re.search(r'\bAKIA[0-9A-Z]{16}\b', text) is None, f'POSSIBLE AWS KEY FAIL: {path.relative_to(ROOT)}')

# Publication wrapper metadata.
must((ROOT/'LICENSE').exists(), 'LICENSE missing')
must((ROOT/'CITATION.cff').exists(), 'CITATION.cff missing')
must((ROOT/'.gitignore').exists(), '.gitignore missing')
citation_text = (ROOT/'CITATION.cff').read_text()
must('https://github.com/risu-research/openapi-mcp-problem-semantics' in citation_text, 'canonical repository URL missing from CITATION.cff')
must('version: "0.1.0-rc1"' in citation_text, 'CITATION version mismatch')
must('license: Apache-2.0' in citation_text, 'CITATION license mismatch')

# Public source manifest must cover every file except itself and validate all recorded hashes.
manifest_path = ROOT/'MANIFEST.sha256'
manifest_lines = [ln for ln in manifest_path.read_text().splitlines() if ln.strip()]
manifest_entries = {}
for ln in manifest_lines:
    parts = ln.split('  ', 1)
    must(len(parts) == 2 and re.fullmatch(r'[0-9a-f]{64}', parts[0]) is not None, f'bad manifest line: {ln}')
    manifest_entries[parts[1]] = parts[0]
actual_files = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file() and p.name != 'MANIFEST.sha256'}
must(set(manifest_entries) == actual_files, f'MANIFEST COVERAGE FAIL: missing={sorted(actual_files-set(manifest_entries))} extra={sorted(set(manifest_entries)-actual_files)}')
for rel, exp in manifest_entries.items():
    got = sha(ROOT/rel)
    must(got == exp, f'MANIFEST HASH FAIL {rel}: {got} != {exp}')

print('RC1 release verification: PASS')
print('version: 0.1.0-rc1')
print('frozen files:', len(expected_frozen))
print('result snapshots:', len(result_expectations))
print('corpus cases:', len(case_ids))
print('raw evidence asset hashes:', len(asset_lines))
print('process topology derived from evidence: PASS')
print('RC1 ledger terminology: E7=39 historical; RC1=36 audited')
