"""Only synthetic fixture definitions reused by P4-P's adversarial tests.

Not a real third-party capture; real JPO recorded-source tests run separately.
"""
from __future__ import annotations
import json
from pathlib import Path

HERE=Path(__file__).resolve().parents[1]
BASE_BODY={"result":{"statusCode":"100","errorMessage":"","remainAccessCount":"799","data":{
    "applicationNumber":"2020015234","designArticle":"example article","designClass":"E2112",
    "filingDate":"20200624","registrationNumber":"1680736",
    "applicantAttorney":[{"applicantAttorneyCd":"519372777","name":"Example"}],
    "bibliographyInformation":[{"number":"2020015234"}]}}}
EMPTY_BODY={"result":{"statusCode":"107","errorMessage":"Record missing","remainAccessCount":"786","data":{}}}
FOUND={"summary":"JPO application 2020015234", "items":[{
    "application_number":"2020015234", "design_article":"example article", "design_class":"E2112",
    "filing_date":"20200624", "registration_number":"1680736",
    "applicant_attorney":[{"applicant_attorney_cd":"519372777","name":"Example"}],
    "bibliography_information":[{"number":"2020015234"}]}], "not_found":[]}
EMPTY={"summary":"JPO application 9999999999 — no data on file.","items":[],"not_found":["9999999999"]}
RULES=json.loads((HERE/"fixtures"/"jpo_observed_mapping.json").read_text())

def make_case(root):
    entries=[];wire=[];pairs=[]
    for i,(case,number,path,body,target) in enumerate([
        ("JPO_normal","2020015234","design",BASE_BODY,FOUND),
        ("JPO_logical_not_found","9999999999","patent",EMPTY_BODY,EMPTY),
    ]):
        entries.append({"request":{"method":"GET","url":f"https://ip-data.jpo.go.jp/api/{path}/v1/app_progress/{number}","headers":[]},
            "response":{"status":200,"headers":[{"name":"Content-Type","value":"application/json"}],
                        "content":{"mimeType":"application/json","text":json.dumps(body)}}})
        rid=i+3
        wire.append({"jsonrpc":"2.0","id":rid,"method":"tools/call","params":{"name":"get_jpo_progress",
          "arguments":{"application_number":number,"ip_type":path}}})
        wire.append({"jsonrpc":"2.0","id":rid,"result":{"isError":False,"structuredContent":target,
            "content":[{"type":"text","text":json.dumps(target)}]}})
        pairs.append({"case_id":case,"target":"jpo_synthetic","http_entry":i,"mcp_call_id":rid,"tool":"get_jpo_progress"})
    (root/"capture.har").write_text(json.dumps({"log":{"version":"1.2","entries":entries}}))
    (root/"mcp.jsonl").write_text("".join(json.dumps(x)+"\n" for x in wire))
    (root/"pairs.json").write_text(json.dumps({"schema":"risu-explicit-capture-pairing-v1","pairs":pairs}))
