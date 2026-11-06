# RISU Probe P4-I — Independent Public Capture Field Trial

**Date:** 2026-11-06. **Baseline:** unchanged installed RISU Probe `0.9.9.dev0`. **Purpose:** measure honest input rejection, successful analysis, and false-alarm risk on **third-party-authored files**. This is **not** a third-party causal end-to-end HTTP-to-MCP evaluation.

## Frozen cohort (actual independently published bytes)

`FROZEN_COHORT.json` pins **10 public files from 7 unrelated repositories** by commit and original Git blob SHA-1. Five files are HAR (of which three are Playwright browser captures) and five are MCP-related JSONL (third-party protocol fixtures, transcripts, and one harness-command file). The distinction between a third-party authored **fixture** and a recorded interaction is retained in the manifest.

- HAR: `aaronhg/har-tap`, `suislanchez/HARvest` (five total files).
- MCP: `samirsawarkar/uniview`, `TekesApps/TekesKernel`, `3zz77/mcpdrift`, `penk/qmlagent`, `meoyawn/kitesurf` (five total files).

The test downloads **immutable public originals** and checks the exact Git blob SHA-1. The product is installed from the original SHA-pinned v0.9.9 build chain; its source is not patched for this study. Download is performed by the CI runner before the offline analyzer invocation. No live API requests, model queries, or user-code execution are made during diagnosis.

## Measured results

| Trial arm | Denominator | Rejected (exit 2) | Analyzed successfully |
|---|---:|---:|---:|
| Original third-party raw files, no conversion | 10 | **10** | **0** |
| Cross-source HAR/MCP folders lacking the required mapping | 25 | **25** | **0** |
| **Total incomplete or one-sided input** | **35** | **35** | **0** |

For the 35 unsupported inputs, rejection was correct and no fake correspondence was inferred. These are **not 35 complete end-to-end tests** and do not demonstrate sensitivity.

**Special adversarial counterexample:** intentionally splice a real HTTP 200 JSON HAR entry from HARvest's Open-Meteo recording with the independently authored `echo` MCP fixture in TekesKernel. Put a knowingly **false** correspondence in a newly authored `pairs.json`. The unchanged product accepted the pair (exit 0) and reported `LOSS: 1`. The sources are provably unrelated. This is a **causal-provenance false-alarm risk** when a developer-supplied mapping is trusted, **not** a discovered defect in FastMCP, Open-Meteo, the MCP SDK, or the public API.

**Real-world false-positive rate: UNMEASURABLE.** The cohort contains **zero** independent, causally attested HTTP→MCP pairs with ground-truthed negative cases. Numerator and denominator for a normal FPR are unknown; `0%` would be deceptive. The one intentionally fabricated mapping is kept in a separate adversarial metric.

Original CI completed: [P4-I field trial run 42229975175](https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42229975175). It restored and installed the pinned v0.9.9 wheel, passed the P4-H native-format regressions (22 tests), validated ten Git blob identities, performed 35 refusal checks and a false-mapping probe, and passed an independent offline audit with **9/9 corrupt-result mutations detected**.

The archived CI artifact contains **only hashes, source identities, aggregate outcomes and an auditor**. Raw third-party HAR and MCP bytes, request URLs, headers, cookies and body texts were not republished in the artifact.

## Reproduce

Use Python 3.11+ and a clean virtual environment; build/install the P4-H v0.9.9 wheel using the pinned workflow or install the identical wheel from the earlier P4-H master.

```bash
python p4i/field_trial.py --fetch --output p4i/results
python p4i/field_trial.py --evaluate --output p4i/results
python p4i/audit_offline.py \
  p4i/FROZEN_COHORT.json \
  p4i/results/field_trial.json \
  p4i/results/offline_reaudit.json
```

Fetch needs access to public pinned GitHub files. **Analysis is offline.** Do not upload or share raw captures from user environments; they may contain secrets.

## P4-J remediation gate to test before promoting this product

1. Add a provenance dimension to every comparison: `CAUSALLY_ATTESTED`, `DEVELOPER_DECLARED_ONLY` or `UNPAIRED`. An input-file hash **does not** attest causality.
2. A mismatch in `DEVELOPER_DECLARED_ONLY` may be a **conditional mismatch for inspection**, but cannot be labeled a *confirmed converter defect*. Avoid a blocking error-level exit solely on that mismatch without stronger evidence.
3. To graduate to `CAUSALLY_ATTESTED`, demand an independently captured correlation witness or joint recording that links **the same** HTTP request/response and MCP tool call. An unsupported user assertion alone is insufficient.
4. Preserve known P4-D/P4-E/P4-H experiments, all 22 native tests and 84 historical regressions. Keep a negative-control forged pair and at least one genuine paired positive/negative source to validate the provenance gate.
5. **Never imply a measured FPR** while the denominator of independently ground-truthed cases is zero.

This project is still a research-stage developer preview. The study provides evidence for a specific user-facing correctness improvement, not evidence of real-world adoption.
