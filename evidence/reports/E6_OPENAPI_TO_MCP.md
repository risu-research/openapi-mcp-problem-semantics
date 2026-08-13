# E6 results — nihal1294/openapi-to-mcp

## Classification

**E6_LOSS_ONLY**

Current unmodified target runtime reproduces meaningful RFC 9457 source-semantic loss, but no existing corpus case produces `INVENTED` under the frozen adapter/oracle. The runtime does put `retryable: true` on P12's raw wire result, but under top-level `meta` rather than accepted protocol `_meta`; this is reported as an adjacent finding and does not override the frozen oracle.

Counts are case-level: preserved **0**, loss **11**, invented **0**, not applicable **1**.

## Method and target

Official GitHub metadata was reverified before sealing the run. The active unarchived repository remained on `master` at `e5fbb3524384f7dd3367cec3b02b7982cddac614` (commit time `2026-07-31T16:42:34Z`), matching the handoff-preparation HEAD. Latest release and project version were `v0.9.0`; no material version split existed.

The target was cloned cleanly, installed with Python 3.14.7 from its committed `uv.lock`, and used to generate a strict 15-tool TypeScript stdio MCP server from the frozen `openapi.json`. The generated server was installed according to its documented npm workflow. Because the generator emitted no Node lockfile, npm resolved its declared ranges once; that `package-lock.json` was then used with `npm ci` for the recorded build/run.

Execution path:

```text
official source @ exact HEAD → actual generator → frozen OpenAPI
→ generated TypeScript server → transparent local observer → frozen fixture
→ generated Axios runtime → stdio MCP server → raw MCP tools/call
→ exact wire + SDK CallToolResult → frozen adapter → frozen oracle
```

No target or generated source was patched.

## 1. Raw observation

Every error call returned `isError: true`, ordinary TextContent, no `structuredContent`, and a top-level `meta` object. The exact P12 wire shape was:

```json
{
  "content": [{"type": "text", "text": "API server error (503): Request failed with status code 503"}],
  "isError": true,
  "meta": {
    "requestId": "…",
    "error": {"code": "api_server_error", "source": "upstream", "retryable": true, "httpStatus": 503}
  }
}
```

There was no wire `_meta`. The SDK-side saved model includes `_meta: null` as a parsed default plus the extra `meta`; `e6-mcp-wire.jsonl` is the exact serialization authority.

The same generated S00 tool showed an asymmetric representation:

- 200 JSON success: `structuredContent={"ok":true,"probe":"same-tool"}`; machine-addressable **yes**.
- 403 Problem Details: diagnostic TextContent plus top-level `meta`; complete RFC 9457 object machine-addressable through an accepted carrier **no**.

All raw case records include source status/media/body, tool name, arguments, CallToolResult, normalized observation, verdict, losses, and inventions in `nihal-e6-results.json`.

## 2. Layer-localization evidence

The transparent observer correlated every response with the generated runtime's `X-Request-Id`. Across **14 RFC 9457 calls** (corpus plus S00 problem):

- `UPSTREAM_PRESENT`: **14/14** — exact status, media type, and full body observed at the boundary delivered to Axios.
- `INTERNAL_OR_AUDIT_PRESENT`: **14/14** at the transient Axios layer — generated source receives the object as `AxiosError.response.data` before reducing it.
- Full body in emitted failure-audit event: **0/14** — resilience converts the AxiosError first, so the later audit sees only `ToolExecutionError`.
- `MCP_VISIBLE_PRESENT` through an adapter-accepted carrier: **0/14**.

Thus the evidence supports “received, transiently represented, then reduced,” not “destroyed everywhere” and not “preserved by MCP.” Per-call correlations and audit events are in `E6_LAYER_BOUNDARY_EVIDENCE.json`.

## 3. Frozen-oracle interpretation

| Case | Verdict | Losses | Inventions |
|---|---|---|---|
| P01-explicit-type | LOSS | problem_type:https://example.test/problems/out-of-credit | — |
| P02-default-about-blank | LOSS | effective_problem_type:about:blank | — |
| P03-same-status-different-type | LOSS | pair_distinct_problem_types | — |
| P04-instance | LOSS | instance:/problems/occurrences/abc-123 | — |
| P05-media-type-gate | NOT_APPLICABLE | — | — |
| P06-scalar-extension | LOSS | extension:code | — |
| P07-nested-validation-extension | LOSS | extension:errors | — |
| P08-unknown-future-extension | LOSS | extension:remediation | — |
| P09-localized-human-text | LOSS | pair_same_problem_type | — |
| P10-no-prose-mining | LOSS | problem_type:https://example.test/problems/quota-exceeded; detail | — |
| P11-origin-status-survives-intermediary | LOSS | body_status:503; observed_status:502; distinct_origin_and_observed_status | — |
| P12-no-retryability-invention | LOSS | problem_type:https://example.test/problems/service-unavailable; observed_status:503 | — |

The adapter did not mine diagnostic prose. It found no complete source Problem object in `structuredContent`, `_meta`, or an embedded typed resource. P05 remained not applicable because its source media type was `application/json`.

P12 lost both required problem type and observed status. Its top-level `meta.error.retryable=true` was present on the wire, but top-level `meta` is not one of the frozen adapter's accepted carriers. Consequently `claims={}`, the P12 verdict is `LOSS`, and the primary invented count is zero.

## 4. Adjacent findings not used for the primary verdict

1. **Wire-visible retryability outside the frozen carrier set.** P12 has `result.meta.error.retryable=true`, derived from status 503, even though the source carries no retry guarantee. This is behaviorally notable, but the frozen oracle does not classify it as invention because the field is not protocol `_meta`.
2. **Generated metadata uses `meta`, not `_meta`.** The current JavaScript SDK's loose result schema lets the extra field traverse stdio, but it is not the protocol metadata field named by the adapter/profile.
3. **Failure audit drops the body despite a body-capable helper.** The source contains an AxiosError branch that could retain response data; the actual resilience ordering converts the error before that branch executes. Recorded error-audit events therefore omit body and media type. Success audit does retain both.
4. Custom codes such as `api_server_error` were not counted as inventions because no frozen `forbid` rule covers them.

## Controls and integrity

- Preservation/adapter control: PASS.
- Supplied `_meta.error.retryable=true` invention-visibility control: PASS and independently returns `INVENTED` for the synthetic P12 observation.
- TextContent-only no-prose-mining control: PASS and remains `LOSS`.
- Post-observation replay through untouched adapter/oracle: PASS.
- All five immutable files match `IMMUTABLE_BASELINE.sha256` after execution.
- Target checkout remained clean.

## Reproduce the saved-observation verification

From the evidence directory, with any standard Python 3 interpreter:

```bash
python verify_e6_saved_results.py
```

This verifier checks baseline hashes, exact SDK-to-wire correspondence, upstream source correspondence, stored adapter observations, stored oracle verdicts, S00, P12 carrier location, and totals. It requires no downloaded packages.

## Final console summary

```text
CLASSIFICATION: E6_LOSS_ONLY
TARGET_REPO: nihal1294/openapi-to-mcp
TARGET_COMMIT: e5fbb3524384f7dd3367cec3b02b7982cddac614
BASELINE_IMMUTABLE: YES
SAME-TOOL SUCCESS MACHINE-ADDRESSABLE: YES
SAME-TOOL PROBLEM RFC9457 MACHINE-ADDRESSABLE: NO
UPSTREAM PROBLEM BODY OBSERVED: YES
MCP-VISIBLE RETRYABLE TRUE ON P12: YES
PRESERVED: 0
LOSS: 11
INVENTED: 0
NOT_APPLICABLE: 1
```
