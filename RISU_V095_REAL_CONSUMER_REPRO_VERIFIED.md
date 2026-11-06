# RISU Probe v0.9.5 — Real consumer contracts to minimal, verified fixes

**Qualification: PASS, 8/8 GitHub Actions jobs.** [Verified run #42145033818](https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42145033818) on commit 199cbcc913e4fb3281dd4219cc8de4a57c5d39b0. All original research and v0.9.1–v0.9.4 experiment branches were left unchanged.

## What is new

The v0.9.5 experimental package adds three stdlib modules:

- risu_repair.py: fail-closed, consumer-side promotion of the first complete JSON text response into structuredContent, but only for a well-formed numeric status_code plus object/array data envelope. The current isError flag and explicit metadata must agree; it refuses to overwrite existing structuredContent.
- risu_minimize.py: bounded recursive dictionary-key/array-item deletion with oracle checks and a final pass verifying one-deletion minimality. This is NOT a global shortest-input claim.
- risu_reproduce.py: a safe, opt-in, offline command generating a minimized synthetic pair, an evidence report, and replay guidance. It states MODEL_ONLY_NOT_LIVE_REPLAY until a real server has been separately executed.

## Unmodified actual application source contracts

Two exact Git commits, file Git blob hashes, and actual SDK error dispatcher functions were checked and executed inside an isolated CI container.

1. **PyGithub**, commit 5aeb43916b197a0fe8016600817b868fc894af5a, github/Requester.py blob 397a58f5d44f62a49fb44cdae9273721a3f69354. Requester.createException(404, headers, body) picks UnknownObjectException when body.message contains Not Found. [Exact original source](https://github.com/PyGithub/PyGithub/blob/5aeb43916b197a0fe8016600817b868fc894af5a/github/Requester.py).
2. **stripe-python**, commit d97a68e28ec6553c3545fdf7e5322e871559cfdb, stripe/_api_requestor.py blob 6224c5e6d357043ff7a404cebefbbdef09ec9b7f. The actual _APIRequestor.handle_error_response code classifies an HTTP 400 with JSON error.code rate_limit as RateLimitError, even for legacy v1 calls. [Exact original source](https://github.com/stripe/stripe-python/blob/d97a68e28ec6553c3545fdf7e5322e871559cfdb/stripe/_api_requestor.py).

The test harness uses one synthetic read-only GET for each error envelope because the pinned MCPGen implementation executes only GET tools under the selected safe policy. These are **synthetic local stand-ins for the SDK error response format**, not observations of real GitHub or Stripe service requests. The authentic unchanged SDK exception dispatchers are the consumers.

## Actual observed before and after

| Genuine SDK contract | Native HTTP-style payload | MCP structured-only bridge | Tested patched bridge | Original JSON | Minimal replayed JSON |
| --- | --- | --- | --- | ---: | ---: |
| PyGithub HTTP 404 | UnknownObjectException | GithubException | UnknownObjectException | 142 bytes | 23 bytes |
| Stripe v1 HTTP 400 | RateLimitError | APIError | RateLimitError | 196 bytes | 31 bytes |

Exact 1-minimal source payloads:
- PyGithub: {"message":"Not Found"}
- Stripe: {"error":{"code":"rate_limit"}}

All four statuses/classifications were measured by calling **the actual pinned application SDK code**. The tests also called an actual MCPGen-generated MCP server against a synthetic loopback HTTP server, once before and once after minimizing each response. Exactly **4 real tool-initiated localhost GET requests** were observed and zero unexpected calls.

Intermediate minimization uses a model of the JSON response envelope observed during the first real MCP call. The **final minimized JSON was independently served again through real generated MCPGen**, and the authentic SDK outcomes were retested. We claim only local 1-minimality relative to recursive key/list-element deletion operations.

The generated patch **consumer_bridge.patch** changes the sample consumer bridge from looking only in structuredContent to carefully promoting the known MCPGen status_code/data text envelope first. CI applied the patch to a disposable file, checked it matched the tested corrected version, then invoked the unchanged PyGithub and Stripe SDKs through that bridge. Separate Docker commands independently replayed the saved minimal fixtures before and after the patch. The patch **does not** modify any vendor's source or claim a universal interoperability fix.

## Reproduction

Checkout the experimental branch, rebuild the exact RISU source via the following verified chain:

    python ci/export_v09_source_portable.py
    python ci/upgrade_v10_modules.py
    python ci/upgrade_v11_semantics.py
    python ci/upgrade_v12_decision_witness.py
    python ci/upgrade_v13_repro.py

Build the wheel from dist/risu_v09_source, then try the safe offline CLI on a synthetic saved source/MCP pair:

    risu-probe reproduce saved_pair.json --path /error/code \
      --out local-repro --allow-synthetic-export

The optional export flag is required because this command writes raw response values to a local directory; do not point it at real credentials or confidential workloads.

For actual SDK source and MCP replay evidence, run the [v0.9.5 GitHub workflow](https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42145033818). It builds the two real pinned SDKs and MCPGen into a Docker image, runs with --network none and nonroot read-only permissions, generates the artifacts in results/repro_package, replays failures before and repairs after, and performs an independent fail-closed audit. The two external SDK file Git blob hashes must match their pins or the build stops.

## Complete qualification and limits

- **6/6 Windows and Ubuntu Python 3.11/3.12/3.13 portable jobs**, each with 93 individual tests, **558 total**. The deterministic unit suites contain an additional 180 seeded repair/minimizer adversarial cases; those are loops within tests, not additional separately counted unittest methods.
- **3 previous real converter implementations** (CNOE, FastMCP, MCPGen) requalified on 12 synthetic GET cases, 36 expected HTTP requests, 12 rejected mutated-source counterfactuals, 0 unexpected requests. Old consumer result: 2 PASS / 3 FAIL / 7 REVIEW under calibrated decision policy and 2/12 structured-only versus 6/12 JSON-text readers. Independent audit PASS; image build plus run 129 seconds on the verified runner.
- **2 authentic SDK contracts**, both broken under a specified structured-only bridge and both repaired under the pinned-MCPGen-text adapter. 2 real minimized source replay calls, 4 expected GET requests, independent audit PASS; separate SDK image build, both replays, patch test and audit 45 seconds on the verified runner.
- Product is still an experimental preview; this does not prove vendor defects or actual user/LLM failures, and it does not establish unknown developer adoption, broader API coverage, or real production compatibility.

Artifacts on verified run: risu-v095-policy-witness-wheel, risu-v095-three-project-witness-evidence, and risu-v095-actual-sdk-minimal-repros. The latter contains sample bridge, exact executable unified diff, source-minimal saved MCP fixtures, app source pins, and replay script.
