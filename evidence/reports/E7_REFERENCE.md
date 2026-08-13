# E7 constructive reference control

## Classification

`E7_CONFIRMED`

The current official MCP client/server wire carried the fixed reference mapping with **11 PRESERVED, 0 LOSS, 0 INVENTED, and 1 NOT_APPLICABLE**. All required controls passed.

This confirms the narrow constructive claim: the current MCP tool-result protocol has sufficient carrier capacity for the RFC 9457 semantics in the frozen profile. It does not revise product-specific findings from earlier phases; it shows that those losses are not forced by MCP carrier capacity alone.

## Decisive result

| Check | Result |
|---|---:|
| Applicable cases preserved | 11 |
| Loss | 0 |
| Invented | 0 |
| Not applicable | 1 |
| Same S00 tool, success result machine-addressable | PASS |
| Same S00 tool, problem result machine-addressable | PASS |
| P11 body status 503 and observed status 502 both retained | PASS |
| P12 no retryability/safety/idempotence invention | PASS |
| P05 non-problem media-type gate | PASS |
| P01 text-only demotion detected as loss | PASS |
| Typed embedded problem resources preserved on official wire | PASS |

## Official current line

The run independently resolved and pinned:

- MCP specification revision `2026-07-28`;
- official TypeScript SDK v2 split-package stable line;
- `@modelcontextprotocol/client@2.0.0`;
- `@modelcontextprotocol/core@2.0.0`;
- `@modelcontextprotocol/server@2.0.0`.

Exact registry tarballs, integrity strings, registry shasums, and attestation URLs are in `OFFICIAL_SDK_REGISTRY_METADATA.json` and `bridge/package-lock.json`.

The official client negotiated `modern` and reported protocol version `2026-07-28`. The server was configured through `serveStdio` with legacy openings rejected, so this was not a silent fallback to the 2025 protocol path.

## Observed path

```text
frozen OpenAPI
  -> 15 operationId-identical MCP tool registrations
  -> 16 real fixture HTTP responses
  -> fixed reference mapping
  -> official MCP v2 server
  -> byte-captured stdio wire
  -> official MCP v2 client
  -> raw CallToolResult
  -> frozen carrier-neutral adapter v0.2
  -> frozen oracle v0.1
```

The 16 calls comprise 14 corpus responses, including both members of P03 and P09, plus both outcomes of the single S00 tool.

## What crossed the wire

The server-to-client transcript contains 16 tool results and 14 typed `EmbeddedResource` problem carriers: 13 corpus Problem Details responses plus the S00 problem response. Each used:

```text
content[].type = resource
content[].resource.mimeType = application/problem+json
content[].resource.text = compact, data-model-preserving problem JSON
result._meta.org.risu.reference.source_http = observed source HTTP facts
```

The official wire codec added its own namespaced server identity and modern `resultType: complete` field. It retained the reference mapping's resource MIME type, exact JSON text, `isError`, and namespaced source-HTTP metadata. The official client returned the expected raw `CallToolResult`; the verifier checks every client result against its wire result after removal of the wire-only `resultType` discriminator.

## Required controls

### Same-tool asymmetry control

The one registered tool `fixture_S00_asymmetry` produced:

- `outcome=success`: `structuredContent` equal to `{"ok":true,"probe":"same-tool"}`, a compatibility TextContent copy, and `isError=false`;
- `outcome=problem`: one typed embedded `application/problem+json` resource containing the full asymmetry-probe object and `isError=true`.

Both outcomes remained machine-addressable after the official client boundary.

### P11 split status

The embedded problem body retained `status=503`, while result metadata independently retained `observed_http_status=502`. The frozen oracle returned `PRESERVED` and verified the values were distinct.

### P12 semantic non-expansion

The result retained the problem type and observed 503 status. Neither the raw result nor normalized observation contained `retryable=true`, `safeToRetry=true`, `safe_to_retry=true`, `idempotent_retry`, or an equivalent bridge-created claim.

### Negative text demotion

P01's same JSON body was separately demoted to ordinary TextContent while source metadata was retained. Adapter v0.2 did not mine that text; oracle v0.1 returned `LOSS`. This demonstrates that the primary pass depends on the typed machine carrier rather than visible JSON-looking prose.

## Frozen-definition integrity

All seven frozen/contract files were hashed before implementation and after observation. Every digest is identical. See `e7-baseline-hashes.json`. The corpus, executable expectations, OpenAPI, oracle, adapter, mapping model, and mapping contract were not changed.

## Evidence layout

- `reference-e7-results.json`: case-level sources, raw results, normalized observations, verdicts, and controls.
- `E7_LAYER_BOUNDARY_EVIDENCE.json`: operation registry, real HTTP audits, bidirectional wire counts/hashes, and adapter/oracle boundary.
- `e7-client-to-server-wire.jsonl` and `e7-server-to-client-wire.jsonl`: untouched stdio messages.
- `e7-official-client-raw.json`: untouched official-client observations.
- `e7-bridge-stderr.jsonl`: bridge-side facts observed from all 16 actual fixture responses.
- `bridge/`: exact TypeScript source, compiled source executed, manifest, lockfile, dependency tree, and compiler configuration.
- `SHA256SUMS`: full evidence-package hash ledger.
- `verify_e7_reference.py`: dependency-free post-observation verifier.

## Verification

From this directory, with Python 3.8 or later:

```bash
python3 verify_e7_reference.py
```

The verifier uses only the Python standard library plus the frozen adapter/oracle files included beside it. It validates every case, both paired members, all wire/client projections, all required controls, all derived result files, and every entry in `SHA256SUMS`.

A full replay additionally requires Node 20 or later and installation of the exact lockfile dependencies:

```bash
cd bridge
npm ci
npm run build
E7_PYTHON=python3 node dist/reference-client.js
cd ..
python3 verify_e7_reference.py --write
```

The raw evidence in this package is already complete; dependency installation is not needed to audit or verify it.
