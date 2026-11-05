# RISU Probe v0.9.1 experimental preview — Windows, lifecycle, first run

**Scope:** an incremental, developer-preview patch to authenticated RISU Probe v0.9. Not a PyPI release or a declaration of full MCP conformance. The original research `main` branch remains unchanged.

## Why this patch exists

An independent cross-platform v0.9 audit exposed a real Python 3.11 syntax failure in `risu_report.py` (a nested f-string expression parsed only on newer versions). The v0.9 pinned CNOE and multi-server GitHub Actions checks previously qualified interoperability, but were Linux-only and did not explicitly gate native Windows subprocess behavior or an immediate clean-wheel first run.

The fix is deliberately small: retain the v0.9 data-loss diagnostic engine, add a Python 3.11-compatible markdown report expression, bounded subprocess stdin writes, process-tree teardown, a safe offline `first-check` entry point, and a distributable wheel with its Apache-2.0 license.

**Final 2026-11-05 qualification: PASS.** [GitHub Actions #42128201010](https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42128201010) completed **6/6 jobs successfully**: Windows and Ubuntu with Python 3.11, 3.12 and 3.13. Each job executed the 9 local regression tests, whole-source syntax check, preview wheel build and fresh virtualenv install. The Python 3.13 Windows and Ubuntu jobs additionally passed 6 real pinned SDK/FastMCP/legacy server calls each and the forced-modern negative control. GitHub artifact ID: `13460794835`. Independent download audit confirmed the 14 preview Python module bytes exactly match the packaged wheel, and wheel includes Apache-2.0 LICENSE. Wheel SHA-256: `7e8fc3d5aa32d3c8eb10489822d35aceab53424c8b3bd054a779728da312c1c9`.

## Provenance and reproducibility

1. `ci/export_v09_source_portable.py` independently authenticates the original 12-module v0.8 source archive by SHA-256, reconstructs the exact four qualified compatibility fixes, and checks the two exact promoted v0.9 hashes.
2. `ci/upgrade_v10_modules.py` applies exact-match patch hunks to the authenticated v0.9, failing if source shapes do not match, then adds `risu_process.py`, `risu_onboarding.py`, the package metadata, and the repository license.
3. CI compiles every module and runs 9 local, no-network subprocess and first-use regressions on Windows and Ubuntu across Python 3.11, 3.12, and 3.13.
4. It builds `risu_probe_preview-0.9.1.dev0-py3-none-any.whl`, creates a new virtual environment, installs the wheel with `--no-index --no-deps`, and verifies the real `risu-probe` console executable.
5. On Windows and Ubuntu Python 3.13 only, pinned official MCP SDK 2.3.0, FastMCP 4.1.6 and fastmcp-slim 4.1.6 run synthetic `echo` MCP servers: `modern`/`auto` against each modern server, `legacy`/`auto` against the legacy control, and forced modern vs legacy must fail.
6. The successful GitHub Actions job produces the exact preview wheel and source for download.

**Published CI evidence:**
- [v0.9 real CNOE and three-server cross-check (run #31)](https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42100196872)
- [v0.9.1 native Windows/Linux, Python 3.11/3.13, real SDK+FastMCP and 9 lifecycle regressions](https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42127710074)
- [v0.9.1 expanded Python 3.11/3.12/3.13 qualification](https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42128201010)

## First run on Windows (PowerShell)

After extracting the preview wheel to your project folder:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-index --no-deps .\risu_probe_preview-0.9.1.dev0-py3-none-any.whl
.\.venv\Scripts\risu-probe.exe first-check .
.\.venv\Scripts\risu-probe.exe first-check . --json
```

The first check **only parses** supported local Python and OpenAPI files. It does not import the target code, launch MCP servers, call APIs, or verify that runtime behavior preserves semantics. Findings are hypotheses. If no supported files are present or a file cannot be parsed, read the `UNVERIFIED`/`PARTIAL` status before relying on the summary. Existing `scan`, `plan-auto`, `verify` and other commands remain accessible; any executable server test requires explicit opt-in and review.

## Tested and untested boundaries

- **Tested:** package source restoration, source compilation, clean-wheel install, safe offline first scan, Unicode/spaced paths, modern/legacy/auto protocol initialization in synthetic tests, subprocess crashing, blocked stdin, no-response timeout, termination of subprocess descendants, and the actual pinned SDK/FastMCP synthetic echo cases.
- **Previously tested at v0.9:** actual CNOE-generated server with 4 synthetic upstream HTTP/MCP cases under an isolated Linux container.
- **Not newly requalified at v0.9.1:** the full v0.9 legacy 232-test collection, the CNOE four-case integration in its complete pinned Docker fixture, arbitrary MCP servers, production HTTP APIs, remote transports, macOS, heavy concurrent loads, or third-party adoption. Support beyond the explicitly tested Python versions remains a declared compatibility intention.
- **Security scope:** the first scan runs no target code, but explicit live server execution remains executable third-party code and should be performed only on reviewed fixtures. The downloadable wheel is an experimental preview and must not be interpreted as a production API safety certification.

## Product positioning

This project is a **before/after, evidence-backed transformation-loss detector**, not a generic OpenAPI version diff tool or a general MCP protocol inspector. The next product milestone should be three independently maintained integrations that find actionable differences and are reproducible by an outside developer within ten minutes, with verified false-positive controls and safe opt-in.
