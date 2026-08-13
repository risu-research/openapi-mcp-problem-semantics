# Preserving Problem Semantics Across OpenAPI→MCP Translation

## Subtitle

A bounded RFC 9457 conformance profile, three empirical translator studies, and a constructive MCP reference control

## Abstract

Machine-readable API errors can lose semantic structure when translated into tool protocols even when both the source and target can represent structured data. This work introduces a bounded conformance profile for preserving RFC 9457 Problem Details semantics across OpenAPI→MCP translation. The profile operationalizes two invariants: no silent loss of source semantics and no unsupported gain of target semantics. A frozen 12-case corpus exercises problem-type identity, the `about:blank` default, occurrence identifiers, scalar and nested extensions, unknown future extensions, localization, media-type gating, prose non-inference, and the distinction between body status and observed HTTP status. We evaluate three OpenAPI→MCP translation architectures using real generated or provider paths and raw MCP results. All three lose every in-scope semantic case under the profile (0 preserved, 11 loss, 1 not applicable), through different observed mechanisms. We then implement a non-normative reference bridge and carry the same corpus through an official MCP 2026-07-28 TypeScript client/server stdio boundary, preserving all 11 in-scope cases with no detected invention. A fresh-install clean-room reproduction rematerializes the exact dependency tree, rebuilds the bridge, starts fresh processes, and reproduces the same 11/0/0/1 result. The result is narrow: it neither establishes ecosystem-wide prevalence nor mandates a particular MCP representation. It does show that, for the semantics exercised here, the observed losses are not forced by the tested MCP carrier capacity. The artifacts include the frozen corpus, oracle, target observations, raw evidence bundles, and constructive reference mapping.

## 1. Research question

When an HTTP API explicitly exposes RFC 9457 Problem Details as machine-readable error semantics, does an OpenAPI→MCP translation preserve that meaning at the protocol-visible target boundary?

A second, falsifying question follows:

If tested translators lose the semantics, is the loss forced by MCP's available carrier capacity, or is a preserving translation executable on the same protocol family?

## 2. Contribution

This paper makes four bounded contributions.

1. A representation-neutral preservation profile for a specific translation boundary.
2. A frozen 12-case executable corpus and oracle.
3. Empirical observations from three tested OpenAPI→MCP translation architectures with independently localized loss mechanisms.
4. A constructive reference control showing preservation across an official MCP 2026-07-28 TypeScript v2 client/server wire, followed by a fresh-install clean-room reproduction of that positive control.

The paper does **not** claim an industry-wide defect rate or a universal MCP error ontology.

## 3. Semantic model

Define a translation `T` from a source response semantic state `S` into target result `R`.

The profile tests two constraints:

**Conservation.** Every source semantic exercised by the case remains deterministically recoverable from a machine-addressable target representation.

**Non-expansion.** The target does not assert a forbidden machine semantic unsupported by the source state exercised by the case.

The profile deliberately separates semantic preservation from surface representation. Exact bytes are not required. Deterministic machine recoverability is.

## 4. Corpus design

Describe P01–P12 and explain why each case corresponds to a semantic boundary rather than corpus volume.

Emphasize:

- media type, not object shape, gates RFC 9457 recognition;
- problem `type` is machine identity while localized human text is not;
- extension members remain open-ended;
- diagnostic prose is not a substitute for machine-addressable semantics;
- observed HTTP status and body `status` can be distinct facts; and
- the corpus includes non-expansion controls as well as conservation controls.

## 5. Method

For each target:

1. pin the current tested source/package revision;
2. preserve the frozen corpus, OpenAPI, adapter, and oracle hashes;
3. execute real source HTTP fixtures;
4. capture the raw MCP-visible result at the lowest practical client boundary;
5. normalize only recognized machine carriers;
6. run the frozen oracle; and
7. preserve provenance and raw evidence.

The constructive reference uses the same corpus and oracle. It is not allowed to redefine success.

## 6. Results

### 6.1 FastMCP 3.4.7

Headline: 0 preserved / 11 loss / 0 invented / 1 N/A.

