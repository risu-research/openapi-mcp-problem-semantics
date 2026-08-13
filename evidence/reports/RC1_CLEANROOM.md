# RC1 clean-room reproduction gate

## Classification

`RC1_CLEANROOM_CONFIRMED`

The public draft independently reproduced the frozen E7 constructive reference control from a fresh dependency installation, fresh source compilation, fresh fixture/server/client processes, and newly captured official MCP stdio bytes.

The artifact is **eligible for promotion**. Creating a repository tag, release, or publication remains a separate human-controlled action.

## Result

| Required check | Clean-room result |
|---|---:|
| Preserved | 11 |
| Loss | 0 |
| Invented | 0 |
| Not applicable | 1 |
| S00 success machine-addressable | PASS |
| S00 problem machine-addressable | PASS |
| P05 excluded from RFC 9457 recognition by media type | PASS |
| P11 body `status=503` retained apart from observed HTTP `502` | PASS |
| P12 contains no bridge-created retryability claim | PASS |
| P01 ordinary-TextContent demotion detected as `LOSS` | PASS |
| Typed `application/problem+json` resources survived the fresh wire | PASS |
| Official client result matched each newly captured wire result | PASS |
| Frozen definition remained unchanged | PASS |

## Input and publication gates

The supplied public draft SHA-256 is:

```text
6cb3947ab8bff220f37b6f81707bc979d56f7cd63788ef0c94f2d1e90e7ac3f7
```

It exactly matches the expected digest. `verify_publication.py` passed both before and after the reproduction. The embedded E7 source bundle also matched the draft's recorded digest `7a6c5a047f66cad20e4ca14b44af30e272646cf7dce72a61401aa24372651f92`, and its 39-file internal ledger passed before any source was copied.

All seven frozen/contract digests were identical before and after:

- corpus and executable expectations;
- source OpenAPI;
- frozen oracle v0.1;
- frozen carrier-neutral adapter v0.2;
- reference mapping model;
- fixed E7 reference mapping contract.

## Clean-room boundary

The primary replay work directory was a sibling of, not a directory inside, the extracted public artifact. Only source inputs were copied. It began without:

- `node_modules`;
- compiled `dist` output;
- previous raw client observations or wire logs;
- a reused fixture or MCP process.

An npm 11.19.0 CLI ran `npm ci` against the unchanged E7 `package-lock.json`, using a newly created empty target cache. It freshly added 17 packages. The lockfile digest remained `47add159bd41427166f373240941e750d93148e3e0a8acc222a3f0f9828c4b9a`; exact installed versions, tarball integrity strings, and installed package hashes are recorded in `RC1_INSTALLED_DEPENDENCIES.json`.

TypeScript 5.9.3 then compiled the copied source while `dist` was absent. The new compiled artifact hashes reproduced E7, but no prior compiled files were used.

## Fresh official-wire observation

New processes produced the observation timestamp `2026-08-12T17:27:32.153Z`. The official client explicitly pinned MCP `2026-07-28`; it observed the `modern` era and negotiated `2026-07-28`. The official server rejected legacy openings.

The fresh capture contains:

- 15 operationId-identical registered tools;
- 16 real fixture responses;
- 16 official client `tools/call` requests;
- 16 official server tool results;
- 14 typed embedded `application/problem+json` resources, covering 13 corpus Problem Details responses plus the S00 problem response.

For every tool result, the verifier removes only the modern wire-only `resultType: complete` discriminator and checks exact equality with the raw `CallToolResult` observed by the official client. All 16 match.

## Frozen adapter/oracle replay

The dependency-free verifier feeds only the new raw client observations through the public draft's frozen adapter and oracle. It does not mine ordinary text. This yields 11 preserved, 0 loss, 0 invented, and 1 not applicable.

The separate P01 negative control demotes the same problem JSON to ordinary TextContent while retaining source metadata. Adapter v0.2 does not recover a problem object from it, and oracle v0.1 returns `LOSS` as required.

## Reproduction comparison

The fresh and E7 observation timestamps differ. After removing only the generated timestamp, the raw client documents are equal; both newly captured stdio transcripts are byte-identical to E7. Because the new run started without installed dependencies, compiled output, or raw observations and launched new processes, this equality is evidence of deterministic reproduction rather than artifact reuse.

## Evidence map

- `rc1-cleanroom-results.json`: case-level fresh sources, raw results, normalized observations, verdicts, and controls.
- `rc1-client-raw.json`: untouched fresh official-client observation.
- `rc1-client-to-server-wire.jsonl` and `rc1-server-to-client-wire.jsonl`: new bidirectional stdio captures.
- `rc1-bridge-stderr.jsonl`: all 16 actual HTTP facts observed by the fresh bridge.
- `RC1_FROZEN_HASHES.json`: before/after frozen digest ledger.
- `RC1_INSTALLED_DEPENDENCIES.json`: clean-install conditions and exact installed package evidence.
- `RC1_CLEANROOM_PROVENANCE.json`: end-to-end source, build, runtime, process, and comparison provenance.
- `bridge/`: copied source, exact package lock, and freshly compiled output; no installed tree.
- `verify_rc1_cleanroom.py`: standard-library-only verifier.
- `SHA256SUMS`: complete evidence-directory ledger.

## Verification

From this directory:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 verify_rc1_cleanroom.py
```

No package installation is required to audit the saved observations. A complete live replay requires Node 20 or later, a fresh `npm ci` from `bridge/package-lock.json`, and permission to bind the loopback fixture port.

## Console summary

```text
CLASSIFICATION: RC1_CLEANROOM_CONFIRMED
PUBLIC_DRAFT_SHA256: 6cb3947ab8bff220f37b6f81707bc979d56f7cd63788ef0c94f2d1e90e7ac3f7
BASELINE_IMMUTABLE: YES
FRESH_DEPENDENCY_TREE: YES
PROTOCOL: 2026-07-28 (modern)
PRESERVED: 11
LOSS: 0
INVENTED: 0
NOT_APPLICABLE: 1
NEGATIVE_TEXT_DEMOTION: PASS
```
