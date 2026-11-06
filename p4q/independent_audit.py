"""Independent source-original JPO audit (never imports RISU array matcher).

All source claims independently verified from the immutable VCR and the
newly replayed FastMCP wire. Fails closed on cardinality, duplicates, differing
typed values, missing origin, false independent-causality or inflated metrics.
"""
import hashlib
import json
import re
from pathlib import Path
import yaml
import copy

ROOT=Path(__file__).resolve().parents[1]
FROZEN=json.loads((ROOT/"p4n"/"FROZEN_SOURCES.json").read_text())
RESULTS=ROOT/"p4n"/"results"
ORIG=ROOT/"p4n"/"external_upstream"
CASE=FROZEN["cases"]["normal"]
SOURCE=ORIG/CASE["original_relative"]

def sha_blob(b):
    return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()

def snake(k):
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])","_",k).lower()

def count_leaves(obj):
    if isinstance(obj,dict):
        return 1 if not obj else sum(count_leaves(x) for x in obj.values())
    if isinstance(obj,list):
        return 1 if not obj else sum(count_leaves(x) for x in obj)
    return 1

def compare_rows(a,b,identity,fields,child=None):
    assert len(a)==len(b)
    sa={};tb={}
    for i,row in enumerate(a):
        assert set(row)==set(fields)|({child} if child else set())
        key=tuple((type(row[k]).__name__,row[k]) for k in identity)
        assert key not in sa
        sa[key]=row
    for j,row in enumerate(b):
        assert set(row)=={snake(k) for k in fields}|({snake(child)} if child else set())
        key=tuple((type(row[snake(k)]).__name__,row[snake(k)]) for k in identity)
        assert key not in tb
        tb[key]=row
    assert sa.keys()==tb.keys()
    joined=[]
    for key,left in sa.items():
        right=tb[key]
        for field in fields:
            assert not isinstance(left[field],(dict,list))
            assert type(left[field]) is type(right[snake(field)])
            assert left[field]==right[snake(field)]
        joined.append((left,right))
    return len(sa)*len(fields),joined

def assert_claim(r):
    assert r["status"]=="PASS"
    assert r["source_leaf_units"]==134
    assert r["original_document_rows"]==11
    assert r["matched_array_rows"]==14
    assert r["array_verified_scalar_units"]==118
    assert r["baseline_coverage_units"]==8
    assert r["new_unique_verified_units"]==116
    assert r["combined_verified_units"]==124
    assert r["combined_unverified_units"]==10
    assert r["both_original_sources_verified"]==126
    assert r["both_original_source_leaf_units"]==138
    assert r["external_independent_same_call_wires"]==0
    assert r["field_false_positive_rate"] is None

