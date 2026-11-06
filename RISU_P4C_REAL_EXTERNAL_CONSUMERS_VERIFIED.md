# RISU Probe P4-C — Real External MCP Consumer Code Qualification (Verified)

**CI: PASS**, independently audited: https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42156699588 (tested source commit 213800222657081f8b545b3aa48f45797874ada5).

This is the **first qualification against real third-party MCP consumer implementations**, with the exact committed source installed in three isolated environments. The MCP responses were synthetic, constructed via each environment's installed MCP SDK and delivered through local fake transport interfaces; no production service or external MCP server was contacted. No LLM was queried and no vendor repository was patched.

## Strict source/protocol pins

Three repositories, exact Git commits, and the original source file Git blob SHA-1s were frozen before running tests in [p4c/FROZEN_EXTERNAL_CONSUMER_PROTOCOL.json](p4c/FROZEN_EXTERNAL_CONSUMER_PROTOCOL.json):

1. LangChain MCP: langchain-ai/langchain @ bb6a25a878527136dcb1a20507d5c20049427f96, libs/langchain_v1/langchain/mcp/tools.py @ ad0c6b0c65226f88432246bad0edcebc63496623. Called actual as_langchain_tool through a local synthetic client and inspected the actual ToolMessage.
2. OpenAI Agents SDK MCP: openai/openai-agents-python @ d4f07df2915ddb029d7076595bb7d4ce89322308, src/agents/mcp/util.py @ d51a773342c93239a1b79f1056ca889f37599d57. Called actual MCPUtil.invoke_mcp_tool and inspected actual model-visible tool output.
3. PydanticAI MCP: pydantic/pydantic-ai @ 61db3e988851c8905bc16c8f518a1052deccec5d, pydantic_ai_slim/pydantic_ai/mcp.py @ e00e00cd395da3b23a7ffff07dc47317aba0f4f0. Called actual _map_mcp_call_tool_result with prefer_structured=True as the preservation control.

The exact four scenarios were preregistered: E1 (structured-content-only error; content=[]), E2 (structured error plus generic text), S1 (same structured payload on success), and T1 (text-only error).

## Confirmed behavior in the original library code

Input E1: structuredContent={"code":"RATE_LIMITED","retry_after":30}, isError=true, content=[].

| Original external consumer | E1 | E2 (generic error text also present) | S1 (success) |
| --- | --- | --- | --- |
| LangChain MCP | Actual ToolMessage(status=error), artifact=None, placeholder text. retry_after absent from artifact/model text | artifact=None, only generic error text | success artifact retains full structured_content including retry_after |
| OpenAI Agents MCP | Actual model-visible tool output is [] | model-visible text "rate limited", no retry_after | model-visible JSON text includes retry_after |
| PydanticAI MCP | Actual mapper retains {"code":"RATE_LIMITED","retry_after":30} | retains full structured error | retains full structured payload |

All 12 real consumer-path executions across 3 frameworks and 4 fixed cases passed their pre-registered assertions; the independent evidence auditor also passed.

**Novelty limits matter.** LangChain structuredContent loss on isError had already been reported in [langchain-ai/langchain#40471](https://github.com/langchain-ai/langchain/issues/40471) (opened August 29, 2026), and must not be marketed as RISU's original bug discovery. The OpenAI SDK source explicitly documents its preference for error content text even when structuredContent accompanies an error. This is an **observed compatibility consequence of an intentional policy**, not evidence that OpenAI violates MCP or that production users are harmed. PydanticAI is a useful negative control. **Zero new undocumented upstream defects and zero production user incidents have been verified.**

## Secondary, post-hoc safe producer-side mitigation

A *separate post-hoc test*, not part of the pre-registered discovery denominator, used a minimal synthetic error containing only {"retry_after":30}. Where isError=true, content=[] and an explicitly reviewed structured error is present, it adds one TextContent block with the JSON string '{"retry_after":30}'.

This uses an **explicit non-sensitive allowlist** (only known synthetic RATE_LIMITED and bounded integer retry_after), never copies arbitrary error bodies, and never changes unrelated successful results or existing text. The updated results were passed through the exact same original external consumer functions.

- LangChain: retry_after becomes visible in model text, but the machine artifact **remains None**, so this is **not** a full structured artifact fix.
- OpenAI Agents: the previously empty model-visible output now carries the allowlisted retry_after JSON text.
- PydanticAI: structured payload is retained unchanged before and after, including already-correct cases.
- All three secondary, post-hoc tests passed, with an independent audit preventing the mitigation from being misrepresented as a full upstream fix.

This text fallback matches MCP's backward-compatibility recommendation that servers returning structured content should normally include useful text. It remains optional: do not automatically expose error details from unreviewed real workloads.

## Safeguards / reproducibility

- GitHub Actions original-code CI: https://github.com/risu-research/openapi-mcp-problem-semantics/actions/runs/42156699588.
- All exact Git source and blob hashes are checked in the Docker build.
- Network is enabled only for public source/dependency installation in the **ephemeral build**. Actual consumer function execution is performed in a **network-none, read-only, nonroot Docker container** with capabilities removed and bounded memory/CPU.
- The original libraries are installed from exact source commits in three independent virtual environments. No OpenAI API key, GitHub account token, real payment, external service request, LLM run, security exploit, or issue/PR submission.
- The original result code plus explicit known-issue classification: [p4c/run_external_consumers.py](p4c/run_external_consumers.py) and [p4c/audit_results.py](p4c/audit_results.py).
- The narrow mitigation and tests: [p4c/run_secondary_mitigation.py](p4c/run_secondary_mitigation.py).
- Full workflow artifacts: risu-p4c-actual-external-consumer-code-audit, including preregistration, three original function results, three secondary results and independently verified hashes.

## Decision about RISU product investment

This round **passes the external consumer-code execution gate** and demonstrates a real interoperability risk that the earlier pure OpenAPI scanner cannot capture. It does **not** pass the much stronger gate "new original upstream integration bug" or "independent developer adoption". Before building a new generic feature, the next rational choice is an exceptionally narrow candidate tied to a real external consumer contract, ideally a public issue with maintainer feedback or a concrete, previously unreported mismatch. Do not relabel the documented LangChain issue or OpenAI's intentional error policy as a novel discovered flaw.

The qualified v0.9.7 product source remains untouched; P4-C is a **separate read-only qualification harness**.
