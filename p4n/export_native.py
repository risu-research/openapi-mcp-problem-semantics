"""P4-N derivative ONLY: original third-party YAML VCR + RISU-recorded MCP wire
to native HAR 1.2 + JSON-RPC JSONL, without inventing a causal witness.

The rendered HAR is a *format conversion*, NOT a capture from the owner's
browser or a third-party observed HAR file. Pairs explicitly declare our
known replay experimental linkage; original upstream source is pinned.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import yaml

ROOT=Path(__file__).resolve().parent
PINS=json.loads((ROOT/"FROZEN_SOURCES.json").read_text())

def sha(b):return hashlib.sha256(b).hexdigest()
def gitblob(b):return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()

def convert(name,external,out):
    c=PINS["cases"][name]
    original=(external/c["original_relative"]).read_bytes()
    assert gitblob(original)==c["git_blob_sha1"]
    v=yaml.safe_load(original)
    exchanges=[x for x in v["interactions"] if x["request"]["method"]=="GET"]
    assert len(exchanges)==1
    x=exchanges[0]
    assert x["response"]["status"]["code"]==c["upstream_http_status"]
    assert c["expected_request_path"] in x["request"]["uri"]
    raw=x["response"]["body"]["string"]
    body=json.loads(raw)
    assert body["result"]["statusCode"]==c["application_status_code"]
    captured=out/name/"observed_stdio_wire.jsonl"
    assert captured.is_file()
    wire=captured.read_bytes()
    requests=[json.loads(s) for s in wire.splitlines()]
    assert requests[-2]["method"]=="tools/call"
    assert requests[-2]["params"]["name"]=="get_jpo_progress"
    assert requests[-2]["params"]["arguments"]=={"application_number":c["application_number"],"ip_type":c["ip_type"]}
    assert requests[-1]["id"]==requests[-2]["id"]==3
    assert "result" in requests[-1]

    # Preserve status and exact original response JSON text. Strip sensitive
    # headers; source cassette SHA ensures this remains independently checkable.
    har={"log":{"version":"1.2","creator":{"name":"RISU derivative converter from pinned original VCR","version":"P4-N"},
        "entries":[{"startedDateTime":"2026-11-06T00:00:00.000Z","time":0,
        "request":{"method":"GET","url":x["request"]["uri"],"httpVersion":"HTTP/1.1","headers":[],"queryString":[],"cookies":[],"headersSize":-1,"bodySize":0},
        "response":{"status":x["response"]["status"]["code"],"statusText":"OK",
        "httpVersion":"HTTP/1.1","headers":[{"name":"Content-Type","value":"application/json"}],
        "cookies":[],"content":{"mimeType":"application/json","text":raw},"redirectURL":"","headersSize":-1,"bodySize":len(raw.encode())},
        "cache":{},"timings":{"send":0,"wait":0,"receive":0}}]}}
    pair={"schema":"risu-explicit-capture-pairing-v1","pairs":[{"case_id":"JPO_"+name,
        "target":"patent_client_agents_original_vcr_replay","http_entry":0,"mcp_call_id":3,"tool":"get_jpo_progress"}]}
    folder=out/"risu_native_inputs"/name
    folder.mkdir(parents=True,exist_ok=True)
    (folder/"capture.har").write_text(json.dumps(har,ensure_ascii=False,separators=(",",":"))+"\n")
    (folder/"mcp.jsonl").write_bytes(wire)
    (folder/"pairs.json").write_text(json.dumps(pair,separators=(",",":"))+"\n")
    provenance={"format":"DERIVED_FROM_THIRD_PARTY_ORIGINAL_VCR_AND_RISU_GENERATED_NEW_MCP_STDIO_WIRE",
        "not_an_independent_original_dual_boundary_capture":True,"not_a_causally_signed_witness":True,
        "original_third_party_cassette_git_sha1":c["git_blob_sha1"],
        "original_cassette_sha256":sha(original),
        "RISU_generated_stdio_mcp_sha256":sha(wire),
        "derived_har_sha256":sha((folder/"capture.har").read_bytes()),
        "api_internal_status_code":c["application_status_code"],"transport_http_status":c["upstream_http_status"]}
    (folder/"DERIVATION_PROVENANCE.json").write_text(json.dumps(provenance,sort_keys=True,indent=2)+"\n")
    print("P4N_RISU_NATIVE_DERIVATIVE_READY",name,
          json.dumps({"http_status":provenance["transport_http_status"],
            "api_status":provenance["api_internal_status_code"],
            "upstream_git_blob":c["git_blob_sha1"],"mcp_sha256":provenance["RISU_generated_stdio_mcp_sha256"]}),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--external",type=Path,required=True)
    p.add_argument("--out",type=Path,default=ROOT/"results")
    a=p.parse_args()
    for c in ("normal","logical_not_found"):convert(c,a.external,a.out)