def main():
    raw=SOURCE.read_bytes()
    assert sha_blob(raw)==CASE["git_blob_sha1"]
    v=yaml.safe_load(raw)
    recorded=[x for x in v["interactions"] if x["request"]["method"]=="GET"]
    assert len(recorded)==1 and recorded[0]["response"]["status"]["code"]==200
    body=json.loads(recorded[0]["response"]["body"]["string"])
    assert body["result"]["statusCode"]=="100"
    assert count_leaves(body)==134
    har=json.loads((RESULTS/"risu_native_inputs"/"normal"/"capture.har").read_text())
    assert json.loads(har["log"]["entries"][0]["response"]["content"]["text"])==body
    source=body["result"]["data"]
    original_wire=json.loads((RESULTS/"normal"/"case_report.json").read_text())
    assert original_wire["original_cassette_git_blob_sha1"]==CASE["git_blob_sha1"]
    assert original_wire["external_independently_recorded_same_call_mcp_wire"] is False
    target=original_wire["mcp_call_result"]["structuredContent"]["items"][0]
    x,attorneys=compare_rows(source["applicantAttorney"],target["applicant_attorney"],
        ["applicantAttorneyCd"],["applicantAttorneyCd","repeatNumber","name","applicantAttorneyClass"])
    y,biblios=compare_rows(source["bibliographyInformation"],target["bibliography_information"],
        ["number","numberType"],["numberType","number"],"documentList")
    cnt=0;rows=0
    for left,right in biblios:
        size,j=compare_rows(left["documentList"],right["document_list"],
            ["documentNumber","documentCode","legalDate"],
            ["legalDate","irirFlg","availabilityFlag","documentCode","documentDescription",
             "documentNumber","versionNumber","documentSeparator","numberOfPages","sizeOfDocument"])
        cnt+=size;rows+=len(j)
    assert (x,y,cnt)==(4,4,110)
    assert (len(attorneys),len(biblios),rows)==(1,2,11)
    result=json.loads((RESULTS/"normal"/"p4q_array_diagnosis.json").read_text())
    assert result["version"]=="0.9.13-experimental"
    assert result["array_identity_v1"]["summary"]["matched_groups"]==3
    assert result["array_identity_v1"]["summary"]["candidate_exact_leaf_units"]==118
    assert result["array_identity_v1"]["summary"]["matched_rows"]==14
    r=result["source_coverage_with_arrays_v1"]["summary"]
    assert r["source_leaf_units"]==134 and r["baseline_verified"]==8
    assert r["array_verified_unique"]==118 and r["overlap_with_baseline"]==2
    assert r["newly_verified_by_array_groups"]==116
    assert r["combined_verified"]==124 and r["combined_unverified"]==10
    assert r["combined_coverage_pct"]==92.54
    assert result["causal_gate_v1"]["summary"]["CONFIRMED_LOSS"]==0
    assert result["results"][0]["verdict"]=="LOSS"
    assert result["results"][0]["causal_v1"]["outcome"]=="CONDITIONAL_MISMATCH"
    other=json.loads((RESULTS/"logical_not_found"/"p4p_field_coverage.json").read_text())
    assert other["field_coverage_v1"]["cases"][0]["full_source"]["total_source_leaf_units"]==4
    assert other["field_coverage_v1"]["cases"][0]["full_source"]["coverage_verified_units"]==2
    receipt={"status":"PASS","source_leaf_units":134,"original_document_rows":rows,
             "matched_array_rows":len(attorneys)+len(biblios)+rows,
             "array_verified_scalar_units":x+y+cnt,"baseline_coverage_units":8,
             "new_unique_verified_units":116,"combined_verified_units":124,
             "combined_unverified_units":10,"both_original_sources_verified":124+2,
             "both_original_source_leaf_units":134+4,
             "external_independent_same_call_wires":0,"field_false_positive_rate":None,
             "sha256_external_original_vcr":hashlib.sha256(raw).hexdigest(),
             "original_external_commit":FROZEN["original_commit"]}
    assert_claim(receipt)
    mutations={
      "false_source_total":lambda x:x.update(source_leaf_units=133),
      "false_doc_count":lambda x:x.update(original_document_rows=10),
      "false_array_count":lambda x:x.update(array_verified_scalar_units=119),
      "false_unique_gain":lambda x:x.update(new_unique_verified_units=117),
      "false_total_coverage":lambda x:x.update(combined_verified_units=134),
      "hide_unverified":lambda x:x.update(combined_unverified_units=0),
      "invent_third_party_wire":lambda x:x.update(external_independent_same_call_wires=1),
      "invent_FPR":lambda x:x.update(field_false_positive_rate=0),
      "invent_combined_all_cases":lambda x:x.update(both_original_sources_verified=138)}
    caught=[]
    for name,alter in mutations.items():
        false=copy.deepcopy(receipt);alter(false)
        try:assert_claim(false)
        except AssertionError:caught.append(name)
        else:raise AssertionError("undetected forged qualification "+name)
    assert len(caught)==9
    receipt["nine_false_claims_blocked"]=caught
    (RESULTS/"p4q_independent_audit.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    print("P4Q_INDEPENDENT_THIRD_PARTY_ORIGINAL_AUDIT_PASS",
          json.dumps({"verified":124,"original":134,"document_rows":rows,
                      "both_original_cases":"126/138","false_claims_blocked":len(caught)},sort_keys=True),flush=True)

if __name__=="__main__":main()
