# RISU Probe P4-L — Third-Party Evidence Acquisition Gate

**Status:** Source qualification PASS, independently confirmed *upstream REST API → MCP* causal pair for both normal and error cases **NOT YET OBTAINED**.

## What was actually verified
Six original public files from five outside repositories were downloaded at immutable commits and validated against the original Git blob SHA-1. The P4-L reviewer executed entirely separately from RISU Probe's policy classifier; existing P4-J source and main branch were not modified.

| External source | Evidence | Admission |
|---|---|---|
| KraidleAI/Monark: `fixtures/h5-e2e-trace.json` and provenance | Real MCP `cascade` step 3 and separate HTTP mirror `POST /cascade` step 8 use exactly identical arguments and response objects in one recorded demonstration | **Tier 2:** two calls, semantic parity; no causal HTTP-as-upstream |
| KraidleAI/Monark: same file | Actual MCP `gate` error with `isError: true` and `task_class_retired` | **Tier 3:** no independently recorded upstream HTTP error for this call |
| Cisco's `mcptoolkit-mock` recording | Four tool-call requests and matching MCP result frames from a third-party recording | **Tier 3:** no original downstream REST API HTTP transaction |
| Tyk `tyk-mock-mcp-server` | Independently authored original handler test actually calls `httptest.NewServer` and verifies structured HTTP 200 output | **Tier 3:** no frozen on-wire MCP client plus upstream HTTP paired trace |
| meda-lang/meda | Independently recorded HTTP transport of MCP calls and proxy receipt events | **Tier 3:** MCP-over-HTTP is not an unrelated REST API upstream |
| BlitterStudio/amiberry-mcp-server | Third-party authored tests compare HTTP/MCP results for both normal and error codes | **Tier 3:** the results are mocked and the interfaces are tested in-process, not archived wire captures |

## Measurement
- **Source verification:** 6/6 original Git objects authenticated.
- **Independently recorded same-execution dual-interface normal parity:** 1 (Monark); not a causal converter example.
- **Independently recorded MCP error without paired HTTP error:** 1 (Monark).
- **Complete independently collected same-call HTTP API → MCP pairs:** normal **0**, error **0**.
- **Real-world false-positive rate:** undefined; independently adjudicated causal true negatives: 0.
- **Independent falsification attempts caught:** 9/9.

No HTTP 200 status was inferred from Monark's HTTP mirror; the output has a recorded object without an HTTP status field. No Monark MCP result was silently treated as REST upstream traffic.

## Reproduce
Requires Python 3.11+ and network **only to fetch original public, pinned files**:

```bash
python p4l/qualify_external.py --fetch
python p4l/qualify_external.py --qualify
python p4l/independent_audit.py
```

The CI artifact includes source/provenance pins and aggregate reports. Raw third-party payloads are not redistributed; the download/verification step retrieves them from the publishers' immutable Git revisions. No third-party software is executed.

## Remaining collection gate
An externally authored/published original recording must contain, for **each of a normal and an error response**, a genuine `tools/call` request and MCP result, **plus the resulting upstream REST API HTTP request and response** in the same execution with a non-guessable request correlation and sufficient independent provenance. Exact body/field data must be preserved or any redactions explicitly accounted for. A source snapshot without same-call correlation remains conditional even when hashes or contents match.

**Next priority:** find a genuinely published two-boundary recording from an independently run OpenAPI→MCP converter; reject stand-in HTTP mirrors, MCP-over-HTTP transport, manually joined HAR files, and testing harnesses with mocked bodies.
