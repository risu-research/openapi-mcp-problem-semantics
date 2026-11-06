# RISU Probe v0.9.3 — evidence-calibrated diagnostics

**Final CI: PASS, 7/7 jobs, 2026-11-05 (US Eastern).** [GitHub Actions run #42136640819](https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42136640819). Independent three-project audit: **PASS**. The original research main and v0.9.1/v0.9.2 branches have not been modified.

## What changed, and why

The old \`LOSS\` verdict answers a strict question: is the upstream JSON still available as the original machine-readable result? That question is useful, but *not* equivalent to whether original values survived somewhere in the MCP response.

The new parallel \`evidence_v1\` answers a narrower, verifiable content-recovery question. This keeps the old verdict for compatibility, while independently classifying:

- \`EXACT_MACHINE\`: same entire JSON object found in a typed/structured carrier, with named carrier type.
- \`EXACT_JSON_TEXT\`: full original JSON object safely parsed from an eligible text representation, including a unique whitelisted \`/data\` envelope. The result remains a text carrier, **not** a structured MCP output.
- \`PROVEN_TRUNCATED_PREVIEW\`: a provable upstream prefix aligns with an explicit clipping marker. This certifies the observed preview was clipped; it is not an ecosystem-wide data-destruction claim.
- \`UNVERIFIED_TEXT\` and \`NO_EXACT_CARRIER_OBSERVED\`: exact recovery was **not established**, which does not prove deletion.
- \`NOT_ASSESSED\` and \`DEFERRED\`: consumer-scope/non-JSON/incomplete or other nonqualifying observations.

The \`error_flag\` and \`http_status\` channels are independent: a full body can survive while \`isError\` disappears, or the status can survive only as a parseable text field. A report contains metadata, approved wrapper names, and counts, never raw body values.

Strict checks reject bool/number equivalence, mismatched values, duplicate JSON keys, NaN, overlarge/deep JSON, accidental JSON snippets inside free prose, and multiple ambiguous matching envelopes. Added 24 deterministic unit tests, including **150 seeded value-mutation pairs**, and preserved nine existing process/CLI reliability regressions. The qualification ran on Windows and Ubuntu, each with Python 3.11, 3.12, and 3.13.

## Independently executed real-code result

| Project & pinned implementation | HTTP 200 | HTTP 400 / 409 / 422 | Distinguishing status |
|---|---|---|---|
| CNOE openapi-mcp-codegen \`8c2b065497cf32ecbb7cf7e28dad3a99c6706c3f\` | \`EXACT_MACHINE\` | three \`UNVERIFIED_TEXT\` | Three observed \`ERROR_FLAG_LOST\` |
| FastMCP \`4.1.6\` | \`EXACT_MACHINE\` | three \`UNVERIFIED_TEXT\` | Error flags preserved |
| MCPGen \`30ee7cb9c2e923ce901e788b0d911f6547772866\` | \`EXACT_JSON_TEXT\` | three \`EXACT_JSON_TEXT\` | All four upstream bodies exactly recoverable under text \`/data\`; status codes recoverable from the text JSON envelope |

The strict, backward-compatible legacy report had marked **10 of 12** as \`LOSS\`. The calibrated report has **2 exact machine, 4 exact text-JSON, 6 unverified text**. In particular, the four MCPGen cases refute treating all legacy machine-carrier failures as disappearance of the original body. This is the central false-positive reduction.

Independent controls: 12 live GET comparisons, **12 rejected mutated-source counterfactuals**, four positive reference cases, 36 expected localhost HTTP GETs, zero unexpected API requests. The checked source \`risu_probe.py\` SHA-256 is \`29ecd65dac04df8de678ef9bd72e798a3ddff281704a77a295fa8d853c764956\`.

**Latest end-to-end CI build+three-project diagnostic interval: 128 seconds** on the qualified hosted Ubuntu runner; per-project actual probes ran after dependencies were installed. This is one measured controlled setup, not a guaranteed first-run time for all users.

Artifacts available on [final run #42136640819](https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42136640819):
- \`risu-v093-evidence-calibrated-wheel\`, installable \`risu_probe_preview-0.9.3.dev0-py3-none-any.whl\`.
- \`risu-v093-three-project-calibrated-evidence\`, redacted per-case observations and independent audit.

## Repeat safely

Run \`ci/export_v09_source_portable.py\`, then \`ci/upgrade_v10_modules.py\`, then \`ci/upgrade_v11_semantics.py\`; build and install the resulting wheel. Read \`triad/Dockerfile\`, \`triad/run_three.py\`, and \`.github/workflows/risu-v093-evidence-calibrated.yml\` for the independent server proof. All runtime project comparisons run on loopback, inside a nonroot, read-only, no-external-network container with only synthetic GETs, no production credentials.

\`risu-probe first-check . --json\` is an offline static first check, not a real preservation certification. \`risu-probe analyze MATRIX.json --profile json-errors --format json\` computes the new \`evidence_v1\` on previously collected actual response pairs without new HTTP calls.

**Boundaries:** This experiment covers three upstream projects, one synthetic read-only API, and four HTTP statuses each. It does not measure ecosystem prevalence, agent task success, protocol compliance, malicious servers, or unaffiliated developer onboarding on an arbitrary fourth repository.
