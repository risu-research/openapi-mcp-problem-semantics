# RISU Probe P6-A: one canonical developer product source tree

**Product quickstart:** [`risu-probe/README.md`](risu-probe/README.md). This repository also retains earlier academic research, release-candidate DOI and all historical experiment branches. They are intentionally not overwritten.

P6-A converts the exact code from the verified P5-E **Linux** wheel (GitHub CI #42330673704) into **38 checked-in, readable source files** in `risu-probe/src/`. All source SHA-256 values are frozen in `P5E_SOURCE_PROVENANCE.json`, and the historical wheel is retained only as a reference fixture in `p6a/reference/`.

Normal developers can now build and install directly with a standard `pyproject.toml`. They no longer need to replay the P4/P5 experimental patch series to get a product wheel. The installer and the package source live together under `risu-probe/`.

**Release gate:** Windows + Linux + macOS each independently build the wheel from checked-in source, validate all 38 source hashes and the CLI, install pinned default PyYAML, and run exact full-JSON parity against the original frozen P5-E installed wheel on the same 10 public repositories.

**No claim:** This is still a preview (`0.9.20.dev0`). It is not a PyPI public release, an MCP standard, evidence of new external bugs, or an external adoption statistic. No code modification of the P5-E analysis engine was needed to form this source tree.

**Other models:** Ruff's stable CLI, uv's simple source install, oasdiff/mcpdiff's version-change CI, Schemathesis's reproducible tests, MCP Inspector's existing protocol interfaces, Renovate's permissioned-gated updates. Product goals remain utility and developer experience, not forced uniqueness.