Mechanism: success JSON remains structured; non-2xx Problem JSON is parsed and then represented only in diagnostic error text at the tested result boundary.

### 6.2 CNOE openapi-mcp-codegen

Headline: 0 / 11 / 0 / 1.

Mechanism: generated API client retains non-2xx JSON under `details`; generated tool discards `details` and returns a generic structured error.

Important limitation: the generated server uses FastMCP as a runtime dependency. Phrase this as a distinct translation architecture with a separately localized pre-runtime loss site, not as a completely independent MCP runtime implementation.

### 6.3 nihal1294/openapi-to-mcp

Headline: 0 / 11 / 0 / 1.

Mechanism: structured target error metadata is produced, demonstrating that target-side error structure alone is not semantic preservation of the source Problem object.

Record the P12 wire-visible non-standard `meta.error.retryable=true` only as an adjacent observation. Do not promote it into the primary frozen-oracle invention count.

### 6.4 Constructive reference

Headline: 11 preserved / 0 loss / 0 invented / 1 N/A.

The fixed reference uses a typed embedded `application/problem+json` resource for the body and namespaced `_meta` for observed source HTTP facts. It survives an official MCP 2026-07-28 TypeScript v2 client/server stdio wire.

The text-only demotion negative control remains LOSS.

### 6.5 RC1 clean-room reproduction

The positive control was repeated from a fresh dependency materialization using the exact lockfile, a new empty npm cache, a fresh TypeScript build, and fresh fixture/client/server processes. It again produced 11 preserved / 0 loss / 0 invented / 1 N/A. The fresh observation timestamp differed from E7, while the two captured stdio transcripts were byte-identical and the raw client document matched after removing only the generated timestamp. This is a reproducibility check on the constructive existence proof, not an additional translator sample.

## 7. Main interpretation

The strongest supported interpretation is not “MCP errors are broken.” It is:

> Structured target errors are not sufficient for source semantic preservation, and the losses observed in the tested translators are not forced by the tested MCP carrier capacity.

This reframes the problem from error formatting to translation fidelity.

## 8. Threats to validity

### External validity

Only three translator architectures were tested. They are not a statistically representative sample.

### Construct validity

The corpus exercises a bounded subset of RFC 9457 semantics. It is intentionally small and boundary-oriented.

### Carrier definition

Machine-addressability is operationalized by a frozen adapter. The adapter was broadened before later targets to accept typed embedded problem resources, preventing a `structuredContent`-only bias. Future MCP carriers may require a new profile version rather than retroactive mutation.

### Runtime independence

CNOE uses FastMCP at runtime. Its evidentiary value comes from the independently localized loss in generated translation code, not from claiming a wholly independent MCP runtime stack.

### Positive-control design

The reference bridge is authored to preserve semantics and therefore cannot estimate ecosystem prevalence. Its role is only to falsify the hypothesis that the tested semantics are impossible to carry over the tested MCP wire.

### Reproduction scope

The clean-room positive-control reproduction was performed on one recorded OS/architecture/runtime stack. It strengthens deterministic reproducibility of the tested wire path but is not a multi-platform or independent-laboratory replication.

### Temporal validity

Implementations and MCP SDKs can change. Every target claim must remain version/commit scoped.

## 9. Implications

For translator authors: preserve source semantic objects before collapsing them into target diagnostic abstractions.

For protocol/tooling reviewers: evaluate translation fidelity separately from whether the target has “structured errors.”

For conformance tooling: maintain source witnesses, target observations, and explicit anti-inference rules so that both loss and unsupported gain remain testable.

## 10. Conclusion

A translation can preserve syntax-like structure yet lose source semantics, or generate structured target errors that omit the source's machine identity and extensions. The bounded experiments here show that three tested OpenAPI→MCP translation architectures lose the semantics exercised by the profile, while a minimal reference bridge preserves the same semantics across an official MCP client/server wire. The resulting claim is deliberately narrow but falsifiable: preservation is executable, and the observed loss is a translation-design outcome rather than a demonstrated necessity of the tested MCP carrier capacity.
