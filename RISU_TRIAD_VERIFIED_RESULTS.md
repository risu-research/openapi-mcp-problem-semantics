# RISU Probe v0.9.1 — THREE independent generator first-diagnosis qualification

**Final result: PASS, 2026-11-05.** [Successful GitHub Actions run #42132745017](https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42132745017). Independent audit: **PASS**. Earlier unsuccessful runs were kept visible as engineering evidence (Ruff cache, FastMCP `httpx` vs `httpx2`, audit-script syntax), not treated as product findings.

## The result, including setup

- **173 seconds** total for Docker image build (including fresh external dependency installation), three actual generated-server experiments, and evidence generation, measured between `results/begin_unix.txt` and `results/end_unix.txt` in the successful hosted runner.
- Target-specific time after dependencies ready: **CNOE 9.442 s**, **FastMCP 4.147 s**, **MCPGen 3.464 s**. These are not whole-machine installation times.
- **12 HTTP/MCP comparison cases** (four per project), **36 counted localhost GET requests**, **0 unexpected source requests**, and **four preserved independent positive controls**.
- v0.9.1 product engine hash (`risu_probe.py`) **9cdc63bb1f1b832260bf6459dabb1c7f47995cf95aa96a5eac88bf327818e5b4**, byte-identical to the earlier qualified v0.9.1 product source.
- First-run evidence artifact: [risu-v092-three-real-project-qualification](https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42132745017/artifacts/13463852845).
- Independent audit's reported summary SHA-256: **8e03d43e4d373849faf8895fc738727dbcac1de33ebf18fed702cd7cf224ba7f**.

## Actual observations

| External implementation | Original HTTP 200 | 400 / 409 / 422 | Strict RISU result |
|---|---|---|---|
| CNOE generated server, `8c2b065497cf32ecbb7cf7e28dad3a99c6706c3f` | PRESERVED | LOSS, LOSS, LOSS | Error flag lost and JSON error structure unavailable |
| FastMCP 4.1.6 `from_openapi` | PRESERVED | LOSS, LOSS, LOSS | Structured errors unavailable as original machine-readable objects |
| MCPGen `30ee7cb9c2e923ce901e788b0d911f6547772866` in explicit `safe-execute` GET mode | LOSS | LOSS, LOSS, LOSS | Textual carrier, no equivalent structured payload |

The independent RISU-maintained reference carrier preserved all four statuses. It is a **positive control** for the checker, not a statement about automatic behavior of the official MCP SDK.

**Interpretation:** `LOSS` measures strict upstream-to-MCP machine-readable carrier preservation under a selected diagnostic profile. An upstream JSON body included in an MCP text message may remain understandable or parseable by downstream software. Do not misstate those observations as literal disappearance of every value, a protocol violation, or a newly discovered upstream defect. FastMCP's error-size policy and MCPGen's server design must be considered when proposing changes.

## Reproduction boundary

- Each pinned generator was actually installed and executed; the resulting MCP server actually called the synthetic local API.
- Runtime Docker container used `--network none`, read-only filesystem, non-root user, no added capabilities or privileges, CPU/memory/PID bounds, no user credentials and only synthetic GET requests.
- Inputs were an explicitly constructed OpenAPI 3.1 fixture with status 200, 400, 409 and 422; no production service was exercised.
- Third-party source commits and direct versions are pinned. Transitive PyPI package hashes are **not fully pinned**; a fully offline immutable dependency archive is future hardening work.
- The 173-second number was observed on one qualifying hosted GitHub Linux runner, not established as a guarantee on other computers.
- This qualifies the prepared three-project first-diagnosis *challenge*. It is **not yet** evidence of unaffiliated developers diagnosing arbitrary real-world projects in under ten minutes, and it does not establish ecosystem-wide incidence.

## Next user-value milestone

Run the same differential workflow against independently maintained *real* application OpenAPI specs, with owners' consent, no credentials in public CI, consented/synthetic non-sensitive inputs, clear decision-usefulness judgments, and independent reproductions. The success criterion is a concrete actionable finding an unrelated developer can reproduce without RISU-specific knowledge. Prefer developer adoption and lower false positives to expanding the number of generic scan rules.

See [reproduction instructions](./RISU_TRIAD_QUICKSTART.md). The original research `main` and frozen releases remain unchanged.
