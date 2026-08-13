# Forensic Audit — RC1 Clean-Room Reproduction

## Verdict

**RC1_CLEANROOM_CONFIRMED — APPROVED**

The uploaded RC1 evidence bundle was independently re-audited against its raw files rather than relying on the Codex summary.

## Independently verified

- ZIP SHA-256 matches the reported digest:
  `60f866d886136481abed9698aa3ac24bddda9c036b37ba84527e063b6b318b33`
- The public draft available in the working environment independently hashes to:
  `6cb3947ab8bff220f37b6f81707bc979d56f7cd63788ef0c94f2d1e90e7ac3f7`
- The prior E7 bundle independently hashes to:
  `7a6c5a047f66cad20e4ca14b44af30e272646cf7dce72a61401aa24372651f92`
- RC1 SHA256SUMS verification passes for all 36 files listed in the RC1 ledger.
- The frozen corpus, executable expectations, OpenAPI source, oracle, carrier-neutral adapter, mapping model, and reference mapping contract retain identical before/after SHA-256 digests.
- The bundled dependency-free verifier was independently executed and returned:
  - PRESERVED: 11
  - LOSS: 0
  - INVENTED: 0
  - NOT_APPLICABLE: 1
  - NEGATIVE_TEXT_DEMOTION: PASS
- The RC1 client→server and server→client stdio transcripts are byte-identical to the prior E7 transcripts.
- The fresh raw client observation differs from E7 only in `generated_at_utc`.
- The fresh observation timestamp differs from E7:
  - E7: `2026-08-12T16:49:21.223Z`
  - RC1: `2026-08-12T17:27:32.153Z`
- The fresh dependency record states:
  - `node_modules` absent before install
  - `dist` absent before build
  - empty npm cache
  - `npm ci` exit 0
  - 17 packages freshly materialized
  - unchanged exact `package-lock.json`
- Source inspection confirms the client uses `StdioClientTransport`, which spawns the wire tee; the wire tee in turn spawns the bridge process. The fixture is separately spawned as a Python process.

## Strongest interpretation

RC1 reproduces the constructive positive control from a fresh dependency materialization and rebuild while leaving the semantic contract unchanged.

Together with E4–E7, the supported bounded claim is:

> For the frozen profile tested here, the semantic losses observed in the three tested OpenAPI→MCP translation architectures are not forced by the tested MCP carrier capacity. A minimal reference translation preserves all 11 in-scope cases across the official MCP 2026-07-28 stdio protocol boundary.

This remains a bounded claim. It does **not** establish industry-wide prevalence, full RFC 9457 coverage, or a unique required target representation.

## Two publication-hygiene nits to fix before RC1 release

1. `verify_rc1_cleanroom.py` currently sets `official_client_and_server_separate_processes_stdio` to `True` rather than deriving that control from captured process provenance. The source code independently supports the claim, so this does not affect the RC1 result, but a release verifier should make the control evidence-derived rather than hard-coded.

2. Distinguish ledger counts precisely:
   - the prior E7 internal ledger contains 39 files;
   - the RC1 `SHA256SUMS` ledger independently verified here contains 36 files.
   Public wording should not ambiguously call the RC1 ledger “39-file.”

## Promotion recommendation

**Promote the research artifact to `v0.1.0-rc1` after fixing the two non-substantive hygiene nits above.**

Do not add a fourth converter before publication. The highest-value next work is release hardening, public timestamping, and external review.
