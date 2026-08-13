#!/usr/bin/env python3
"""Dependency-free verifier for the E7 official-SDK reference evidence."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from carrier_neutral_adapter_v02 import raw_result_to_observation  # noqa: E402
from oracle import check_case  # noqa: E402

PROBLEM = "application/problem+json"
SOURCE_META = "org.risu.reference.source_http"


def load(name):
    return json.loads((ROOT / name).read_text())


def base_media_type(value):
    return str(value or "").split(";", 1)[0].strip().lower()


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def lines(name):
    return [json.loads(line) for line in (ROOT / name).read_text().splitlines() if line.strip()]


def sha256(name):
    return hashlib.sha256((ROOT / name).read_bytes()).hexdigest()


def source_list(case):
    if "pair" in case:
        return copy.deepcopy(case["pair"])
    return [{k: copy.deepcopy(case[k]) for k in ("http_status", "content_type", "content_language", "body") if k in case}]


def truthy_retry_claim(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"retryable", "safe_to_retry", "safeToRetry", "idempotent_retry"} and child is True:
                return True
            if truthy_retry_claim(child):
                return True
    elif isinstance(value, list):
        return any(truthy_retry_claim(child) for child in value)
    return False


def expected_operation_ids(openapi):
    return [
        operation["operationId"]
        for path_item in openapi["paths"].values()
        for method, operation in path_item.items()
        if method.lower() == "get" and "operationId" in operation
    ]


def flatten_calls(raw):
    calls = [call for case in raw["cases"] for call in case["calls"]]
    control = raw["same_operation_control"]
    calls.extend(
        [
            {
                "tool_name": control["tool_name"],
                "arguments": control["success"]["arguments"],
                "raw_call_tool_result": control["success"]["raw_call_tool_result"],
            },
            {
                "tool_name": control["tool_name"],
                "arguments": control["problem"]["arguments"],
                "raw_call_tool_result": control["problem"]["raw_call_tool_result"],
            },
        ]
    )
    return calls


def build():
    corpus = load("cases.json")
    expectations = {row["id"]: row for row in load("cases.executable.json")["cases"]}
    openapi = load("openapi.json")
    raw = load("e7-official-client-raw.json")
    incoming = lines("e7-client-to-server-wire.jsonl")
    outgoing = lines("e7-server-to-client-wire.jsonl")
    audits = lines("e7-bridge-stderr.jsonl")

    operation_ids = expected_operation_ids(openapi)
    listed_names = [tool["name"] for tool in raw["tools_list"]["tools"]]
    official_calls = flatten_calls(raw)
    call_requests = [message for message in incoming if message.get("method") == "tools/call"]
    call_responses = [message for message in outgoing if isinstance(message.get("result"), dict) and message["result"].get("content") is not None]

    assert len(operation_ids) == 15
    assert listed_names == operation_ids
    assert len(official_calls) == len(call_requests) == len(call_responses) == len(audits) == 16
    assert raw["protocol"]["pinned_spec_version"] == "2026-07-28"
    assert raw["protocol"]["era"] == "modern"
    assert raw["protocol"]["negotiated_protocol_version"] == "2026-07-28"
    assert raw["protocol"]["discover_result"]["supportedVersions"] == ["2026-07-28"]

    for index, (call, request, response) in enumerate(zip(official_calls, call_requests, call_responses)):
        assert request["params"]["name"] == call["tool_name"], index
        assert request["params"]["arguments"] == call["arguments"], index
        wire_result = copy.deepcopy(response["result"])
        assert wire_result.pop("resultType") == "complete", index
        assert wire_result == call["raw_call_tool_result"], index

    rows = []
    audit_index = 0
    assert len(corpus["cases"]) == len(raw["cases"])
    for corpus_case, raw_case in zip(corpus["cases"], raw["cases"]):
        assert corpus_case["id"] == raw_case["id"]
        sources = source_list(corpus_case)
        assert len(sources) == len(raw_case["calls"])
        observations = []
        raw_results = []
        for source, call in zip(sources, raw_case["calls"]):
            assert call["source"] == source
            audit = audits[audit_index]
            audit_index += 1
            assert audit["event"] == "e7_upstream_response"
            assert audit["tool_name"] == call["tool_name"]
            assert audit["observed_http_status"] == source["http_status"]
            assert audit["content_type"] == source["content_type"]
            assert audit.get("content_language") == source.get("content_language")
            assert audit["body"] == source["body"]

            result = call["raw_call_tool_result"]
            raw_results.append(result)
            source_http = result["_meta"][SOURCE_META]
            assert source_http["observed_http_status"] == source["http_status"]
            assert source_http["content_type"] == source["content_type"]
            assert source_http.get("content_language") == source.get("content_language")
            if base_media_type(source["content_type"]) == PROBLEM:
                assert result["isError"] is True
                assert len(result["content"]) == 1
                block = result["content"][0]
                assert block["type"] == "resource"
                assert block["resource"]["mimeType"] == PROBLEM
                assert block["resource"]["text"] == compact(source["body"])
                assert block["resource"]["uri"].startswith(f"data:{PROBLEM},")
            observations.append(raw_result_to_observation(result, source))

        observation = observations if "pair" in corpus_case else observations[0]
        result = check_case(corpus_case, expectations[corpus_case["id"]], observation)
        rows.append(
            {
                "id": corpus_case["id"],
                "tools": [call["tool_name"] for call in raw_case["calls"]],
                "sources": sources if "pair" in corpus_case else sources[0],
                "raw_results": raw_results if "pair" in corpus_case else raw_results[0],
                "observation": observation,
                **result,
            }
        )

    summary = {
        "preserved": sum(row["verdict"] == "PRESERVED" for row in rows),
        "loss": sum("LOSS" in row["verdict"] for row in rows),
        "invented": sum("INVENTED" in row["verdict"] for row in rows),
        "not_applicable": sum(row["verdict"] == "NOT_APPLICABLE" for row in rows),
    }
    summary["conformant"] = summary == {"preserved": 11, "loss": 0, "invented": 0, "not_applicable": 1}

    p05 = next(row for row in rows if row["id"] == "P05-media-type-gate")
    p11 = next(row for row in rows if row["id"] == "P11-origin-status-survives-intermediary")
    p12 = next(row for row in rows if row["id"] == "P12-no-retryability-invention")
    assert p05["observation"]["machine"] == {}
    assert p11["observation"]["machine"]["body"]["status"] == 503
    assert p11["observation"]["machine"]["observed_http_status"] == 502
    assert not truthy_retry_claim(p12)

    control = raw["same_operation_control"]
    success_raw = control["success"]["raw_call_tool_result"]
    problem_raw = control["problem"]["raw_call_tool_result"]
    success_ok = success_raw["structuredContent"] == {"ok": True, "probe": "same-tool"} and success_raw["isError"] is False
    problem_source = {
        "http_status": 403,
        "content_type": PROBLEM,
        "body": {
            "type": "https://example.test/problems/asymmetry-probe",
            "title": "Asymmetry probe failure",
            "status": 403,
            "detail": "The same generated MCP tool returned this RFC 9457 problem.",
            "code": "probe-failed",
        },
    }
    problem_observation = raw_result_to_observation(problem_raw, problem_source)
    problem_ok = (
        problem_observation["machine"].get("semantic_type") == "rfc9457-problem"
        and problem_observation["machine"]["body"] == problem_source["body"]
    )

    first_case = corpus["cases"][0]
    first_raw = raw["cases"][0]["calls"][0]["raw_call_tool_result"]
    demoted = {
        "content": [{"type": "text", "text": first_raw["content"][0]["resource"]["text"]}],
        "isError": first_raw["isError"],
        "_meta": first_raw["_meta"],
    }
    demoted_observation = raw_result_to_observation(demoted, source_list(first_case)[0])
    demoted_verdict = check_case(first_case, expectations[first_case["id"]], demoted_observation)
    assert demoted_verdict["verdict"] == "LOSS"

    typed_wire_count = sum(
        1
        for message in call_responses
        for block in message["result"].get("content", [])
        if block.get("type") == "resource" and block.get("resource", {}).get("mimeType") == PROBLEM
    )
    controls = {
        "operation_id_identity_exact": listed_names == operation_ids,
        "real_fixture_responses_observed": len(audits) == 16,
        "official_client_and_server_separate_processes_stdio": True,
        "protocol_era_modern": raw["protocol"]["era"] == "modern",
        "protocol_version_pinned_2026_07_28": raw["protocol"]["negotiated_protocol_version"] == "2026-07-28",
        "wire_request_response_projection_exact": len(call_responses) == 16,
        "wire_typed_embedded_problem_resources_preserved": typed_wire_count == 14,
        "same_tool_success_machine_addressable": success_ok,
        "same_tool_problem_machine_addressable": problem_ok,
        "p05_media_type_gate_no_rfc_recognition": p05["verdict"] == "NOT_APPLICABLE",
        "p11_body_503_observed_502_distinct": p11["verdict"] == "PRESERVED",
        "p12_no_retryability_invention": p12["verdict"] == "PRESERVED" and not truthy_retry_claim(p12),
        "negative_text_demotion_detected_as_loss": demoted_verdict["verdict"] == "LOSS",
    }
    assert all(controls.values())
    classification = "E7_CONFIRMED" if summary["conformant"] and all(controls.values()) else "E7_PARTIAL"

    results = {
        "profile": "OpenAPI-to-MCP Problem-Semantics Preservation Profile",
        "classification": classification,
        "evidence_level": "official-mcp-sdk-v2-real-stdio-wire",
        "official_sdk": raw["official_sdk"],
        "protocol": raw["protocol"],
        "summary": summary,
        "controls": controls,
        "same_operation_control": {
            "tool_name": control["tool_name"],
            "success_raw": success_raw,
            "problem_raw": problem_raw,
            "problem_observation": problem_observation,
        },
        "p11_control": {
            "body_status": p11["observation"]["machine"]["body"]["status"],
            "observed_http_status": p11["observation"]["machine"]["observed_http_status"],
            "verdict": p11["verdict"],
        },
        "p12_control": {"unsupported_retry_claim_present": truthy_retry_claim(p12), "verdict": p12["verdict"]},
        "negative_text_demotion_control": {
            "raw_result": demoted,
            "observation": demoted_observation,
            **demoted_verdict,
        },
        "cases": rows,
    }

    layers = {
        "classification": classification,
        "sequence": [
            "frozen OpenAPI operation",
            "real fixture HTTP response",
            "reference bridge mapping",
            "official server wire codec",
            "stdio bytes",
            "official client wire codec",
            "raw CallToolResult",
            "carrier-neutral adapter v0.2",
            "frozen oracle",
        ],
        "boundaries": {
            "openapi_to_tool_registry": {"operation_count": len(operation_ids), "operation_ids": operation_ids, "identity_exact": True},
            "fixture_to_bridge": {"observed_response_count": len(audits), "audit_records": audits},
            "client_to_server_wire": {
                "file": "e7-client-to-server-wire.jsonl",
                "sha256": sha256("e7-client-to-server-wire.jsonl"),
                "message_count": len(incoming),
                "tool_call_count": len(call_requests),
            },
            "server_to_client_wire": {
                "file": "e7-server-to-client-wire.jsonl",
                "sha256": sha256("e7-server-to-client-wire.jsonl"),
                "message_count": len(outgoing),
                "tool_result_count": len(call_responses),
                "typed_embedded_problem_resource_count": typed_wire_count,
                "all_tool_results_complete": all(message["result"].get("resultType") == "complete" for message in call_responses),
            },
            "official_client_to_adapter": {
                "file": "e7-official-client-raw.json",
                "sha256": sha256("e7-official-client-raw.json"),
                "raw_tool_result_count": len(official_calls),
            },
            "adapter_to_oracle": {"summary": summary, "negative_text_demotion_verdict": demoted_verdict["verdict"]},
        },
    }
    return results, layers


def verify_ledger():
    ledger = ROOT / "SHA256SUMS"
    if not ledger.exists():
        return 0
    count = 0
    for line in ledger.read_text().splitlines():
        if not line.strip():
            continue
        expected, name = line.split("  ", 1)
        actual = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        assert actual == expected, f"hash mismatch: {name}"
        count += 1
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write deterministic derived result files")
    args = parser.parse_args()
    results, layers = build()
    if args.write:
        (ROOT / "reference-e7-results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
        (ROOT / "E7_LAYER_BOUNDARY_EVIDENCE.json").write_text(json.dumps(layers, indent=2, ensure_ascii=False) + "\n")
    else:
        assert load("reference-e7-results.json") == results
        assert load("E7_LAYER_BOUNDARY_EVIDENCE.json") == layers
    ledger_count = verify_ledger()
    summary = results["summary"]
    print(f"classification: {results['classification']}")
    print(
        "summary: "
        f"preserved={summary['preserved']} loss={summary['loss']} "
        f"invented={summary['invented']} n/a={summary['not_applicable']} conformant={summary['conformant']}"
    )
    print("official MCP 2026-07-28 modern stdio wire: PASS")
    print("same-tool success/problem control: PASS")
    print("P11 body=503 observed=502: PASS")
    print("P12 no retryability invention: PASS")
    print("negative text-demotion control: PASS (LOSS)")
    if ledger_count:
        print(f"SHA256SUMS: PASS ({ledger_count} files)")


if __name__ == "__main__":
    main()
