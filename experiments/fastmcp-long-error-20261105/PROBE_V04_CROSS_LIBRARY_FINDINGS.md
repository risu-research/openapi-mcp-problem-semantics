# RISU Probe v0.4 — cross-library replay qualification (2026-11-05)

**Experimental branch record. No change to canonical main release.**

## Evidence provenance

This note records a **local offline run of the RISU Probe v0.4 code** on saved external results. It is **not** a claim that the v0.4 CLI was run by this GitHub Actions workflow. The v0.4 CLI source and full local tests are in the corresponding developer preview ZIP.

- **Fresh real integration capture:** GitHub Actions [audited FastMCP 4.1.6 run #7](https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42043089456), using SDK 2.3.0, actual MCP stdio client/server and synthetic localhost HTTP.
- **Frozen historical integration captures:** E5 CNOE codegen, E6 nihal1294/openapi-to-mcp, E7 hand-written SDK reference, in the canonical public release. These were normalized into [frozen-cross-library-matrix.json](frozen-cross-library-matrix.json) with both variants of P03/P09 preserved. This does not rerun those older generator versions.

## Offline v0.4 analysis

| Captured target | Pairs | PRESERVED | LOSS | Distinctive observation |
|---|---:|---:|---:|---|
| FastMCP 4.1.6 (fresh CI saved capture) | 8 | 1 | 7 | 5 explicit `TRUNCATED_UPSTREAM_ERROR` |
| SDK 2.3.0 hand-written control (same CI) | 8 | 8 | 0 | Typed Problem Details carriers retained |
| CNOE generator (historical) | 14 | 0 | 14 | 14 `ERROR_FLAG_LOST` |
| nihal1294/openapi-to-mcp (historical) | 14 | 0 | 14 | Original Problem bodies not retained in accepted machine carriers |
| E7 SDK hand-written reference (historical) | 14 | 13 | 1 | One `application/json` generic error outside old Problem-only profile |

The original frozen RFC 9457-only results were scoped differently: the non-Problem media-type control was excluded. Here **v0.4's wider JSON-error profile** also tests that control. No current-version bug is imputed to the frozen targets.

The v0.4 detection conditions are portable: an explicit text clipping marker **and** an aligned upstream JSON prefix are both needed for the truncation code. A 1,000-character constant is not built into detection. Missing source data in machine-readable carriers, loss of error flag, and proven clipping are different outputs.

## Claims not supported

No third-party production integrations, new upstream CNOE/nihal executions, source-provider adoption, or end-user injury have been measured. FastMCP's bounded error text is documented behavior, not an undisclosed flaw or proven protocol violation.

## Reproduction

Use the full RISU Probe v0.4 developer preview and run:

```bash
python risu_probe.py analyze fixtures/fastmcp_real_evidence.json --format json
python risu_probe.py analyze fixtures/frozen-cross-library-matrix.json --format sarif
```

The full saved matrices contain **synthetic** HTTP/MCP data and must not be confused with a fresh live measurement.
