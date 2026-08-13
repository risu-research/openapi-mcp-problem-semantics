#!/usr/bin/env python3
"""MCP CallToolResult -> semantic-fidelity observation adapter v0.2.

Machine-addressable candidates accepted by this profile:
1. `structuredContent` JSON;
2. `_meta` JSON;
3. an embedded MCP resource whose declared MIME type is
   `application/problem+json` and whose text is valid JSON.

Plain TextContent is diagnostic only. It is never mined for semantics.
Resource links are not treated as direct preservation because recovering the
problem object would require another fetch and the object is not present in
this tool result.
"""
from __future__ import annotations
import copy, json

PROBLEM = "application/problem+json"


def _walk(value):
    yield value
    if isinstance(value, dict):
        for v in value.values():
            yield from _walk(v)
    elif isinstance(value, list):
        for v in value:
            yield from _walk(v)


def _find_exact_or_superset(container, source_body):
    if not isinstance(source_body, dict):
        return None
    for node in _walk(container):
        if isinstance(node, dict) and all(k in node and node[k] == v for k, v in source_body.items()):
            return copy.deepcopy(node)
    return None


def _embedded_problem_objects(raw):
    out=[]
    for block in raw.get("content") or []:
        if not isinstance(block,dict) or block.get("type") != "resource":
            continue
        resource=block.get("resource")
        if not isinstance(resource,dict):
            continue
        mt=str(resource.get("mimeType") or "").split(";",1)[0].strip().lower()
        if mt != PROBLEM:
            continue
        text=resource.get("text")
        if not isinstance(text,str):
            continue
        try:
            obj=json.loads(text)
        except (ValueError,TypeError):
            continue
        if isinstance(obj,dict):
            out.append(obj)
    return out


def _find_observed_status(container):
    names={"observed_http_status","http_status","httpStatus","status_code","statusCode"}
    for node in _walk(container):
        if isinstance(node,dict):
            for k,v in node.items():
                if k in names and isinstance(v,int) and 100 <= v <= 599:
                    return v
    return None


def _claims(container):
    out={}
    truthy={"retryable":"retryable_true","safe_to_retry":"safe_to_retry_true","safeToRetry":"safe_to_retry_true","idempotent_retry":"idempotent_retry"}
    for node in _walk(container):
        if isinstance(node,dict):
            for k,label in truthy.items():
                if node.get(k) is True:
                    out[label]=True
    return out


def _diagnostic(raw):
    texts=[]
    for block in raw.get("content") or []:
        if isinstance(block,dict) and block.get("type")=="text" and isinstance(block.get("text"),str):
            texts.append(block["text"])
    return "\n".join(texts) if texts else None


def raw_result_to_observation(raw, source):
    structured={"structuredContent":raw.get("structuredContent"), "_meta":raw.get("_meta")}
    embedded=_embedded_problem_objects(raw)
    all_machine={"structured":structured,"embedded_problem_resources":embedded}
    machine={}
    if str(source.get("content_type","")).split(";",1)[0].strip().lower()==PROBLEM:
        body=_find_exact_or_superset(all_machine,source.get("body"))
        if body is not None:
            machine={"semantic_type":"rfc9457-problem","body":body,"content_type":PROBLEM}
            observed=_find_observed_status(all_machine)
            if observed is not None:
                machine["observed_http_status"]=observed
    return {
        "machine":machine,
        "diagnostic":_diagnostic(raw),
        "claims":_claims(all_machine),
        "_wire":{
            "isError":raw.get("isError"),
            "structuredContent_present":raw.get("structuredContent") is not None,
            "meta_present":raw.get("_meta") is not None,
            "embedded_problem_resource_count":len(embedded),
        },
    }
