# E4 Results — Official FastMCP Distribution, Full MCP Path

## Classification

`E4_CONFIRMED`

FastMCP 3.4.7 remained the latest stable release in official PyPI metadata at execution time. The hash-verified official `fastmcp` and `fastmcp-slim` wheels reproduced the prior semantic-loss observation through the full required path.

```text
official PyPI wheel
→ OpenAPIProvider
→ FastMCP server
→ FastMCP Client
→ Client.call_tool_mcp()
→ raw mcp.types.CallToolResult
→ representation-neutral oracle adapter
```

## 1. Directly observed runtime facts

- The two official wheel SHA-256 values exactly matched the hashes independently obtained from PyPI metadata before installation.
- Runtime versions reported by `importlib.metadata` were `fastmcp==3.4.7` and `fastmcp-slim==3.4.7`.
- Both pre-E4 local baselines passed before the official-package run.
- `S00-asymmetry` was called twice through the same generated tool.
  - `outcome=success` returned `isError=false` and `structuredContent={"ok":true,"probe":"same-tool"}`.
  - `outcome=problem` returned `isError=true`, `structuredContent=null`, and `_meta=null`. The RFC 9457 object appeared only in `content[].text`.
- All 12 corpus cases were exercised with `Client.call_tool_mcp()` and raw results were serialized with aliases and nulls retained.
- Each saved case record contains its source status, media type, original body, raw MCP result, normalized observation, verdict, lost semantic paths, and invented claims.
- Oracle summary: 0 `PRESERVED`, 11 `LOSS`, 0 `INVENTED`, and 1 `NOT_APPLICABLE`.
- The post-observation regression verifier passed.
- The five baseline-definition files matched their pre-execution SHA-256 hashes after execution.

## 2. Source-code corroboration

The installed official wheel's `fastmcp/server/providers/openapi/components.py` had SHA-256 `725a8cda2935de4fab959f9ac2fbca75389650bbc01fefd4e03be30a43b9f086`.

Its success path parses JSON and returns `ToolResult(structured_content=structured_output)`. Its non-2xx path calls `response.raise_for_status()`, parses the error JSON, interpolates that object into an error-message string, and raises `ValueError`. This matches the runtime asymmetry: structured success versus prose-only problem detail.

## 3. Inference and interpretation

Under this profile's representation-neutral machine-addressability rule, the 11 in-scope RFC 9457 cases lose required semantics at the MCP result boundary. Their values remain visually present in diagnostic text, but recovery would require parsing Python-like prose from `content[].text`, which the oracle correctly does not treat as preservation.

No unsupported retryability, safe-to-retry, idempotency, custom problem-type, or RFC 9457 recognition claims were observed in machine-addressable carriers. Therefore the result is semantic loss without detected semantic invention.

## 4. Claims still not supported

This E4 result does not establish that all OpenAPI-to-MCP converters lose RFC 9457 semantics, that MCP cannot carry structured tool errors, or that `structuredContent` is the only valid carrier. It does not establish universal retry behavior for HTTP 429 or 503, and it does not test FastMCP versions other than 3.4.7.

## Harness note

One evidence-packaging defect was corrected after the first observation: each case row now copies in its existing source fixture and raw result. The change did not alter the corpus, expectations, oracle, adapter, OpenAPI definition, invocation path, raw serialization, or verdict logic. See `E4_HARNESS_CHANGES.md`.

## Required summary

```text
CLASSIFICATION: E4_CONFIRMED
TARGET: 3.4.7
BASELINE IMMUTABLE: YES
SAME-TOOL SUCCESS STRUCTURED: YES
SAME-TOOL PROBLEM MACHINE-ADDRESSABLE: NO
PRESERVED: 0
LOSS: 11
INVENTED: 0
NOT_APPLICABLE: 1
```
