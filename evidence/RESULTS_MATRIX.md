# Empirical Results Matrix

| Stage | Target | Evidence path | Preserved | Loss | Invented | N/A | Decisive observed mechanism |
|---|---|---|---:|---:|---:|---:|---|
| E4 | FastMCP 3.4.7 | Official PyPI package → OpenAPIProvider → FastMCP server/client → raw CallToolResult | 0 | 11 | 0 | 1 | Non-2xx Problem JSON parsed, then demoted into diagnostic error prose; same-tool 200 JSON stayed structured |
| E5 | CNOE `openapi-mcp-codegen` @ `d0d9e1d...` | Actual generator → generated API client/tool/server → real HTTP → MCP stdio | 0 | 11 | 0 | 1 | Client retained full error JSON under `details`; generated tool discarded `details` and returned generic structured error |
| E6 | `nihal1294/openapi-to-mcp` @ `e5fbb352...` | Actual generator → generated TypeScript server → real HTTP → raw MCP stdio | 0 | 11 | 0 | 1 | Rich target error metadata emitted, but source Problem object unavailable through frozen accepted carriers |
| E7 | Non-normative reference bridge | Real HTTP → fixed mapping → official MCP 2026-07-28 TypeScript v2 server/client → captured stdio wire | 11 | 0 | 0 | 1 | Typed `application/problem+json` embedded resource preserved body; `_meta` separately retained observed HTTP facts |

## Comparative reading

The table does not show merely “three failures and one success.” It isolates three different propositions:

1. **Replication:** semantic loss appears in three tested translation architectures.
2. **Mechanism diversity:** the loss occurs through different transformations rather than one identical code defect.
3. **Constructive falsification of a protocol-capacity explanation:** the reference control carries the same exercised semantics across the tested official MCP wire.

The E7 row is not evidence that its representation is uniquely correct. It is an existence proof.


## RC1 reproducibility gate

RC1 is **not a fourth translator target**. It is a fresh-install reproduction of the E7 constructive positive control.

| Gate | Dependency state | Build/process state | Protocol | Preserved | Loss | Invented | N/A |
|---|---|---|---|---:|---:|---:|---:|
| RC1 clean-room | Exact lockfile, new empty npm cache, fresh `node_modules` | Fresh TypeScript build and fresh fixture/client/server processes | MCP 2026-07-28 stdio | 11 | 0 | 0 | 1 |

The RC1 internal `SHA256SUMS` ledger contains **36 file entries**. The prior E7 run separately verified an **E7 39-file internal ledger**. These counts refer to different evidence snapshots and MUST NOT be conflated.
