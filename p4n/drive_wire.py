"""P4-N actual MCP JSON-RPC stdio wire driver, tied to original external HTTP VCR.

This is a RISU-authored REPLAY under pinned third-party source, never an
independent vendor-side trace. The raw wire is captured from stdout bytes,
not reconstructed from ClientSession's model_dump; the HTTP source bytes are
from a third party's immutable Git original redacted cassette.
"""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import yaml

ROOT=Path(__file__).resolve().parent
FROZEN=json.loads((ROOT/"FROZEN_SOURCES.json").read_text())

def blob(data):
    return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()

async def read_frame(process,seq,timeout=55):
    line=await asyncio.wait_for(process.stdout.readline(),timeout=timeout)
    if not line:
        error=(await asyncio.wait_for(process.stderr.read(),timeout=10)).decode("utf-8","replace")
        raise RuntimeError("P4N_EARLY_STDIO_SERVER_EXIT "+str(seq)+" STDERR "+error[-4500:])
    assert len(line)<2_000_000,("INVALID_STDIO_WIRE_FRAME",seq)
    value=json.loads(line)
    assert isinstance(value,dict) and value.get("jsonrpc")=="2.0"
    return line,value

async def call(process,frames,payload):
    raw=json.dumps(payload,separators=(",",":"),ensure_ascii=False).encode()+b"\n"
    process.stdin.write(raw)
    await asyncio.wait_for(process.stdin.drain(),timeout=30)
    frames.append({"direction":"client_to_server","wire_utf8":raw.decode("utf-8")})
    if "id" not in payload:return None
    line,response=await read_frame(process,payload["id"])
    frames.append({"direction":"server_to_client","wire_utf8":line.decode("utf-8")})
    assert response.get("id")==payload["id"],("MCP_WRONG_JSONRPC_ID",payload["id"],response.get("id"))
    assert "error" not in response,("PROTOCOL_ERROR",response.get("error"))
    assert isinstance(response.get("result"),dict)
    return response["result"]

