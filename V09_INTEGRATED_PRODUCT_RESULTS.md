# RISU Probe v0.9 integrated product: real-server regression qualification

**Completed 2026-11-05. Experimental source and qualification branch.** Original `main` and frozen research release are unchanged.

## Verified integrated source

- [GitHub Actions #31 — completed, all steps PASS](https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42100196872)
- The build starts from the authenticated v0.8 module bundle, applies the **four already qualified CNOE interoperability fixes**, then applies four narrowly scoped product version / output-label updates. An independent auditor reconstructs both modified source files from the original tar archive and rejects any extra source changes.
- SHA256 `risu_probe.py`: `d2a9af2b19a17d33925d64f2ced8b0e52442577fcecba020bdcccd360bb070f1`
- SHA256 `risu_verify.py`: `4bdbae7da26ea308333f45d668176a65cfacb890f9bc30e0ca4a9ca583f612b0`
- Both exact byte strings were also verified against the downloadable v0.9 wheel's bundled modules.
- v0.9 product version: `0.9.0-experimental`. This is a *developer preview*, not a PyPI publishing claim.

## Real MCP server matrix

| Server | Mode(s) tested | Actual call result |
|---|---|---|
| Fresh pinned CNOE-generated server, FastMCP 3.4 runtime | fixture-specific legacy | 4 HTTP/MCP pairs captured; 200 preserved, 400/409/422 LOSS |
| Official MCP Python SDK 2.3.0 server | modern, auto | 2 synthetic `echo` calls preserved |
| Real FastMCP 4.1.6 server | modern, auto | 2 synthetic `echo` calls preserved |
| Independent stdlib legacy test server | legacy, auto | 2 synthetic `echo` calls preserved |
| Legacy server under forced modern-only setting | modern | Correctly rejected (negative control) |

The CNOE fixture recorded **12 localhost GETs** (three per case) and **zero unexpected requests**. The other three targets use harmless synthetic echo tools, no production API.

**Isolation:** Different pinned virtualenvs for CNOE and modern MCP libraries, Docker runtime `--network none`, `--read-only`, non-root UID 65534, no new privileges/capabilities, memory/PID/CPU bounds.

**Results:** `AUDIT.json` verdict `PASS`, six non-CNOE protocol transport calls passed, independent hash and module-provenance audit passed, and the GitHub evidence archive is `risu-v09-cross-server-qualification` (artifact ID `13449627951`, SHA-256 `38521dae9f58a5dc2fb97d8f0128319f841562a705fd2d01230cdc52e3581fb2`).

## Precise limits

The data establish interoperability in these pinned configurations and particular tools, **not** full MCP conformance, production API prevalence, arbitrary third-party code safety, or all transports/operating systems. Local product tests were run independently by module because earlier subprocess-heavy suites intermittently delayed under combined execution.

## Product source vs build recipe

The branch contains the authenticated-source reconstruction and strict-delta build recipe, the actual server implementations, and the fail-closed CI audit. The complete integrated v0.9 developer-preview source (including all tests, demos, docs and a installable wheel) is distributed in the project ZIP alongside this verified CI artifact.
