# Conformance corpus

This directory is the frozen executable research contract used across E4, E5, E6, and E7.

Files:

- `cases.json`: source fixtures and semantic case definitions;
- `cases.executable.json`: executable checks and forbidden claims;
- `openapi.json`: shared OpenAPI source description;
- `oracle.py`: frozen case verdict logic;
- `carrier_neutral_adapter_v02.py`: target observation normalizer.

The same SHA-256 digests for `cases.json`, `cases.executable.json`, `openapi.json`, and `oracle.py` appear in all four evidence stages. Adapter v0.2 is the audited carrier-neutral revision used for E5–E7 and for final comparative interpretation.

The public profile is intentionally bounded. Do not add cases merely to increase corpus size. A new profile version should be created only when a new case exercises a meaningful semantic boundary not already covered.
