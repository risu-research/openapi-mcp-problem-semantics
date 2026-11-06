# RISU Probe P4-E — Second Independent Public API → MCP Converter → Consumer Qualification

**RESULT: PASS**. Final GitHub Actions [run #42167138991](https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42167138991) at pinned candidate commit `91fc6036879528ae4e418615dd3691d12c35533c` completed successfully. Independently replaying the downloaded evidence archive also passed. Eight mutated-evidence tests were detected.

## Why this is independent of P4-D

| | P4-D (first case) | P4-E (this case) |
|---|---|---|
| Original public API contract | Meilisearch GET /indexes/{indexUid} | **DeepL GET /v2/usage** |
| Actual converter | CNOE openapi-mcp-codegen | **FastMCP 4.1.6 from_openapi** |
| Actual consumer code | LangChain MCP ToolMessage | **PydanticAI MCP result mapper** |
| Observable mechanism | CNOE lost the original error code and set isError=false | FastMCP set isError=true; typed error code lost, 429 code absent even from text |
| Production service contacted? | No | No |

## Frozen public source

- DeepL official public OpenAPI file: `DeepL/openapi` at commit `2b5e50f83888960923bf7c842e75ef2dbf309e96`, path `openapi.json`, Git blob `f1029f7003e08ce82c3322bd3f6d9ad97f594ee2`. Source file length 471,671 bytes and SHA-256 `58640716fb614dfe5b65fbebbde46fc78a367f9d02cc50e4429c31c5e40692f6`. OpenAPI version 3.0.3, API documentation version 3.14.0.
- The vendor operation is **GET /v2/usage**, operationId **getUsage**, and documents 200, 429 and 456 responses. ErrorResponse requires `message` and permits an optional machine-readable `code`. The normal 200 response uses the vendor's actual published `free` example.
- Conversion engine: FastMCP **4.1.6**, separate environment with MCP SDK **2.3.0**.
- Consumer: `pydantic/pydantic-ai` at commit `61db3e988851c8905bc16c8f518a1052deccec5d`, original `pydantic_ai.mcp._map_mcp_call_tool_result` run with `prefer_structured=True`, source blob `e00e00cd395da3b23a7ffff07dc47317aba0f4f0`.

## Exact real local execution

The original official spec's **single GET operation** and all transitive referenced component schemas are projected into a local spec. The local copy replaces the vendor server URL with loopback and removes the production authentication requirement. It does not change the original operation's declared responses and schema. The original source file is included with the CI evidence.

A real local HTTP server returns, in order:
- **200**: the vendor-published `{"character_count":180118,"character_limit":1250000}` free example.
- **456**: schema-conforming SYNTHETIC `{"message":"Local synthetic character quota exhausted","code":"RISU_SYNTH_QUOTA_EXCEEDED"}`.
- **429**: schema-conforming SYNTHETIC `{"message":"Local synthetic request rate limit","code":"RISU_SYNTH_RATE_LIMITED"}`.

**Both error code values and their messages are local test data**, not actual DeepL response examples, and not observed from the production DeepL service. They only exercise fields the public vendor error schema permits.

FastMCP's authentic OpenAPI converter creates the server; a real MCP SDK stdio session initializes it, lists `getUsage` and calls it three times; the unmodified external PydanticAI mapper consumes the real MCP SDK results. The local HTTP server received exactly 3 declared GET calls and no other HTTP requests. All execution occurs inside `docker run --network none --read-only --cap-drop ALL` with nonroot execution and bounded resources. Only pinned public source and dependencies are downloaded at image build time; no vendor API, account credential or LLM is accessed.

## Real observed outputs

| Case | MCP isError | MCP structuredContent | PydanticAI original mapper | Original test code visible in final output? |
|---|---|---|---|---|
| 200 success | false | original usage JSON dict | original usage JSON dict | N/A |
| 456 quota | true | null | string containing HTTP 456 and original synthetic JSON | **Yes in text; no typed field** |
| 429 rate | true | null | `Rate limited by upstream API, please retry later` | **No, not even as text** |

The PydanticAI unmodified mapper separately preserved structured error codes when an authentic MCP SDK CallToolResult containing `structuredContent` was supplied as a control. Thus, in these selected executions, typed information was absent from FastMCP's delivered error response before the mapper received it. For 456, text recovery remains possible. For 429, the supplied test-specific error `code` and `message` were replaced by a generic message.

The 429 standardization is also described by FastMCP's own OpenAPI documentation. **This is a reproducible compatibility consequence, not evidence of an unknown upstream vulnerability, a normative MCP specification breach, or a user incident.**

## Independent external checks and adversarial controls

The CI preserved both the pinned original DeepL OpenAPI bytes and the local HTTP response *byte strings*. The independent audit checks the original Git blob SHA-1 and SHA-256, the unchanged selected source operation, its response definitions, HTTP byte hashes, exact case ordering, MCP error flags, code visibility classifications, consumer output shape, and the claimed outcome.

Eight altered evidence tests were independently rejected, including modified HTTP status, forged consumer typed visibility, changed original code, altered verdict, broken positive control, manipulated MCP flag, mutated HTTP bytes, and changed projected spec.

The downloadable CI artifact is named `risu-p4e-deepl-fastmcp-pydanticai-full-chain`, with GitHub artifact ID **13480150205** and SHA-256 for the ZIP `4ffc6737e98b51c5e791e5e4e9419afadc88c7a771b4d9c40e16b0dae54b04be`.

## Reproduction

From a checkout of this branch, with Docker and public GitHub/PyPI network access available for build:

```bash
docker build -f p4e/Dockerfile -t risu-p4e:local .
mkdir -p results && chmod 777 results
docker run --rm --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges --user 65534:65534 \
  --pids-limit 128 --memory 3g --cpus 2 \
  --tmpfs /tmp:rw,nosuid,nodev,size=256m,mode=1777 \
  --mount type=bind,src="$PWD/results",dst=/results \
  risu-p4e:local --out /results/full_chain.json
python p4e/audit.py results/full_chain.json results/independent_audit.json
```

Check the `result` and `negative_mutation_detections` keys in `results/independent_audit.json`.

## Product decision

P4-E **passes** the bounded gate "second different public API specification + authentic different converter + authentic external consumer code". The results of P4-D and P4-E differ in their information-loss mechanisms, demonstrating why the Probe diagnosis must distinguish typed-loss, text-recoverable loss, actual missing values, and lost isError flags.

This does **not** prove that an independent developer would adopt RISU Probe, that the vendor's live API currently returns these precise error bodies, or that a newly undiscovered bug exists. Product v0.9.7 and earlier public research branches have not been modified. Avoid new generic feature development until a genuine third-party usage or maintainer-confirmed integration need exists.
