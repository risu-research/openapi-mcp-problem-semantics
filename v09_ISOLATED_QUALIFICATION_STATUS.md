# RISU Probe v0.9 — isolated real CNOE qualification

This experimental branch is a **staging area**, not an executed qualification. The downloadable v0.9 harness is the source of truth until all source-authenticated files have been committed here and the manual GitHub Actions run passes.

## Target
Execute the original RISU Probe **v0.8 modules extracted byte-for-byte from the v0.8 wheel** (wheel SHA-256 `e9ebe383ff6453951150ad4050f401d3e207ac9d8a1df88dcbde1d05149c6b71`) against an MCP server generated from **CNOE openapi-mcp-codegen commit `8c2b065497cf32ecbb7cf7e28dad3a99c6706c3f`**. No simulation of the product verifier is acceptable.

## Execution isolation
Build dependencies in Docker image without project secrets. Execute inside `docker run --network none --read-only --user 65534:65534 --cap-drop ALL --security-opt no-new-privileges`, with bounded resources and only loopback fixture HTTP. The independent evidence audit must confirm a successful positive control, actual MCP calls, exactly four captured cases, three error losses, source and result hashes, and no unknown fixture requests.

## Status
- **Locally verified:** extracted original product modules SHA-256; v0.8 fixture preflight on CNOE's previously generated actual source; exact product modules on a local stdlib MCP test double (3 cases, 2 errors lost).
- **Not yet verified:** new Docker no-network run against freshly generated CNOE server. Do not cite the local test double as external qualification.
- **Blocked transfer:** The linked GitHub app can create UTF-8 repository files but does not accept the existing binary wheel or its container path as a file upload. The full runnable project archive contains the precise v0.8 product module source bundle, SHA ledger, Dockerfile, experiment runner, and audit. Upload the archive contents to this branch before triggering CI. Never invent a green status.

Use the full project archive accompanying this handoff; its `README.md` has the exact Docker and GitHub Actions instructions.
