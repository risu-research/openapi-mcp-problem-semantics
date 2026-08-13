# RC1 promotion report

**Candidate:** `v0.1.0-rc1`  
**Scientific promotion status:** APPROVED  
**Public push status:** HELD for human-controlled license/authorship/repository/privacy decisions

## Promotion basis

- E4 FastMCP: 0 PRESERVED / 11 LOSS / 0 INVENTED / 1 N/A.
- E5 CNOE: 0 / 11 / 0 / 1.
- E6 openapi-to-mcp: 0 / 11 / 0 / 1.
- E7 constructive reference: 11 / 0 / 0 / 1 across official MCP 2026-07-28 stdio.
- RC1 clean-room reproduction: 11 / 0 / 0 / 1 after fresh exact-lock dependency materialization, rebuild, and fresh processes.
- Frozen semantic core remains byte-identical.
- Text-only demotion negative control remains LOSS.

## Hygiene corrections applied

1. Separate-process stdio verification is evidence-derived from clean-room provenance plus preserved TypeScript source (`StdioClientTransport` → wire tee child → bridge stdio server); it is no longer accepted merely because a verifier constant says `True`.
2. Ledger terminology is explicit: the historical E7 internal ledger has 39 files, while the RC1 `SHA256SUMS` ledger has 36 entries.
3. Raw historical archives are indexed by exact SHA-256 rather than embedded in the public-source ZIP. This avoids silently repackaging historical evidence and isolates machine-local path metadata from the main public snapshot.
4. The public-source verifier checks for local user paths and obvious live-secret prefixes in textual release files.
5. The release manifest covers every file in the public source snapshot except the manifest itself and verifies each hash.

## Strongest supported claim

> For the frozen profile tested here, semantic loss is not forced by the tested MCP carrier capacity.

The clean-room reproduction strengthens reproducibility of the constructive existence proof. It does not turn three tested translators into an ecosystem prevalence estimate.
