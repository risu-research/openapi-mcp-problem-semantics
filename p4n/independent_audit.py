"""P4-N independent raw MCP stdio wire and external VCR source audit.

Does not import RISU Probe comparison logic or the replay driver; checks bytes,
original pinned third-party source, actual message order and the replay status.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import yaml

ROOT=Path(__file__).resolve().parent
FROZEN=json.loads((ROOT/"FROZEN_SOURCES.json").read_text())

def blob(data):
    return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()

def audit_case(case,root,external,check_bytes=True):
    cfg=FROZEN["cases"][case]
    report=json.loads((root/case/"case_report.json").read_text())
    wire=(root/case/"observed_stdio_wire.jsonl").read_bytes()
    assert len(wire)<2_000_000 and len(wire)>1000
    if check_bytes:
        original=(external/cfg["original_relative"]).read_bytes()
        assert blob(original)==cfg["git_blob_sha1"]
        v=yaml.safe_load(original)
        auth=[x for x in v["interactions"] if x["request"]["method"]=="POST"]
        upstream=[x for x in v["interactions"] if x["request"]["method"]=="GET"]
        assert len(auth)==len(upstream)==1
        assert auth[0]["response"]["status"]["code"]==200
        rec=upstream[0]
        assert rec["response"]["status"]["code"]==cfg["upstream_http_status"]
        assert cfg["expected_request_path"] in rec["request"]["uri"]
        assert json.loads(rec["response"]["body"]["string"])["result"]["statusCode"]==cfg["application_status_code"]
        assert report["original_cassette_sha256"]==hashlib.sha256(original).hexdigest()
        assert report["original_http_get_body_sha256"]==hashlib.sha256(rec["response"]["body"]["string"].encode()).hexdigest()
    assert report["case"]==case
    assert report["original_cassette_git_blob_sha1"]==cfg["git_blob_sha1"]
    assert report["original_http_status"]==cfg["upstream_http_status"]==200
    assert report["original_application_status_code"]==cfg["application_status_code"]
    assert report["original_vcr_interactions_replayed"]==2
    assert report["run_category"]=="RISU_REPLAY_OF_THIRD_PARTY_ORIGINAL_HTTP_CAPTURE"
    assert report["actual_original_third_party_fastmcp_subserver"] is True
    assert report["actual_mcp_wire_transport"]=="stdio JSON-RPC over subprocess stdin/stdout"
    assert report["external_independently_recorded_same_call_mcp_wire"] is False
    assert report["field_fpr"] is None
    assert report["mcp_call_raw_wire_sha256"]==hashlib.sha256(wire).hexdigest()
    assert report["jsonrpc_frames_recorded"]==7
    assert wire.endswith(b"\n")
    msgs=[json.loads(line) for line in wire.splitlines()]
    assert len(msgs)==7
    assert all(x.get("jsonrpc")=="2.0" for x in msgs)
    assert msgs[0].get("method")=="initialize" and msgs[0]["id"]==1
    assert msgs[1].get("id")==1 and "result" in msgs[1]
    assert msgs[2].get("method")=="notifications/initialized" and "id" not in msgs[2]
    assert msgs[3].get("method")=="tools/list" and msgs[3]["id"]==2
    assert msgs[4].get("id")==2 and "result" in msgs[4]
    assert any(t.get("name")=="get_jpo_progress" for t in msgs[4]["result"]["tools"])
    assert msgs[5].get("method")=="tools/call" and msgs[5]["id"]==3
    assert msgs[5]["params"]["name"]=="get_jpo_progress"
    assert msgs[5]["params"]["arguments"]=={"application_number":cfg["application_number"],"ip_type":cfg["ip_type"]}
    assert msgs[6].get("id")==3 and "result" in msgs[6] and "error" not in msgs[6]
    result=msgs[6]["result"]
    assert result==report["mcp_call_result"]
    assert isinstance(result.get("content"),list) and result["content"]
    assert report["mcp_call_isError"]==result.get("isError",False)
    assert report["mcp_call_has_structuredContent"]==("structuredContent" in result)
    assert report["mcp_call_content_types"]==[c.get("type") for c in result["content"]]
    canonical=json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    assert hashlib.sha256(canonical).hexdigest()==report["mcp_call_result_json_sha256"]
    # Semantic checks are grounded in the *third-party tool's actual wire*.
    # Status 107 is explicitly a successful HTTP 200 empty lookup; it must
    # NOT be treated as a generic MCP isError loss.
    structured=result.get("structuredContent")
    assert isinstance(structured,dict)
    assert result.get("isError",False) is False
    if case=="normal":
        assert len(structured.get("items",[]))==1
        assert structured["items"][0].get("application_number")==cfg["application_number"]
        assert structured.get("not_found")==[]
    elif case=="logical_not_found":
        assert structured.get("items")==[]
        assert structured.get("not_found")==[cfg["application_number"]]
        assert "no data" in structured.get("summary","").lower()
    # Raw protocol must not accidentally echo OAuth credentials or auth headers.
    assert b"REDACTED_ACCESS_TOKEN" not in wire
    assert b"REDACTED_PASSWORD" not in wire
    assert b"Authorization:" not in wire
    assert report["external_original_commit"]==FROZEN["original_commit"]
    assert report["external_original_repo"]==FROZEN["original_repo"]
    return {"case":case,
        "real_stdio_wire_frames":len(msgs),
        "http_status":report["original_http_status"],
        "api_status":report["original_application_status_code"],
        "mcp_isError":result.get("isError",False),
        "structured":("structuredContent" in result),
        "wire_sha256":hashlib.sha256(wire).hexdigest()}

def run_audit(out,external,check_bytes=True):
    assert not any(x.get("originally_independently_recorded_mcp_wire",False) for x in FROZEN["cases"].values())
    rs=[audit_case(c,out,external,check_bytes) for c in ("normal","logical_not_found")]
    summary=json.loads((out/"summary.json").read_text())
    assert summary["schema"]=="risu-p4n-original-vcr-to-actual-mcp-stdio-replay-metrics-v1"
    assert summary["real_third_party_original_http_cassettes"]==2
    assert summary["risu_replayed_actual_mcp_stdio_wires"]==2
    assert summary["original_independently_recorded_complete_causal_pairs"]==0
    assert summary["independent_field_false_positive_rate"] is None
    assert summary["external_original_commit"]==FROZEN["original_commit"]
    assert len(summary["results"])==2
    for i,r in enumerate(rs):
        s=summary["results"][i]
        assert s["case"]==r["case"] and s["mcp_call_raw_wire_sha256"]==r["wire_sha256"]
    return rs

def check_claim_mutations(out,external):
    report=out/"normal"/"case_report.json"
    original=report.read_bytes()
    try:
        edits={
            "invent_independent_wire":lambda x:x.update(external_independently_recorded_same_call_mcp_wire=True),
            "invent_HTTP_404":lambda x:x.update(original_http_status=404),
            "fabricate_isError":lambda x:x.update(mcp_call_isError=not x["mcp_call_isError"]),
            "invent_source_blob":lambda x:x.update(original_cassette_git_blob_sha1="0"*40),
            "false_frame_count":lambda x:x.update(jsonrpc_frames_recorded=6),
            "fake_wire_hash":lambda x:x.update(mcp_call_raw_wire_sha256="0"*64),
            "fake_result":lambda x:x.update(mcp_call_result={"content":[]}),
            "invent_FPR":lambda x:x.update(field_fpr=0.0)
        }
        caught=[]
        for name,fn in edits.items():
            fake=json.loads(original)
            fn(fake)
            report.write_text(json.dumps(fake))
            try:audit_case("normal",out,external,check_bytes=False)
            except (AssertionError,KeyError,TypeError,ValueError):caught.append(name)
            else:raise AssertionError("P4N_UNDETECTED_FALSE_CLAIM "+name)
        assert len(caught)==len(edits)
        return caught
    finally:
        report.write_bytes(original)

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",type=Path,default=ROOT/"results")
    ap.add_argument("--external",type=Path,required=True)
    args=ap.parse_args()
    external=args.external.resolve()
    actual=subprocess.check_output(["git","-C",str(external),"rev-parse","HEAD"],text=True).strip()
    assert actual==FROZEN["original_commit"]
    audited=run_audit(args.out,external)
    controls=check_claim_mutations(args.out,external)
    assert len(controls)==8
    receipt={"schema":"risu-p4n-raw-stdio-mcp-original-vcr-independent-audit-v1",
     "status":"PASS","original_upstream_cassettes_git_pinned":2,
     "actual_replayed_raw_mcp_stdio_wires":2,
     "independent_original_both_boundary_proof":0,
     "field_fpr":None,"per_case":audited,"caught_false_claims":controls}
    (args.out/"independent_audit.json").write_text(json.dumps(receipt,indent=2,ensure_ascii=False,sort_keys=True)+"\n")
    print("P4N_INDEPENDENT_RAW_WIRE_AUDIT_PASS",json.dumps(receipt,sort_keys=True),flush=True)
