# P4-V | Real external MCP `$ref` and `anyOf` qualification

Date: 2026-11-06. Official `modelcontextprotocol/servers` `mcp-server-time` releases **2026.10.19 → 2026.11.4**, from exact PyPI wheels verified by SHA-256 and executed in separate isolated Python environments.

**GitHub Actions success:** https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42306722031

## Observed and verified

- True MCP stdio JSON-RPC `initialize`, `tools/list`, `tools/call` from both installed releases.
- `convert_time` expanded output paths: **11 → 24**. One optional added parent `/later_occurrence`, twelve conditional paths under its `anyOf` object branch. Original `TimeResult` required `$ref` descendants remain unchanged.
- New unconditionally mandatory advertised output fields: **zero**.
- In normal current-time-controlled execution, `later_occurrence` was `null`. In separate actual runtime execution with a **fixed test clock** for the US DST fall-back on 2026-11-01 at 01:30 in America/New_York, the released new server produced a non-null object with the second occurrence (`-05:00`); the previous release did not have this field.
- Recomputed raw wire and tool response SHA-256 receipts, with the MCP frame present in the recorded transcript.
- The existing P4-T history and P4-U original superficial comparison remain unchanged. These CI scripts independently check the nested real-release case. The extended full strict analyzer and its 37 local adversarial tests are distributed in the separate P4-V master ZIP.

**Evidence boundary:** Released public packages were genuinely executed, but the injected clock is a test fixture. No independent historical production trace, legal supplier commitment, production data loss, or real-world downstream consumer failure is inferred. A nested field marked required within an optional `anyOf` branch is not a global must-output obligation.

Scripts: `p4v/dst_probe.py`, `p4v/nested_eval.py`.

CI: `.github/workflows/risu-p4v-real-external-nested-anyof.yml`.
