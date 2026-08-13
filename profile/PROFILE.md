# OpenAPI→MCP Problem-Semantics Preservation Profile v0.1.0-rc1

Status: Experimental release candidate; clean-room positive-control reproduction confirmed.  
Scope: Bounded translation fidelity for HTTP responses explicitly represented as RFC 9457 Problem Details.  
Normative keywords: MUST, MUST NOT, SHOULD, and MAY are used as profile requirements, not as claims about RFC 9457 or MCP themselves.

## 1. Purpose

This profile tests one narrow invariant:

> A translation MUST NOT silently lose machine-readable source semantics, and MUST NOT assert target semantics that are unsupported by the source.

The profile does **not** define a universal MCP error model. It does **not** require one specific MCP carrier. It does **not** claim that every RFC 9457 member must always be copied byte-for-byte.

## 2. Source scope

A source response is in scope only when the response representation is explicitly identified as `application/problem+json`.

Field-shape resemblance alone is insufficient. A JSON object containing keys such as `type`, `title`, or `detail` under another media type is not recognized as RFC 9457 by this profile.

For an in-scope response, the source semantic state consists of:

1. the RFC 9457 Problem Details data model carried in the body;
2. the effective problem type, including RFC 9457's `about:blank` default when `type` is absent;
3. occurrence identity carried by `instance` when present;
4. extension members, including unknown and nested members, with structure, values, order where semantically relevant, and cardinality preserved;
5. the observed source HTTP status associated with the representation; and
6. the distinction between an observed HTTP status and a `status` member carried inside the Problem Details body.

The profile treats human-readable `title` and `detail` as human-facing text. Their prose MUST NOT be mined to manufacture new machine claims unless the source provides a separate machine-readable basis for those claims.

## 3. Target machine-addressability

A source semantic is preserved only if a target consumer can deterministically recover it without natural-language interpretation or heuristic extraction from diagnostic prose.

A conforming target carrier MAY use any representation that satisfies that rule, including, for example:

- target-protocol structured content;
- target-protocol metadata;
- an explicitly typed embedded serialization; or
- another target-native structured carrier with an unambiguous machine contract.

Ordinary diagnostic text does not become machine-addressable merely because it contains JSON-looking text, a language-specific object representation, or enough prose for an LLM to reconstruct the source.

This definition is intentionally representation-neutral. The non-normative reference bridge in this repository uses a typed embedded `application/problem+json` resource plus namespaced source-HTTP metadata, but that mapping is only an existence proof.

## 4. Conservation requirements

For every in-scope source response exercised by the profile, a conforming translation MUST preserve every semantic assertion checked by the frozen conformance case.

In particular, the v0.1 corpus checks that a translator can preserve:

- explicit problem type identity;
- effective `about:blank` identity when `type` is absent;
- distinct problem types despite equal HTTP status;
- `instance` occurrence identity;
- scalar extension members;
- nested validation extensions and their cardinality;
- unknown future extension structures;
- stable machine identity despite localized human text;
- source `detail` without mining it into retry metadata;
- body `status` independently from observed HTTP status; and
- problem type plus observed status for a service-unavailable response.

## 5. Non-expansion requirements

A translation MUST NOT introduce a machine-readable claim that is not entailed by the source semantic state relevant to the case.

The executable v0.1 corpus specifically forbids:

- inventing a custom problem type when RFC 9457 yields effective `about:blank`;
- recognizing RFC 9457 solely from field shape under a non-problem media type;
- deriving retry timing from human prose; and
- asserting retryability, safe-to-retry, or idempotent-retry semantics in P12 without an accepted source basis.

The general non-expansion invariant is broader than the finite v0.1 executable `forbid` list. Passing v0.1 therefore establishes conformance only to the semantics exercised by this version of the corpus.

## 6. Verdicts

Each case receives one of four verdicts:

- `PRESERVED`: all required source semantics are machine-addressable and no forbidden target claim is introduced;
- `LOSS`: at least one required source semantic is not machine-addressable;
- `INVENTED`: no required source semantic is lost, but at least one forbidden target claim is introduced;
- `NOT_APPLICABLE`: the source is outside the profile's media-type gate.

An implementation conforms to v0.1 only if every in-scope case is `PRESERVED` and no forbidden invention is observed.

A future implementation could, in principle, both lose a source semantic and invent a target semantic. The current v0.1 case-level verdict vocabulary reports the primary executable classifications used by the frozen oracle; broader research discussion should keep loss and unsupported gain conceptually separate even where an implementation exhibits both phenomena outside the current carrier/forbid set.

## 7. Frozen v0.1 corpus

The normative executable corpus is `../conformance/cases.executable.json`, backed by `cases.json`, `openapi.json`, `oracle.py`, and `carrier_neutral_adapter_v02.py`.

The corpus contains 12 named cases: 11 in scope and one media-type-gated `NOT_APPLICABLE` case. Paired variants inside P03 and P09 and the S00 same-operation control cause more than 12 actual HTTP/tool invocations in some runs.

The frozen hashes are recorded in `../FROZEN_HASHES.sha256`.

## 8. What conformance does not mean

Conformance to v0.1 does not establish:

- complete RFC 9457 coverage;
- compatibility with every MCP SDK or protocol revision;
- a requirement to use EmbeddedResource;
- correctness of application-specific retry policy;
- correctness of `isError` signaling beyond what a case actually checks; or
- universal semantic fidelity for all OpenAPI→MCP translation.

Those are separate questions.
