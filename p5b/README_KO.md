# RISU Probe P5-B. Real external consumer consequence and source-backed repair

A single `run_full_chain.py` execution collects all three comparison phases. It uses **unchanged original** official archived Meilisearch OpenAPI error example, generated MCP server from the original pinned CNOE code generator, actual MCP SDK stdio sessions and original pinned LangChain MCP tool consumer; it then sends the displayed result body to the **unmodified official Meilisearch Python SDK** `MeilisearchApiError` decoder.

1. **Original source** HTTP 404 JSON: the external SDK obtains `code=index_not_found` and the explicit test-application consumer condition passes.
2. **CNOE conversion**: original HTTP 404 goes over loopback to the original CNOE-generated MCP server, through authentic stdio JSON-RPC, into unmodified LangChain; LangChain receives a success-status `ToolMessage` with generic error content (as recorded by P4-D). The original Meilisearch SDK parses this output but its `.code` is `None`. Our **explicit test-application contract** raises `SourceErrorContractFailure`. *The official SDK itself does not raise on missing `.code`; do not misattribute the failure.*
3. **Repaired producer boundary**: the test-only stdio proxy passes original CNOE success results byte-equivalently, but for the single exact, preregistered 404 case, adds the *separately verified original HTTP body* into `structuredContent` and a JSON text block and sets `isError=true`. The same unmodified LangChain tool consumer and Meilisearch SDK then satisfy the identical fixed application contract.

The proxy **cannot recover information solely from lossy MCP output**. Its original HTTP 404 body is explicitly passed from the local provider replay fixture; a practical production solution would require source-side instrumentation or retaining a safe error envelope at the converter boundary. The test adapter does *not* patch CNOE, LangChain or Meilisearch SDK and is *not* itself an upstream product fix. Only the public documented 404 response example and no vendor API endpoint are used.

All actual MCP stdio frames between original server, proxy and external SDK client are recorded in `passthrough_wire.jsonl` and `repair_wire.jsonl`, plus one report and independent standard-library auditor. Runtime is in Docker with `--network none`, nonroot, read-only filesystem, no credentials and no LLM calls. Pinned Git commit and source blob checks are enforced before execution.

**To rerun in a clean checkout**, run the P5-B GitHub Actions workflow or:

```bash
docker build -f p5b/Dockerfile -t risu-p5b .
mkdir -p results && chmod 0777 results
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
  --user 65534:65534 --pids-limit 128 --memory 3g --cpus 2 \
  --tmpfs /tmp:rw,nosuid,nodev,size=256m,mode=1777 \
  --mount type=bind,src="$PWD/results",dst=/results risu-p5b
python p5b/audit.py results/full_chain.json results/INDEPENDENT_AUDIT.json
```

The record does not substantiate a previously unknown production defect or a production user outage. Original successful requests are negative controls and are not modified by the adapter.