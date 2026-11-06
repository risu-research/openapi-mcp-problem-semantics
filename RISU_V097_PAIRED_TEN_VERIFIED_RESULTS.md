# RISU Probe v0.9.7 — Verified paired 10-project OpenAPI compatibility repair

**Outcome:** Automatically recognized and parsed the original ten official public OpenAPI documents: **1/10 in v0.9.6 to 10/10 in v0.9.7**. No targets were replaced. The prior blind 1/10 score remains unchanged.

**CI:** https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42153289863 — **7/7 jobs PASS**. Six Ubuntu/Windows x Python 3.11, 3.12, 3.13 matrix jobs each passed 130 unittest methods (780 total unit-method executions). A separate no-network Docker job compared both source trees against the exact same 10 preregistered public Git blobs and passed an independent audit.

## Exactly what changed

- Additional filenames: candidates among JSON/YAML files with unusual names can be detected from at most **16 KiB** of their header, with full parsing required before declaring the file an OpenAPI specification.
- Include the known '.schema' documentation folder while still skipping unrelated hidden folders, symlinks, .git, virtual environments, node_modules and other excluded paths.
- OpenAPI descriptions only: 16 MiB per-file limit and 35 MiB cumulative accepted-file budget. The Python source scanner retains its earlier 512 KiB cap. Original 3,000-file, 24-directory-depth, and 500-finding limits remain.
- The product version is updated. No changes were made to evidence/decision rules, consumer witness implementations, source-to-MCP comparison algorithms, or fix-application logic.

The change is in ci/upgrade_v15_openapi_compat.py. Regression tests are in ci/test_v097_compat.py. The compiled installed package is the CI wheel risu_probe_preview-0.9.7.dev0-py3-none-any.whl.

## Ten unchanged public projects

| Project | v0.9.6 auto | v0.9.7 auto | Declared GET operations |
| --- | --- | --- | ---: |
| swagger-api/swagger-petstore | Yes | Yes | 8 |
| meilisearch/specifications | No | Yes | 27 |
| digitalocean/openapi | No | Yes | 463 |
| stripe/openapi | No | Yes | 313 |
| github/rest-api-description | No | Yes | 659 |
| twilio/twilio-oai | No | Yes | 6 |
| openai/openai-openapi | No | Yes | 170 |
| ory/kratos | No | Yes | 25 |
| plaid/plaid-openapi | No | Yes | 5 |
| go-gitea/gitea | No | Yes | 269 |

All ten v0.9.7 scans completed with exactly one OpenAPI file parsed per project and **zero incomplete files**. The original independent inventory and updated RISU both count **1,945 documented GET operations**. The independent inventory counts **1,199 GET operations with documented error/default responses**.

The combined ten scan subprocess durations on the hosted runner rose from 2.95 seconds in the original scanner to 7.80 seconds when all ten documents were genuinely parsed, including ~4.5 seconds for Plaid YAML. These durations exclude fetching, container build, installation and human onboarding; no independent developer first-use claim is warranted.

## Safety and strength of evidence

The only networking was to the preregistered official GitHub RAW source files. All file sizes, exact commit identifiers and Git-blob SHA1s were fixed before the original P4-A test and checked again. Both product versions ran in the SAME no-network, read-only, nonroot container with CPU/memory/time bounds. The target repositories' code was never imported or executed; no production API, authentication, MCP server, fuzzing or exploitation was attempted.

The paired trial is **post-hoc fix verification**, not a second blind independent qualification. Both versions reported zero Python-source-pattern findings; those zero results are NOT proof of API-to-MCP information preservation. The ten external descriptions were only parsed; no actual downstream consumers or production failures were observed.

**Decision:** The narrow usability compatibility repair met the predeclared 8/10 goal and passed regression tests, so v0.9.7 is a qualified experimental release candidate. Product demand remains unproven and P4 independent application adoption remains open. Avoid another broad feature expansion until an independently observed source-to-MCP consumer mismatch supports it.

## Evidence

- Freeze: p4a/FROZEN_PREREGISTRATION.json
- Exact target downloader: p4a/fetch_frozen.py
- Paired source-only test: p4b/paired_run.py
- Independent audit: p4b/independent_audit.py
- CI run: https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42153289863
- Original CI artifacts: risu-v097-compat-source-wheel; risu-v097-ten-unchanged-sources-paired-audit

Original main, previous v0.9.6, and P4-A baseline branches remain untouched.
