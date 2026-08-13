#!/usr/bin/env python3
"""Non-normative reference mapping model for the preservation profile.

This is an executable model of ONE conforming mapping, not a required MCP
representation. It deliberately uses only carriers already admitted by the frozen
carrier-neutral adapter v0.2:

* RFC 9457 body -> typed embedded resource (`application/problem+json`)
* observed HTTP facts -> namespaced result `_meta`
* successful JSON -> `structuredContent` plus serialized TextContent

It never mines human prose and never infers retryability or other behavioral claims.
"""
from __future__ import annotations

import json
from urllib.parse import quote

PROBLEM = "application/problem+json"


def media_base(value: str | None) -> str:
    return str(value or "").split(";", 1)[0].strip().lower()


def _source_meta(source: dict) -> dict:
    m = {
        "observed_http_status": int(source["http_status"]),
        "content_type": source.get("content_type"),
    }
    if source.get("content_language") is not None:
        m["content_language"] = source["content_language"]
    return {"org.risu.reference.source_http": m}


def _data_uri(media_type: str, text: str) -> str:
    # Self-contained valid URI: no dereferenceability or external identity claim.
    return f"data:{media_type},{quote(text, safe='')}"


def map_source_to_raw_call_tool_result(source: dict) -> dict:
    status = int(source["http_status"])
    mt = media_base(source.get("content_type"))
    body = source.get("body")
    is_error = not (200 <= status < 300)

    if mt == PROBLEM and isinstance(body, dict):
        text = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        return {
            "content": [
                {
                    "type": "resource",
                    "resource": {
                        "uri": _data_uri(PROBLEM, text),
                        "mimeType": PROBLEM,
                        "text": text,
                    },
                }
            ],
            "isError": is_error,
            "_meta": _source_meta(source),
        }

    if 200 <= status < 300 and isinstance(body, dict):
        text = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        return {
            "content": [{"type": "text", "text": text}],
            "structuredContent": body,
            "isError": False,
            "_meta": _source_meta(source),
        }

    # Out-of-profile error representation. Do not infer RFC 9457 from field shape.
    return {
        "content": [{"type": "text", "text": f"Upstream HTTP {status}"}],
        "isError": is_error,
        "_meta": _source_meta(source),
    }