async def run_case(case,repo,source,output):
    config=FROZEN["cases"][case]
    orig=source/config["original_relative"]
    assert orig.is_file()
    assert blob(orig.read_bytes())==config["git_blob_sha1"]
    # Isolate original corpus: VCR must not modify pinned source file.
    with tempfile.TemporaryDirectory(prefix="p4n-original-cassette-") as td:
        capsule=Path(td)/"original.yaml"
        shutil.copyfile(orig,capsule)
        before=hashlib.sha256(capsule.read_bytes()).hexdigest()
        env={**os.environ,
            "P4N_EXTERNAL_PROJECT":str(repo),
            "P4N_ORIGINAL_CASSETTE_COPY":str(capsule),
            "JPO_API_USERNAME":"REDACTED_USERNAME",
            "JPO_API_PASSWORD":"REDACTED_PASSWORD",
            "P4N_REPLAY_ONLY":"1",
            "PYTHONDONTWRITEBYTECODE":"1",
            "VCR_RECORD_MODE":"none",
            "FASTMCP_CHECK_FOR_UPDATES":"off",
            "FASTMCP_SHOW_SERVER_BANNER":"false"}
        cmd=[sys.executable,"-u",str(ROOT/"replay_original_jpo_subserver.py")]
        p=await asyncio.create_subprocess_exec(*cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(repo),
            env=env)
        frames=[]
        try:
            result=await call(p,frames,{"jsonrpc":"2.0","id":1,"method":"initialize",
                  "params":{"protocolVersion":"2025-06-18",
                  "capabilities":{},"clientInfo":{"name":"risu-p4n-original-recording-replay","version":"0"}}})
            assert result.get("protocolVersion")
            await call(p,frames,{"jsonrpc":"2.0","method":"notifications/initialized"})
            listed=await call(p,frames,{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}})
            names=[t["name"] for t in listed.get("tools",[])]
            assert "get_jpo_progress" in names,("THIRD_PARTY_ORIGINAL_TOOL_NOT_EXPOSED",names[:40])
            tool=await call(p,frames,{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{
                "name":"get_jpo_progress",
                "arguments":{"application_number":config["application_number"],"ip_type":config["ip_type"]}}})
        finally:
            if p.stdin and not p.stdin.is_closing():
                p.stdin.close()
            try:
                await asyncio.wait_for(p.wait(),timeout=28)
            except asyncio.TimeoutError:
                p.kill()
                await p.wait()
        stderr=(await p.stderr.read()).decode("utf-8","replace")
        if p.returncode!=0:
            raise RuntimeError("ORIGINAL_SERVER_NONZERO: "+str(p.returncode)+"; "+stderr[-5500:])
        assert "P4N_REPLAY_MODE_ONLY" in stderr
        assert "P4N_ORIGINAL_HTTP_CASSETTE_PLAY_COUNT 2" in stderr,stderr[-2200:]
        assert hashlib.sha256(capsule.read_bytes()).hexdigest()==before
        assert blob(orig.read_bytes())==config["git_blob_sha1"]
    original=yaml.safe_load(orig.read_text(encoding="utf-8-sig"))
    up=[x for x in original["interactions"] if x["request"]["method"]=="GET"]
    assert len(up)==1
    resp=up[0]["response"];parsed=json.loads(resp["body"]["string"])
    assert resp["status"]["code"]==200
    assert parsed["result"]["statusCode"]==config["application_status_code"]
    assert "error" not in tool
    assert isinstance(tool.get("content"),list) and len(tool["content"])>0
    captured_json_bytes=("".join(x["wire_utf8"] for x in frames)).encode("utf-8")
    directory=output/case;directory.mkdir(parents=True,exist_ok=True)
    raw=directory/"observed_stdio_wire.jsonl"
    raw.write_bytes(captured_json_bytes)
    report={
     "case":case,
     "schema":"risu-p4n-original-external-vcr-replayed-through-real-third-party-mcp-stdio-v1",
     "external_original_repo":FROZEN["original_repo"],
     "external_original_commit":FROZEN["original_commit"],
     "original_cassette_git_blob_sha1":config["git_blob_sha1"],
     "original_cassette_sha256":hashlib.sha256(orig.read_bytes()).hexdigest(),
     "original_http_status":resp["status"]["code"],
     "original_application_status_code":parsed["result"]["statusCode"],
     "original_http_path":config["expected_request_path"],
     "original_http_get_body_sha256":hashlib.sha256(resp["body"]["string"].encode("utf-8")).hexdigest(),
     "original_vcr_interactions_replayed":2,
     "run_category":"RISU_REPLAY_OF_THIRD_PARTY_ORIGINAL_HTTP_CAPTURE",
     "actual_original_third_party_fastmcp_subserver":True,
     "actual_mcp_wire_transport":"stdio JSON-RPC over subprocess stdin/stdout",
     "jsonrpc_frames_recorded":len(frames),
     "mcp_tools_list_includes_target":True,
     "mcp_call_isError":tool.get("isError",False),
     "mcp_call_has_structuredContent":"structuredContent" in tool,
     "mcp_call_content_types":[x.get("type") for x in tool["content"]],
     "mcp_call_raw_wire_sha256":hashlib.sha256(captured_json_bytes).hexdigest(),
     "mcp_call_result_json_sha256":hashlib.sha256(json.dumps(tool,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
     "mcp_call_result":tool,
     "external_independently_recorded_same_call_mcp_wire":False,
     "field_fpr":None}
    (directory/"case_report.json").write_text(json.dumps(report,sort_keys=True,indent=2,ensure_ascii=False)+"\n")
    print("P4N_ORIGINAL_REPLAY_REAL_STDIO_MCP",case,json.dumps({k:report[k] for k in
        ("original_http_status","original_application_status_code","jsonrpc_frames_recorded",
         "mcp_call_isError","mcp_call_has_structuredContent","mcp_call_raw_wire_sha256")},sort_keys=True),flush=True)
    return report

async def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--external",type=Path,required=True)
    ap.add_argument("--out",type=Path,default=ROOT/"results")
    a=ap.parse_args()
    root=a.external.resolve()
    assert (root/".git").exists()
    sha=subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()
    assert sha==FROZEN["original_commit"],("THIRD_PARTY_COMMIT_DRIFT",sha)
    a.out.mkdir(parents=True,exist_ok=True)
    summaries=[]
    for case in ("normal","logical_not_found"):
        summaries.append(await run_case(case,root,root,a.out))
    summary={
      "schema":"risu-p4n-original-vcr-to-actual-mcp-stdio-replay-metrics-v1",
      "external_original_commit":sha,
      "results":[{k:r[k] for k in r if k!="mcp_call_result"} for r in summaries],
      "real_third_party_original_http_cassettes":2,
      "risu_replayed_actual_mcp_stdio_wires":len(summaries),
      "original_independently_recorded_complete_causal_pairs":0,
      "independent_field_false_positive_rate":None,
      "evidence_boundary":"RISU replay on pinned third-party code with recorded third-party HTTP original. MCP wire is generated in OUR new execution, not third-party archived wire."}
    (a.out/"summary.json").write_text(json.dumps(summary,sort_keys=True,indent=2,ensure_ascii=False)+"\n")
    assert summary["risu_replayed_actual_mcp_stdio_wires"]==2

if __name__=="__main__":
    asyncio.run(main())
