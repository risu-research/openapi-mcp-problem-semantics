# OpenAPI→MCP Problem-Semantics Preservation Profile

[![DOI](https://zenodo.org/badge/1332313466.svg)](https://doi.org/10.5281/zenodo.21911146)

**Version:** v0.1.0-rc1  
**Status:** Experimental release candidate; bounded, review-oriented research artifact  
**Promotion gate:** Core experiments frozen; clean-room positive-control reproduction confirmed

## Thesis

Machine-readable error structure at the target is not, by itself, proof that source error semantics survived translation.

This release candidate tests a narrow invariant for OpenAPI→MCP translation of RFC 9457 Problem Details:

> **No silent loss + no unsupported gain.**

A source semantic must remain deterministically machine-recoverable at the target boundary, and the translation must not manufacture unsupported machine claims.

## What is here

- `profile/PROFILE.md` — normative experimental profile;
- `conformance/` — frozen 12-case corpus, OpenAPI, oracle, and carrier-neutral adapter;
- `evidence/` — result snapshots, reports, RC1 provenance, and hashes for five immutable raw evidence assets;
- `reference/` — non-normative constructive preserving mapping;
- `paper/` — review-ready argument skeleton and abstract;
- `review/` — reviewer attack surface, RC1 forensic audit, and external-review next move;
- `release/` — RC1 promotion notes and publication gate;
- `verify_release.py` — dependency-free release verifier.

## Headline evidence

| Target / control | Preserved | Loss | Invented | N/A |
|---|---:|---:|---:|---:|
| FastMCP 3.4.7 | 0 | 11 | 0 | 1 |
| CNOE openapi-mcp-codegen | 0 | 11 | 0 | 1 |
| nihal1294/openapi-to-mcp | 0 | 11 | 0 | 1 |
| Constructive reference over official MCP 2026-07-28 wire | 11 | 0 | 0 | 1 |
| RC1 fresh-install reproduction of constructive reference | 11 | 0 | 0 | 1 |

The strongest supported comparative claim is:

> **For the frozen profile tested here, semantic loss is not forced by the tested MCP carrier capacity.**

The artifact does **not** establish ecosystem-wide prevalence, complete RFC 9457 coverage, or a unique required MCP representation.

## Why RC1 matters

E7 showed that a preserving translation survives an official MCP 2026-07-28 TypeScript client/server stdio wire. RC1 repeated that positive control from a fresh dependency materialization, rebuild, and fresh processes while keeping the semantic contract unchanged. The fresh run again produced 11 PRESERVED, 0 LOSS, 0 INVENTED, and 1 NOT_APPLICABLE, with the text-only demotion control still classified as LOSS.

The RC1 source snapshot does not modify the historical E7 or RC1 evidence archives. Release verification derives the separate-process stdio topology from the preserved TypeScript source plus recorded clean-room provenance rather than trusting a hard-coded boolean.

## Verify this release candidate

```bash
python3 verify_release.py
```

This uses only the Python standard library. It checks the frozen semantic core, result summaries, RC1 clean-room provenance, evidence-derived process topology, RC1 internal ledger count, and the public-source manifest.

## Citation and license

Canonical repository: `https://github.com/risu-research/openapi-mcp-problem-semantics`

Concept DOI (all versions): [`10.5281/zenodo.21911146`](https://doi.org/10.5281/zenodo.21911146)

Version DOI (`v0.1.0-rc1`): [`10.5281/zenodo.21911147`](https://doi.org/10.5281/zenodo.21911147)

Citation metadata is provided in `CITATION.cff`. This repository is released under the Apache License 2.0.

## Publication discipline

Read `profile/CLAIM_LEDGER.md` and `release/PUBLICATION_GATE.md` before reusing conclusions. This is a release candidate, not an accepted MCP/IETF/industry standard. The archived `v0.1.0-rc1` release and its DOI are fixed historical records; later commits to `main` do not alter that archive. Website publication, maintainer outreach, subsequent versioning, and preprint submission remain deliberate human-controlled actions.