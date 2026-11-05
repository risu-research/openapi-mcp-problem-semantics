# RISU auto mapping and fresh CNOE execution — 2026-11-05

This is experimental evidence, outside the frozen `main` RFC 9457 release.

## Executed (not simulated)

- Cloned CNOE `openapi-mcp-codegen` fresh from commit `8c2b065497cf32ecbb7cf7e28dad3a99c6706c3f`.
- Generated a Python MCP stdio server from a synthetic localhost OpenAPI GET operation `get_order`.
- Examined the **actual** tool catalog's input schema (required string `path_id`) and four explicitly authored parameter examples: normal, conflict, validation, generic.
- Constructed a read-only plan. Confirmed **0** synthetic upstream HTTP requests during planning.
- Sent each planned tool name and exact argument object into the freshly generated server using an official MCP SDK 2.3.0 client isolated from the CNOE generator's native dependencies.
- Confirmed exactly **1** mediated upstream GET per MCP call, plus two independent source comparison GETs, for each case.
- Independent fail-closed audit verified source/MCP payload digests, planned argument identity, response statuses, generated source hashes, and all four data pairs.

## Result

| Input | Upstream HTTP | Observed MCP | Semantic-preservation check |
|---|---:|---|---|
| normal | 200 | `isError=false` | PRESERVED |
| conflict | 409 | `isError=false` | LOSS |
| validation | 422 | `isError=false` | LOSS |
| generic | 400 | `isError=false` | LOSS |

Evidence: [public audited CI run #12](https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42064216658). The run artifact contains the OpenAPI input, generator config, freshly generated server sources, full dependency freeze, HTTP/MCP response matrix, and SHA-256 inventory.

## Scope and important distinctions

This CI invokes an **independent example-to-schema matching harness** in the CNOE experimental branch. The separately packaged RISU Probe **v0.6 product module** underwent local live HTTP+MCP end-to-end tests and independently mapped the saved actual CNOE tool schema to four inline examples. These are complementary validation paths; we do not claim the exact v0.6 Python module was uploaded to and executed by this CNOE CI run.

CNOE is a generated-code producer, not the MCP SDK. FastMCP 3.4.0 was installed as a **dependency of CNOE's generated server**; the client used official SDK 2.3.0. The result is a bounded synthetic test of behavior under this precise configuration. No current production use, MCP standard violation, secret access, real user harm, or generic tool safety proof is claimed.

MCP readOnly annotations alone are not sufficient to authorize invocations. Only explicit GET examples were called; real deployments require reviewing destination, command, credentials and possible GET side effects.
