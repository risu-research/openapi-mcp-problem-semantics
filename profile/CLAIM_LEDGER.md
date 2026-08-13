# Claim Ledger

This file separates direct observation, evidence-supported inference, and claims that remain out of scope.

## A. Directly supported observations

### A1. FastMCP 3.4.7

In the tested official-package path, the frozen profile produced 0 PRESERVED, 11 LOSS, 0 INVENTED, and 1 NOT_APPLICABLE. The same generated tool returned machine-addressable structured content on a 200 JSON success outcome, while the RFC 9457 problem outcome was exposed only through diagnostic text with no machine-addressable Problem Details carrier recognized by the profile.

### A2. CNOE openapi-mcp-codegen at commit d0d9e1d848c5705d9bfb1f58a82a7e653c9c85c2

In the tested lockfile-faithful generated-server path, the frozen profile produced 0 PRESERVED, 11 LOSS, 0 INVENTED, and 1 NOT_APPLICABLE. The generated API client retained non-2xx JSON internally under `details`; the generated tool returned a generic structured error and discarded those details before the MCP result boundary.

### A3. nihal1294/openapi-to-mcp at commit e5fbb3524384f7dd3367cec3b02b7982cddac614

In the tested generated-server path, the frozen profile produced 0 PRESERVED, 11 LOSS, 0 INVENTED, and 1 NOT_APPLICABLE. The target emitted richer structured error metadata, yet the source Problem Details object was not recoverable through the frozen profile's accepted machine carriers. A wire-visible non-standard top-level `meta.error.retryable=true` appeared in P12; it is recorded as an adjacent finding and is not counted as an oracle invention.

### A4. Constructive reference control

Across the tested official MCP 2026-07-28 TypeScript SDK v2 client/server stdio wire, the fixed reference mapping produced 11 PRESERVED, 0 LOSS, 0 INVENTED, and 1 NOT_APPLICABLE. The same frozen corpus, oracle, and adapter were used. A text-only demotion of P01 remained LOSS.

### A5. RC1 clean-room reproduction

A fresh-install reproduction of the constructive reference began without `node_modules` or compiled `dist`, used a new empty npm cache, materialized the exact lockfile dependency tree, rebuilt the TypeScript bridge, started fresh fixture/client/server processes, negotiated MCP `2026-07-28`, and reproduced 11 PRESERVED, 0 LOSS, 0 INVENTED, and 1 NOT_APPLICABLE. The text-only demotion control remained LOSS. The new stdio transcripts were byte-identical to E7 while the fresh observation timestamp differed.

## B. Evidence-supported comparative claims

### B1. Replicated semantic-loss class

The same bounded semantic-loss class was reproduced across three tested OpenAPI→MCP translation architectures, with different observed loss mechanisms.

This wording is preferred to “three completely independent MCP implementations.” The CNOE-generated server uses FastMCP as a runtime dependency, although the observed CNOE loss occurs in generated translation code before the runtime boundary.

### B2. Structured target errors are not sufficient

The nihal1294 target demonstrates that a translator can emit structured target-side error metadata while still failing to preserve the source Problem Details semantics exercised by this profile.

### B3. Tested MCP carrier capacity does not force the observed loss

Because the constructive reference carried all 11 in-scope cases across an actual official MCP client/server wire, the losses observed in the three tested translators are not explained by an inability of that tested MCP data model/SDK path to carry the exercised semantics.

Preferred wording:

> For the frozen profile tested here, semantic loss is not forced by the tested MCP carrier capacity.

### B4. Positive-control reproducibility

The constructive preservation result is not limited to one previously materialized dependency tree: it reproduced after a fresh exact-lock install and rebuild. This strengthens reproducibility of the existence proof; it does not increase the number of independently sampled translators or establish ecosystem prevalence.

## C. Claims that are NOT supported

Do not claim that:

- all OpenAPI→MCP converters lose RFC 9457 semantics;
- the three tested translators are statistically representative of the ecosystem;
- MCP cannot carry structured errors;
- EmbeddedResource is the only conforming representation;
- the 12-case corpus covers RFC 9457 completely;
- every `retryable=true` mapping is semantically invalid;
- top-level non-standard `meta` is equivalent to MCP `_meta`;
- the profile is already an accepted MCP, IETF, or industry standard; or
- the experiments prove downstream user harm or agent misbehavior without a separate behavioral study; or
- one clean-room reproduction establishes cross-platform or multi-laboratory reproducibility.

## D. Publication rule

When a sentence moves from A → B, label the reasoning as an inference and cite the supporting experiments. Never silently upgrade B into a universal C-level ecosystem claim.
