# RISU Probe P5-E — measured AST optimization and 10-repository exact diagnostic parity

**Status:** completed on the experimental qualification branch, final two-OS CI [#42330673704](https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42330673704), both jobs SUCCESS.

## Why this optimization

Real `cProfile` of the existing RISU Python static analyzer identified repeated walks of the same AST as the dominant avoidable rule-pass cost. P5-E reuses a single ordered list of function AST nodes across binding, error branch, slice and exception handler checks, caching function inventories per file. **The rule predicates, reporting schema and evidence classifications were not changed.**

Exactly three installed-wheel modules differ from P5-D: `risu_static.py` for this optimization and `risu_probe.py` / `risu_firstuse.py` for the `0.9.20.dev0` version presentation. The other **35 of 38 modules are byte-identical** to the corresponding P5-D original wheel, checked inside CI separately for Linux and Windows. A Windows newline conversion discovered by an independent master audit was corrected before the final run; the separate CI wheel-identity gate now rejects this regression.

## Measured results (FINAL CI, 3 CLI runs per repository and implementation)

| Same-OS comparison | Ubuntu runner | Windows runner |
|---|---:|---:|
| Baseline P5-D median of repository medians, full installed CLI | 958.761 ms | 922.960 ms |
| Candidate P5-E median of repository medians, full installed CLI | 633.007 ms | 628.966 ms |
| Within-run time reduction | 34.0% | 31.9% |
| Individual repos with faster median CLI run | **10/10** | **10/10** |
| Median reduction in `ast.walk` call counts measured by `cProfile` | **57.19%** | **57.19%** |
| Full JSON diagnostic parity excluding only display version | **10/10** | **10/10** |
| Any shifted diagnostic verdict, code, file/line, evidence, coverage, OpenAPI fields | **0** | **0** |

**Larger external example:** FastMCP decreased from 10,501.449 to 7,567.973 ms on the Linux runner and 10,115.292 to 7,587.597 ms on the Windows runner.

The repository pins are unchanged from [P5-D's ten-source manifest](p5d/external_repos.json): Requests, HTTPX, Click, Meilisearch Python, FastAPI, CNOE codegen, MCP Python SDK, FastMCP, Pydantic Settings, and MCP reference servers.

**Reproducibility:** Both CI OSes downloaded and SHA-256-verified their own exact P5-D wheel from [run #42327747638](https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42327747638). Each installed baseline and optimized wheel in its own venv, checked AST rule counterexamples and byte-level allowed-source changes, pinned all ten upstream checkouts, ran three alternating-order CLI samples for each case, compared the complete normalized JSON (including the rule/message/evidence/file/order and coverage information), and then captured actual function-by-function `cProfile` calls for both wheels across all ten projects. The independent audit independently cross-checks per-repo profiles against benchmark outcomes.

CI evidence artifacts: `risu-p5e-ast-profile-parity-Linux` and `risu-p5e-ast-profile-parity-Windows` for run #42330673704, including both test wheel, precise timings, per-project profiles, hashes and source provenance.

## Interpretation and limits

- `cProfile` durations include instrumentation overhead. The separate CLI subprocess timings include Python startup and JSON output. Neither is a promise of identical speedup on an arbitrary machine.
- All ten repos are fixed public projects, not a statistically representative ecosystem sample. Filesystem caches and CI runner load vary; previous successful runs had different absolute timings.
- The static analyzer never imports or executes the scanned source; these outcomes demonstrate **unchanged offline diagnostics**, not preservation of all runtime behavior.
- This is an experimental wheel `risu-probe-preview 0.9.20.dev0`, not a PyPI release or evidence of production adoption. Main branch remains untouched.
