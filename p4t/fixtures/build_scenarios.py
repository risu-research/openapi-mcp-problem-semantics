"""Clearly synthetic upgrade; baseline shape follows recorded P4-S declared fields."""
import json
from pathlib import Path
p=Path(__file__).resolve().parent
base={"type":"object","required":["summary","items","provenance"],"properties":{
 "summary":{"type":"string"},"items":{"type":"array"},
 "provenance":{"type":"object","required":["source","retrieved_at","endpoint","verified"],"properties":{
   "source":{"type":"string"},"retrieved_at":{"type":"string"},"endpoint":{"type":"string"},"verified":{"type":"boolean"}}},
 "not_found":{"type":"boolean"}}}
new=json.loads(json.dumps(base))
new['properties']['items']['type']='string'
new['properties']['quota_remaining']={"type":"integer"}
new['required']=["summary","items","not_found","quota_remaining"]
policy_old={"format":"operator-demo-v1","rules":[
 {"id":"quota","source_path":"/result/remainAccessCount","condition":"always","importance":"HIGH","reason":"UI shows remaining calls","source":"operator"},
 {"id":"error","source_path":"/result/errorMessage","condition":"nonempty","importance":"MEDIUM","reason":"errors need visible message","source":"operator"}]}
policy_new={"format":"operator-demo-v1","rules":[
 {"id":"error","source_path":"/result/errorMessage","condition":"always","importance":"HIGH","reason":"all error texts visible","source":"operator-policy-revision"},
 {"id":"registration","source_path":"/data/registrationDate","condition":"always","importance":"HIGH","reason":"audit requirements","source":"operator"}]}
for name,value in [('baseline_schema.json',base),('upgrade_schema.json',new),('operator_old.json',policy_old),('operator_new.json',policy_new)]:
 (p/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
print('P4T_SYNTHETIC_FIXTURES_READY')
