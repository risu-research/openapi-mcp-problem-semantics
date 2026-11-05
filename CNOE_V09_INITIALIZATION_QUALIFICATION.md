# RISU Probe CNOE initialization — qualified targeted fix (2026-11-05)

## Status

**PASS:** [audited GitHub Actions run #24](https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42096907252). This experimental branch does not modify `main` or the frozen v0.1.0-rc1 research release.

This qualification uses the **original authenticated RISU Probe v0.8 code** with exactly four edits in `risu_verify.py`. It is an experimental v0.9 compatibility patch, **not** evidence that unchanged v0.8 passed.

## Root-cause analysis

The real CNOE generated server (FastMCP 3.4.0) accepted direct JSON-RPC `initialize` with protocol versions `2025-06-18` and `2025-11-25`; both returned valid server metadata. The original RISU v0.8 `MCPClient` could also directly connect in `legacy` mode and discover `get_order`.

However, the v0.8 fixture module called `Path.resolve()` on an explicitly supplied virtualenv `python` launcher. On symlink-based POSIX environments, this dereferences the virtualenv entry point and may invoke system Python **without the isolated venv dependencies**, causing the server subprocess to close stdout on startup. This mechanism was reproduced with a separate symlinked Python virtualenv. A targeted path-preservation edit, together with explicit handshake-era mode for this known FastMCP 3.4 adapter, allowed the real product to complete its end-to-end execution.

There is **no proof that generic MCP `auto` negotiation fails for every legacy server**. The CNOE-specific legacy mode is a conservative compatibility choice. The general-purpose `MCPClient` implementation remains unchanged.

## Exactly four edits

1. `interpreter=str(exe.resolve())` → `interpreter=str(exe.absolute())`
2. CNOE tool catalog: `protocol='auto'` → `protocol='legacy'`
3. CNOE example auto-planner: `protocol='auto'` → `protocol='legacy'`
4. CNOE HTTP/MCP data collector: `protocol='auto'` → `protocol='legacy'`

Original `risu_verify.py` SHA-256: `154bfe4359739be844730e33aaa1b1eddfa9043ee7a2d6a33d39bf291c2a7676`

Patched SHA-256: `b7c83bada20b3479136be6e9d984307acacabaa8f15a4abcacc075c421ba855a`

The CI reconstructs the original authenticated archive from six committed parts and compares the output file against these **exact four textual replacements**. An unexpected edit fails CI.

## End-to-end result

| Synthetic HTTP case | Verified preservation |
|---|---|
| 200 JSON | PRESERVED |
| 400 JSON error | LOSS |
| 409 Problem Details | LOSS |
| 422 Problem Details | LOSS |

Four planned/captured tool calls; 12 total synthetic local HTTP GETs; **zero unexpected requests**; three error-loss findings. Raw source/MCP sample hashes and all 13 archived generated files were independently audited.

CNOE source is pinned to `8c2b065497cf32ecbb7cf7e28dad3a99c6706c3f`. Runtime constraints: `--network none`, `--read-only`, non-root UID 65534, no added Linux capabilities, `no-new-privileges`, memory/CPU/PID limits, and synthetic localhost data only. Build-time dependency retrieval is separate from offline runtime.

Run artifact: `risu-v09-real-product-isolated-cnoe` (GitHub artifact ID `13447083877`, SHA-256 `0518ab830e7e50295636c7483b76801c505218ba2c403e6874e65951ee34ca5d`).

## Honest limits

This qualification does not establish production impact, general protocol compliance, exact Python line-execution coverage, or absolute container security. Some older subprocess-heavy test modules still show intermittent latency. The changed v0.9 adapter is qualified here only for this pinned CNOE generated server and synthetic fixture profile. An independent adoption/release decision belongs after broader compatibility testing.
