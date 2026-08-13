# Raw evidence assets

The five immutable raw evidence archives are intentionally **not embedded in the main RC1 source archive**. They should be attached as separate release assets if/when publication is desired. This keeps the source snapshot reviewable and avoids silently repackaging historical evidence.

Their exact SHA-256 digests are recorded in `RAW_EVIDENCE_ASSETS.sha256`.

Publication hygiene note: a scan found **no live credential-like secrets** in the five archives. Some historical provenance files contain machine-local absolute paths (for example a local user directory), and source templates contain placeholder authorization examples. Review that metadata before making the raw archives public. Do not rewrite historical archives without changing their hashes and documenting the sanitization as a derivative artifact.
