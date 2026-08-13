# E5 Results — CNOE openapi-mcp-codegen

## Classification

`E5_CONFIRMED`

The current unmodified default-branch target independently reproduces meaningful RFC 9457 semantic loss through its actual generator and generated MCP server.

```text
current official GitHub source
→ openapi-mcp-codegen generator
→ generated API client
→ real local HTTP fixture responses
→ generated MCP tool
→ generated FastMCP server
→ MCP ClientSession tools/call
→ raw CallToolResult
→ carrier-neutral adapter v0.2
→ immutable oracle
```

## Directly observed runtime facts

- Official GitHub metadata resolved `main` to commit `d0d9e1d848c5705d9bfb1f58a82a7e653c9c85c2`; the repository was not archived.
- The target's current Python requirement remained `>=3.13,<4.0`.
- The primary clean environment used Python 3.13.15 and the repository's exact `uv.lock`, including FastMCP 2.11.1 and MCP 1.12.3.
- The unmodified generator produced the generated API client, MCP server, and 15 tools from the supplied immutable `openapi.json`.
- The generated server was run over MCP stdio. Calls used low-level `ClientSession.call_tool()` and retained aliases and nulls from raw `CallToolResult` values.
- `S00-asymmetry` was called twice through generated tool `get_fixture_s00_asymmetry`.
  - Success returned `isError=false` and `structuredContent={"ok":true,"probe":"same-tool"}`.
  - Problem returned `isError=false` and `structuredContent={"error":"API request failed: 403"}`. It had `_meta=null` and no typed embedded Problem Details resource.
- Every corpus failure returned an ordinary successful MCP result whose structured value was only a generic status-based `error` string.
- Oracle summary: 0 `PRESERVED`, 11 `LOSS`, 0 `INVENTED`, 1 `NOT_APPLICABLE`.
- The saved raw results were independently re-fed through the immutable v0.2 adapter and oracle; all normalized observations and verdicts reproduced exactly.
- The adapter's FastMCP E4 regression and typed-resource fairness control still passed.
- All five immutable Phase 5 research-definition hashes matched after execution.
- The target Git worktree remained clean.

## Source-code corroboration

The current generated client retains each non-2xx JSON object internally under `details`. The generated tool then returns only `response["error"]` and drops `details`. Server logs show the complete problem objects at the client layer; raw MCP results show only generic error objects after the tool layer.

The preserved current target templates and all generated sources are listed in `E5_SOURCE_EVIDENCE.sha256` and included in the evidence bundle.

## Interpretation

This is independent confirmation of the tested semantic-loss class, with a different outward failure shape from FastMCP E4. FastMCP 3.4.7 converted the upstream problem to diagnostic error prose with `isError=true`; CNOE's generated tool instead returns a generic structured object with `isError=false`. In both cases the original RFC 9457 object is unavailable in any carrier accepted by the profile.

The CNOE result is especially localized: source and runtime logs demonstrate that the generated API-client layer still possesses the complete JSON error, then the generated tool discards it before FastMCP serializes the return value. That supports an implementation-independent converter-layer loss observation, even though the generated MCP server itself uses FastMCP.

No unsupported retryability, safe-to-retry, idempotency, custom problem type, or RFC 9457 recognition claim appeared in the machine-addressable output.

## Claims not supported

This experiment does not establish that all OpenAPI-to-MCP converters lose Problem Details, that MCP cannot carry typed failures, that one MCP carrier is mandatory, or that every CNOE revision behaves this way. It does not claim that the generic status-based error value is absent; it establishes that the source RFC 9457 semantics are absent.

## Required summary

```text
CLASSIFICATION: E5_CONFIRMED
TARGET_REPO: cnoe-io/openapi-mcp-codegen
TARGET_COMMIT: d0d9e1d848c5705d9bfb1f58a82a7e653c9c85c2
BASELINE_IMMUTABLE: YES
SAME-TOOL SUCCESS MACHINE-ADDRESSABLE: YES
SAME-TOOL PROBLEM RFC9457 MACHINE-ADDRESSABLE: NO
PRESERVED: 0
LOSS: 11
INVENTED: 0
NOT_APPLICABLE: 1
```
