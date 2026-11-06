# RISU Probe P4-H — native developer capture interoperability gate

Product lane: isolated `0.9.9.dev0` candidate. Main/default branch unchanged.

## One command

```bash
risu-probe analyze ./capture-directory --recovery --format text
```

`capture-directory` contains **unaltered** source forms:
- `capture.har`: HAR 1.2 HTTP response bodies, status and Content-Type
- `mcp.jsonl`: actual JSON-RPC 2.0 request/response frames containing `tools/call`
- `pairs.json`: explicit call-to-HTTP mapping, e.g. `{"schema":"risu-explicit-capture-pairing-v1","pairs":[{"case_id":"C404","target":"server-A","http_entry":0,"mcp_call_id":2,"tool":"get_data"}]}`
- `consumer.jsonl`: **optional**, only `kind=langchain_toolmessage` with `call_id` and unchanged serialized LangChain `ToolMessage` under `message`.

No source/mcp payload is silently inferred. Pairing is **declared by the developer**, not attested by the tool. Neither raw request URL, Authorization headers, nor original response body are exported in the report. Hashes fingerprint input files; they do not prove file origin or real-world causality. Missing consumer is marked UNTESTED. JSON-RPC protocol errors, `input_required`, duplicate IDs, mismatched tools, invalid or ambiguous HAR content, oversized or dangerous input are rejected, exit code 2. Existing `--fail-on-loss` remains exit code 1.

Supported native HAR HTTP: bounded GET with JSON object result and explicit Content-Type. HAR base64, response arrays, unpaired HAR entries, streaming multipart/SSE and SDK formats without a native JSON-RPC payload are **not** automatic matches. No remote request, user-code execution or LLM calls occur in analysis.

## Independent format trial and provenance

`runner/make_native_capture.py` runs **unmodified third-party Python MCP SDK v2.3.0** against an intentionally simplistic **author-written local test server**, captures raw stdio JSON-RPC via a byte-transparent recorder, and independently records actual local HTTP requests into HAR. This is a **new test recording**, independent from P4-D/P4-E archived conversions, but **it is not a real external developer's production recording**, nor an undisclosed bug in the MCP SDK.

The scripted server deliberately sends one correct 200 typed object and one 404 tool result where `isError` is set false, while the HTTP source returned 404. The test exists to measure whether the product can handle authentic external-library-generated native frames and produce the correct conditional diagnosis.

`tests/test_native_capture.py` also tests malformed, ambiguous and hostile captures, including exact typed JSON equality and refusal to treat a JSON-RPC-level error as a tool-error response. The existing P4-G `saved_p4de.json` is rerun under the new wheel as a nonregression control. Values remain hidden from exported output, even when the capture contains an Authorization header.

## Scope/next step

This proves **format compatibility for tested HAR 1.2 / JSON-RPC 2.0 captures and explicit call mapping**, not arbitrary real-world capture acceptance. The next hard proof is a genuine unrelated external developer-supplied recording with independently witnessed HTTP-to-MCP correspondence; if unavailable, remain conservative and do not call our own test recording such evidence.