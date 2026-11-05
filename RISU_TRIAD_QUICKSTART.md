# RISU Probe — three independent OpenAPI-to-MCP projects

**Status:** experimental reproducibility lab; the v0.9.1 product remains the verified baseline. Do not treat this benchmark as proof of ecosystem prevalence or MCP protocol nonconformance.

## 10-minute first-diagnosis challenge

The three implementations are external, independently maintained projects. The fixture is deliberately synthetic and common to all implementations. All runtime requests are local `GET /orders/{id}` and are counted. We check HTTP 200, 400, 409, and 422, compare the actual returned MCP result with the original HTTP body and status, and require a separate no-loss reference control.

- FastMCP 4.1.6: OpenAPI conversion in a real FastMCP server.
- CNOE `openapi-mcp-codegen` pinned commit `8c2b065497cf32ecbb7cf7e28dad3a99c6706c3f`: actual generated Python server. Its dependency environment is separate because of MCP version differences.
- MCPGen pinned commit `30ee7cb9c2e923ce901e788b0d911f6547772866`: generated policy-aware server set explicitly to **safe-execute GET only**, never writes.

### For developers: clean Linux/Docker reproduction

Prerequisites: Python 3.11+, Docker Engine, Git; internet for **dependency installation only**. The container used to execute third-party code has no external networking, no privileges, and a read-only filesystem. Run the following in the exact experiment branch, from repository root:

```bash
python3 ci/export_v09_source_portable.py
python3 ci/upgrade_v10_modules.py
python3 -m compileall -q dist/risu_v09_source
mkdir -p results && chmod 777 results
date +%s > results/begin_unix.txt
docker build --pull -f triad/Dockerfile -t risu-triad-probe .
docker run --rm --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges --user 65534:65534 \
  --pids-limit 160 --memory 2g --cpus 2 \
  --tmpfs /tmp:rw,nosuid,nodev,size=512m,mode=1777 \
  --mount type=bind,src="$PWD/results",dst=/results \
  risu-triad-probe
date +%s > results/end_unix.txt
python3 triad/audit_results.py results
chmod 700 results
```

Read `results/THREE_PROJECTS_SUMMARY.json` and `results/INDEPENDENT_AUDIT.json`. The run fails closed when any required project does not produce real evidence. Each project includes a time-to-first-diagnosis measurement **after its dependencies are installed**. Total setup + generation + three probes is measured separately and should be reported without cherry-picking.

On Windows, prefer the project's already-qualified v0.9.1 wheel for local offline `first-check`; the three-project Docker workflow above is qualified on a Linux runner. Do not assume native Windows Docker bind-mount compatibility without a distinct test.

### Safety and interpretive boundaries

- Zero real credentials and zero production API calls. Review all executable server code before adapting this to other projects.
- Only the predetermined synthetic read-only `GET` method is allowed. Unexpected HTTP traffic fails the test. The positive control is a **RISU-maintained reference carrier**, not a claim that an external library preserves all semantics.
- `LOSS` may refer to the loss of a machine-readable **structured carrier**, even when a human-readable textual error remains visible. Do not call this data destruction or a protocol violation without further evidence.
- A deliberate redaction/size limit or a library that defaults to dry-run can be valid product policy. The harness explicitly opts in to safe GET execution when supported and compares observed behavior under that policy.
- Preconfigured demonstrations of three upstream implementations do **not** prove an unaffiliated developer can diagnose an arbitrary fourth project within ten minutes. That is a later adoption benchmark.
- Do not publish captured raw responses from actual APIs; this fixture exports only synthetic metadata and hashes.

## Why this is a distinct product category

Ruff suggests the one-command usability target; uv suggests low-friction packaging; oasdiff already covers OpenAPI contract changes; MCP Inspector already covers connectivity and catalog inspection. RISU Probe is built to answer the narrower before/after question: **which upstream response properties survived or lost their structured form after conversion into actual MCP tool results?** The differential evidence, not another dashboard, is the differentiator.
