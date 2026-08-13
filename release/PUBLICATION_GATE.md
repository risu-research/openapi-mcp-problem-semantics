# Publication gate for v0.1.0-rc1

## Machine-verifiable gate

Run:

```bash
python3 verify_release.py
```

Expected result: `RC1 release verification: PASS`.

## Human-controlled gate

Do not publish merely because the verifier passes. Before public repository/tag/preprint actions, explicitly decide:

1. **License:** choose code and documentation/content licenses. No license is selected by this artifact.
2. **Authorship:** record final author/contributor names and affiliations exactly as desired for citation.
3. **Repository identity:** choose owner, repository name, and visibility.
4. **Raw evidence privacy:** historical raw archives are immutable but some contain machine-local absolute paths. A scan found no live credential-like secrets; placeholder authorization examples exist in upstream/template source. Decide whether to publish raw archives unchanged, publish clearly labeled sanitized derivatives alongside original hashes, or publish only hashes and provide originals on request.
5. **Timestamp order:** prefer repository/tag release before preprint submission so the executable artifact has a stable technical timestamp.

None of these governance choices changes the frozen scientific result.
