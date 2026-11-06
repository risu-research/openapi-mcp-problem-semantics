# RISU Probe 0.9.4 — P0 decision consistency + first Consumer Witness

## Verified scope

- Experimental branch: experiment/risu-probe-v094-decision-witness-20261105.
- Original research main, v0.9.1, v0.9.2 and v0.9.3 are unchanged.
- Python 3.11+, stdlib product. All live tests use synthetic localhost-only HTTP GETs.
- Full qualification runs six Windows/Ubuntu Python environments and executes actual pinned CNOE, FastMCP and MCPGen generated tools in an isolated no-network container.
- The model consumers below are **deterministic Python policies**. They are NOT real LLM clients or empirical agent-task-success estimates.

## P0: Same policy in every output

The original \`verdict\` remains for comparison with published results. The additional \`decision_v1\` holds the same action-oriented interpretation across JSON, text, Markdown, SARIF and exit codes. All commands use the common \`risu_decision\` module.

| Outcome | Meaning | Calibrated CI behavior |
| --- | --- | --- |
| PASS | Exact body is available via structuredContent; no stronger issue detected | Do not block |
| REVIEW | Exact text is recoverable but no structured carrier, metadata-only, unknown text, or other insufficient evidence | Report as SARIF warning; do not block by default |
| FAIL | Confirmed error-flag mismatch, explicitly conflicting observed status, unsupported retry claim, clipped preview, or an inspection that could not complete | Block when failure gating is enabled |
| DEFERRED | An incomplete MCP request needs user input | Report as SARIF note |
| NOT_APPLICABLE | Content outside selected comparison profile | No preservation claim |

The old machine-carrier \`LOSS\` is a *strict carrier policy finding*, not a proof of destroyed data. \`--policy strict-carrier\` restores strict blocking for it, with an explicit \`STRICT_CARRIER_CONTRACT_VIOLATION\` reason. \`--fail-on-review\` permits CI to block unverified observations too.

Operational inspection failures share the FAIL outcome but are **not represented as verified content loss**; the reason \`INSPECTION_INCOMPLETE\` explicitly distinguishes them.

## P1: Consumer Witness

The witness reads an actual saved HTTP source and MCP tool response, never runs any app or calls a network:

1. \`structured-only\`: only reads the top-level \`structuredContent\` object. Does not search metadata or parse content text.
2. \`json-text-data\`: scans text parts in order, takes the **first parseable complete JSON**, and unwraps \`data\` only when the JSON object has an integer \`status_code\` alongside an object/array \`data\`. It **never** examines source values to pick among candidate messages. Duplicate JSON keys and nonfinite numbers are rejected.

Consumers compare explicitly declared RFC 6901 JSON Pointer fields to the upstream values with exact types and full nested values, optionally check \`isError\`, and optionally require the HTTP status as a separate consumer contract.

**Verified on final non-oracle consumer code**: GitHub Actions [run #42141715063](https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42141715063), **7/7 jobs PASS**, independent external-project audit PASS. Clean Docker dependency image build plus actual three-project execution: **155 seconds** on that hosted runner. 12 observed cases, 12 counterfactual source mutations rejected; 36 expected localhost GETs, zero unexpected requests. Calibrated policy results: **2 PASS, 3 FAIL, 7 REVIEW**. Consumer field-contract passes: **structured-only 2/12, json-text-data 6/12**; four divergent outcomes, all from MCPGen.

| Project | 200 | 400 / 409 / 422 | Consumer delta |
| --- | --- | --- | --- |
| CNOE | Both readers pass | Both fail, error flags also lost | No divergent consumer outcomes |
| FastMCP | Both readers pass | Both fail required error-status field extraction | No divergent consumer outcomes |
| MCPGen | Only JSON-text reader passes | Only JSON-text reader passes | Four meaningful divergences |

The results do **not** assert that real LLMs will behave identically to the deterministic consumers.

## Usage

Install the validated wheel in a fresh environment, then:

    risu-probe --version
    risu-probe first-check . --json
    risu-probe analyze MATRIX.json --format json
    risu-probe analyze MATRIX.json --format sarif --fail-on-loss
    risu-probe analyze MATRIX.json --policy strict-carrier --fail-on-loss
    risu-probe analyze MATRIX.json --fail-on-loss --fail-on-review
    risu-probe witness MATRIX.json --path /status
    risu-probe witness MATRIX.json --path /status --require-http-status
    risu-probe witness MATRIX.json --path /status --fail-on-consumer structured-only
    risu-probe witness MATRIX.json --path /status --fail-on-consumer json-text-data

Source and MCP response matrices remain local. Witness reports include no raw HTTP/MCP response values, only categorical findings and field counts. The user must choose a pointer present in **every** source response in the input file; mixed schemas require separate matrices or appropriate per-case contracts.

## Exact qualification and limits

The SHA-verified reconstruction chain is:

    python ci/export_v09_source_portable.py
    python ci/upgrade_v10_modules.py
    python ci/upgrade_v11_semantics.py
    python ci/upgrade_v12_decision_witness.py

The GitHub workflow \`.github/workflows/risu-v094-decision-witness.yml\` runs all direct tests and exact external generated server comparisons. Pinned generators: CNOE commit \`8c2b065497cf32ecbb7cf7e28dad3a99c6706c3f\`, MCPGen commit \`30ee7cb9c2e923ce901e788b0d911f6547772866\`, FastMCP \`4.1.6\`. This is a synthetic read-only interoperability proof, not ecosystem-prevalence research, MCP conformance certification or proof of unaffiliated developer adoption.

Next priority: explicit consumer contracts from independent application repositories, minimal reproducer generation, and confirming changes in real downstream task behavior.
