# RISU Probe P4-D — Independent Public OpenAPI → CNOE → LangChain Qualification

**Status: PASS.** [GitHub Actions #42164496830](https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42164496830), tested commit `6d5bdccdeca68a8d5a86c0096a1673ad6ad74f04`. The actual MCP/client execution step and independent audit step both succeeded.

This is the **first bounded full-chain evidence** in this project connecting three unrelated, public, pinned software sources: an original vendor API contract, an independent OpenAPI→MCP converter, and actual third-party consumer code. This is not a test against Meilisearch production services, a newly reported vendor defect, an MCP normative violation, or evidence of real-user impact.

## Original third-party sources and exact pins

- [Meilisearch official archived OpenAPI](https://github.com/meilisearch/open-api/blob/0b0b0fdbb9d5821ec018a3db2777986a231eec37/open-api.json) @ `0b0b0fdbb9d5821ec018a3db2777986a231eec37`, original Git blob `8e01bc5c07f4f17cc2f183ecfb427e2592ba333b`. API document v1.15.2. Original operation `GET /indexes/{indexUid}` (`get_index`), examples for HTTP 200 and 404, including `code=index_not_found`.
- [CNOE OpenAPI MCP generator](https://github.com/cnoe-io/openapi-mcp-codegen/tree/8c2b065497cf32ecbb7cf7e28dad3a99c6706c3f) @ `8c2b065497cf32ecbb7cf7e28dad3a99c6706c3f`. We executed the original generator and its generated MCP server without patching CNOE.
- [LangChain native MCP consumer](https://github.com/langchain-ai/langchain/blob/bb6a25a878527136dcb1a20507d5c20049427f96/libs/langchain_v1/langchain/mcp/tools.py) @ `bb6a25a878527136dcb1a20507d5c20049427f96`, original Git blob `ad0c6b0c65226f88432246bad0edcebc63496623`. We called actual `as_langchain_tool` through an initialized MCP stdio session and inspected real `ToolMessage` results.

## Actual source → converter → consumer results

| Layer | GET /indexes/movies, HTTP 200 | GET /indexes/does-not-exist, HTTP 404 |
| --- | --- | --- |
| Source HTTP | Original example fields `uid, primaryKey, createdAt, updatedAt` | Local replay of original example fields `message, code=index_not_found, type=invalid_request, link` |
| Generated MCP | `structuredContent` retains full successful response, `isError=false` | `structuredContent={"error":"API request failed: 404 - Index ... not found."}`, `isError=false`; `code`, `type`, `link` unavailable |
| LangChain ToolMessage | `status=success`, artifact includes original successful JSON | `status=success`, artifact includes generic error string but not `index_not_found` |

Runtime verified **4 actual localhost HTTP GET requests** (two 200; two 404) and **0 unexpected requests**. Source error code visibility: MCP **false**, downstream LangChain **false**. Original API path parameter `indexUid` was represented as `path_indexUid` by CNOE's `tools/list` schema. The first real-call attempt using `indexUid` failed tool argument validation before any HTTP was sent; the qualified run used the generated schema's declared `path_indexUid`.

The final producer-side error-code loss occurs **before** LangChain receives the result. Therefore the P4-C text fallback cannot recover `index_not_found` from the observed converted response. This is an observed compatibility consequence, not proof of a standards violation or malicious behavior.

## Evidence and self-falsification

- Final CI [#42164496830](https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42164496830), all steps PASS, including actual pinned source installation, generated MCP server, stdio client, native LangChain and independent audit.
- [Exact tested commit](https://github.com/risu-research/openapi-mcp-problem-semantics/commit/6d5bdccdeca68a8d5a86c0096a1673ad6ad74f04).
- Actions artifact `risu-p4d-real-meilisearch-cnoe-langchain`, artifact ID `13478865696`, SHA-256 `d6015926b19ab68979d8383d0c2646c29f6d750aeb01e2c19f815eba56812d7a`. The artifact contains original source pins, full result JSON and independent audit JSON.
- Recalculated exact full result digest from the CI artifact: `e811e0e557a5f447fc6a892cff5f0928a6cfca35a25b93aea550a6f5d78d3d3b`. Re-ran the independent auditor against downloaded evidence outside Actions: PASS.
- Additional offline audit mutations that altered HTTP request counts, MCP code visibility, downstream code visibility, LangChain error status, source error code and argument mapping were **all 6/6 detected**.

## Strict scope and safety

- The local test derived **one original read-only GET operation and dependent schemas** from the original public vendor OpenAPI. We did not transform the entire vendor spec or contact the live Meilisearch API.
- The local HTTP server replayed public success/404 example data; only the missing index name within the human-readable 404 message changed to match the local test input.
- No valid Meilisearch account token was used. The generated client required a token-shaped environment variable, so we used a clearly synthetic dummy with a localhost-only mock endpoint.
- Network access was available exclusively for public Git source/dependency installation during isolated Docker build. Test runtime used `--network none`, nonroot, read-only filesystem and limited resources. No LLM calls, external service writes, account data, or bypasses.
- RISU Probe v0.9.7 and the research main branch are unchanged. This qualification lives on a separate branch.
- This is **one pinned external integration case**, not measured external adoption or a representative prevalence estimate. Do not claim CNOE has an unreported bug or that LangChain is solely responsible for source fields already absent upstream.

**Next decision:** Preserve this end-to-end case as a reproducible first external integration benchmark. Test at least one other unrelated public API/converter/consumer chain before generalizing a new product diagnostic or presenting market-level claims.
