# RISU — FastMCP 4.1.6 long-error boundary experiment

**Experimental branch only.** The canonical v0.1.0-rc1 research release, its fixed cases, and `main` are unchanged.

This test uses official Python MCP SDK 2.3.0 to call an **unmodified FastMCP 4.1.6 OpenAPI server** and a separately hand-written SDK-preserving control server. Both servers request the same synthetic localhost HTTP responses. There are no third-party services, secrets, or write operations.

## Why this experiment
The pinned FastMCP 4.1.6 source contains `_ERROR_BODY_LIMIT=1000` in `fastmcp_slim/fastmcp/server/providers/openapi/components.py` and `OpenAPITool.run()` calls `_raise_for_status(response)` before the structured-success path.

Source: https://github.com/PrefectHQ/fastmcp/blob/v4.1.6/fastmcp_slim/fastmcp/server/providers/openapi/components.py

Test cases: 999, 1000, 1001, 1600 and 5000 JSON characters; nested 40-entry validation errors; Unicode; success control. A distinct tail marker lets us test whether the last field actually reaches the MCP client.

## Run
```bash
python -m pip install -r experiments/fastmcp-long-error-20261105/requirements.txt
python experiments/fastmcp-long-error-20261105/experiment.py
```

Run via [branch-specific GitHub Actions](https://github.com/risu-research/openapi-mcp-problem-semantics/actions/workflows/risu-fastmcp-long-error.yml). Download `risu-fastmcp-long-error-evidence` from the run to inspect `evidence.json` and `SUMMARY.md`.

## Interpret carefully
An error represented only as prose is a **machine-structure loss** under the RISU profile, even when a person can read the JSON. An explicit `… (truncated)` marker and absent late canary are **wire-level loss of literal bytes/characters**. A hand-written SDK2 positive control demonstrates that a typed embedded Problem Details resource can retain the data; it is *not* an automatic SDK OpenAPI conversion.

No claim of a security vulnerability, MCP conformance violation, or population-wide prevalence is made. FastMCP's limit may be deliberate for bounded error messages. This is exploratory vendor-independent evidence intended for maintainer discussion.