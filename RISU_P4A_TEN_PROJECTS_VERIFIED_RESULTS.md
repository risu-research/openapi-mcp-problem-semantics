# RISU Probe P4-A: pre-registered ten-public-project blind qualification

**CI independently audited PASS**: https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42151297517

**Purpose:** Test the frozen RISU Probe v0.9.6's ability to make an honest offline *first diagnosis* against unfamiliar real-world public OpenAPI source files. This does not measure actual users, production servers, LLM behavior, or downstream consumer defects.

## Frozen protocol and evidence

The exact ten repositories, commit SHA-1s, official spec source paths, Git-blob SHA-1s, and file lengths were preregistered in [p4a/FROZEN_PREREGISTRATION.json](p4a/FROZEN_PREREGISTRATION.json) **before any spec analysis**. No target was substituted or removed. A CI fetcher retrieved each exact GitHub RAW source, checked the original Git-blob ID and byte length, then passed the original file name and native directory path to a **network-disabled, read-only, nonroot Docker runtime**. The runtime ran the *unmodified*, SHA-verified v0.9.6 first-check and scan. An independent read-only inventory parsed the full official OpenAPI documents without dereferencing remote links. A separate audit recomputed all provenance and denominators.

There were no vendor API calls, service probes, credential access, repository software execution, vulnerability scans, automated GitHub issues/PRs, or safety-filter bypasses.

## Main pre-registered results — intent to treat

| External project | Authenticated Git-blob source | Original folder-based v0.9.6 | GET declarations* | Error/default GET declarations* |
| --- | --- | --- | ---: | ---: |
| swagger-api/swagger-petstore | VERIFIED | NO_STATIC_FINDINGS (parsed) | 8 | 8 |
| meilisearch/specifications | VERIFIED | UNVERIFIED (not discovered by filename) | 27 | 23 |
| digitalocean/openapi | VERIFIED | UNVERIFIED (not discovered by filename) | 463 | 0 |
| stripe/openapi | VERIFIED | UNVERIFIED (over 512KiB) | 313 | 313 |
| github/rest-api-description | VERIFIED | UNVERIFIED (filename and over 512KiB) | 659 | 434 |
| twilio/twilio-oai | VERIFIED | UNVERIFIED (not discovered by filename) | 6 | 0 |
| openai/openai-openapi | VERIFIED | UNVERIFIED (over 512KiB) | 170 | 163 |
| ory/kratos | VERIFIED | UNVERIFIED (hidden directory not walked) | 25 | 23 |
| plaid/plaid-openapi | VERIFIED | UNVERIFIED (filename and over 512KiB) | 5 | 5 |
| go-gitea/gitea | VERIFIED | UNVERIFIED (over 512KiB) | 269 | 230 |

**Measured main outcome: 10/10 official source hashes verified, 1/10 automatically recognized, 9/10 UNVERIFIED.** The independent inventory identified 1,945 documented GET operations and 1,199 GET operations having explicitly declared error status or default responses. This counts **declarations in published specifications**, not actual observed failures, effective error-policy behavior, end-user contracts, or proven compatibility problems. Files that use external references, generic default response shapes or unsupported constructs can cause inventory undercounts. The original scanner made zero confirmed behavior claims.

Six files were not even selected by the existing discovery rules in their original directories; three were discovered but over the 512KiB cap. Five of the ten source files are intrinsically over 512KiB. The native filename and location were not renamed, and the 512KiB product limit was not raised to make benchmark scores better.

## Post-hoc usability diagnosis — NOT part of the primary score

A second, clearly labeled and **non-preregistered** arm passed the exact same file paths directly to the existing unchanged v0.9.6 scanner. This increased successful OpenAPI parsing to **5/10** (Petstore, Meilisearch, DigitalOcean, Twilio and Ory), with **five large files still UNVERIFIED**. This points to source discovery and bounded-file handling as causes. It cannot replace or retrospectively improve the 1/10 primary result.

The scanner legitimately uses exit code **2** for an \`UNVERIFIED\` analysis while still emitting valid JSON. During our first harness run, that return code was incorrectly recorded as \`INCOMPLETE_EXECUTION\`. We corrected the **measurement harness only**, not RISU itself, reran CI, and the independent audit confirmed all nine are explicitly classified \`STATIC_UNVERIFIED_OR_PARTIAL\`. The original ten targets and original 1/10 outcome did not change.

**Latency:** the sum of ten first-check subprocess times was about 3.32 seconds on the hosted runner *after* downloading and building the environment; the full fetch+build+analysis time and independent developer setup time are different measures. No 10-minute unaffiliated developer adoption claim is warranted.

## Independent relevance corroboration, not proof of RISU adoption

A public FastMCP issue (https://github.com/PrefectHQ/fastmcp/issues/1082) asked about passing an upstream HTTP 401/authentication error to an MCP client. Maintainer discussion noted that preserving HTTP status semantics requires special design. This externally confirms there are real integration questions in the field, but **does not confirm RISU found or fixes that report**.

## Stop/go decision

**PAUSE general product feature expansion and any claim of independent usability.** The pre-registered acceptance target was not met: only one of ten real public OpenAPI source files was handled successfully by the unmodified default first-check. There are **zero newly confirmed consumer contract defects in this round because no actual external consumer code was executed**; that metric is *unmeasured*, not a proof that the external projects are defect free.

A narrowly scoped future portability fix (recognize alternate common OpenAPI names and safely handle larger specifications within resource budgets) could improve first diagnosis, but merely raising scanner coverage would not establish developer demand or actual downstream consequences. After any such fix, report its 10-project result as a **new iteration** with a new pre-registered protocol; do not relabel this blinded trial. A developer-market push requires at least one genuinely independent code-consumer path/real-world integration mismatch and an independent replayable fix, not another ten manufactured mock errors.

The existing research, three-MCP implementations and two authentic SDK error-dispatcher examples remain useful controlled evidence; freezing product expansion does not mean deleting or discarding them.

## Reproduction

GitHub CI: https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42151297517

Run the linked workflow to reconstruct v0.9.6 exactly, fetch only pinned GitHub RAW sources, run all static checking in a Docker container with \`--network none\`, and produce \`P4A_10_PROJECT_RESULTS.json\` plus \`INDEPENDENT_P4A_AUDIT.json\`. Original full third-party raw specifications are **not** republished in the CI evidence artifact. Their exact official repository, commit, path and verified hashes suffice to retrieve them again.

No P4 independent-human benchmark was performed. No external software was installed or imported into the test runtime.
