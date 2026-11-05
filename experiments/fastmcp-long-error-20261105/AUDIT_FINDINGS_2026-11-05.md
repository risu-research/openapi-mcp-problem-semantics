# Adversarial audit of the FastMCP 4.1.6 1000-character error boundary

**2026-11-05 · Experimental branch only.** This supplements, and does not alter, the archived RFC 9457 research artifact or the default `main` branch.

## What is actually proved

With actual FastMCP 4.1.6 OpenAPI tools and official MCP SDK 2.3.0 client/server processes communicating via stdio 2026-07-28, synthetic localhost JSON error bodies are rendered into diagnostic text. Under the fixed configuration, FastMCP truncates the Python-character serialization after 1000 characters with a marker. The threshold was reproduced at 999/1000/1001 characters and with 1600/5000-character, Unicode, and nested-validation samples.

In one 3174-character synthetic error containing 40 JSON Pointers, 12 complete pointers (indices 0–11) are visible in text, 28 complete pointers (12–39) are missing, and the next entry starts as an incomplete fragment. These counts describe **this fixed synthetic fixture**, not the percentage lost in real applications.

An explicitly hand-written SDK 2 preservation control retained all error bodies and the observed HTTP status. It is not an automatic SDK OpenAPI converter.

## Important limits and correction

**This is known, documented FastMCP behavior, not evidence of an undisclosed bug or MCP protocol violation.** The FastMCP release documentation explicitly describes bounding OpenAPI upstream errors. The tested source applies a 1000-*Python-character* limit; this is not exactly a 1024-byte cutoff for Unicode strings.

The evidence records official SDK-decoded `CallToolResult` objects reserialized as JSON, **not raw stdio JSON-RPC bytes**. No production API, authenticated endpoint, LLM behavior, user impact, or newer FastMCP prerelease was tested. This is a tool-conversion, safety-policy and consumer-data-loss observation, not a security vulnerability claim.

## Additional adversarial verification

- The original run's green status was insufficient: it checked the positive control without independently enforcing every loss boundary. The CI workflow now runs a separate **fail-closed evidence auditor** after the E2E experiment.
- The auditor checks original HTTP and MCP sample hashes, source media/status, 1000-character prefix, Unicode character/byte counts, complete pointer count, and preserved SDK control. Three deliberate mutations (original body, rehashed MCP result, rehashed SDK control) must be detected.
- An additional **real MCP stdio** policy test confirms that default `application/json` errors are also truncated, HTML error bodies are omitted, and `mask_error_details=True` suppresses upstream error details.
- RISU Probe v0.3 was independently given all 16 saved target/case results: FastMCP 7 LOSS + 1 PRESERVED, SDK control 8 PRESERVED. The current Probe does not yet provide a first-class truncation root-cause code.
- Full dependency snapshot is included in the GitHub Actions artifact; package pins alone are not a fully hash-pinned environment.

## Recorded audited run

- [CI run #6 (audited and policy-tested)](https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42042402732)
- Run commit: `447cd7f3194e9f1320adf155c5eeeaa5f582a03e`
- Artifact: `risu-fastmcp-long-error-evidence` (contains `evidence.json`, `AUDIT.json`, `POLICY.json`, `ENVIRONMENT.txt`, `SUMMARY.md`)
- Artifact SHA-256 reported by GitHub: `0cc838b2bc02d871d751cbb50b76329d5af5588bc573b3d0fa9543d9b8ce631b`
- All audit checks and deliberate mutation controls passed.
- GitHub artifact retention is finite; archive a copy if long-term reproducibility matters.

## Research and product implications

It is inaccurate to market this as discovery of an unknown FastMCP defect. It **does** demonstrate a measurable, machine-relevant loss under a known output policy. Any optional structured preservation proposal needs explicit enablement, authorization boundaries, PII redaction and bounded size. An upstream maintainer discussion should be framed as a usability tradeoff and possible enhancement.

The next RISU Probe feature should identify `TRUNCATED_UPSTREAM_ERROR` separately from `UNSTRUCTURED_ERROR`, link to a minimal reproducible example, and distinguish source-provided, documented behavior from unintended regressions.

Original FastMCP source: https://github.com/PrefectHQ/fastmcp/blob/v4.1.6/fastmcp_slim/fastmcp/server/providers/openapi/components.py

Official integration docs: https://gofastmcp.com/integrations/openapi

Protocol tools spec: https://modelcontextprotocol.io/specification/2026-07-28/server/tools
