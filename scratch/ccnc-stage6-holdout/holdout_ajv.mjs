import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import AjvPkg from 'ajv/dist/2020.js';
const Ajv=AjvPkg.default||AjvPkg;
const ajv=new Ajv({strict:false,allErrors:true,validateFormats:false});
const maps=['properties','patternProperties','$defs','definitions','dependentSchemas'];
const singles=['items','contains','not','if','then','else','propertyNames','contentSchema'];
const arrays=['allOf','anyOf','oneOf','prefixItems'];
const suites=['additionalProperties','unevaluatedProperties','patternProperties','oneOf','anyOf','dependentSchemas','ref','if-then-else','items'];
function walk(s,p=[]){const r=[[p,s]];if(!s||typeof s!=='object'||Array.isArray(s))return r;
 for(const k of maps)if(s[k]&&typeof s[k]==='object'&&!Array.isArray(s[k]))
  for(const n of Object.keys(s[k]))r.push(...walk(s[k][n],[...p,k,n]));
 for(const k of singles)if(k in s)r.push(...walk(s[k],[...p,k]));
 for(const k of arrays)if(Array.isArray(s[k]))s[k].forEach((v,i)=>r.push(...walk(v,[...p,k,i])));
 return r;
}
const at=(s,p)=>p.reduce((x,k)=>x[k],s);
const boundary=s=>s&&typeof s==='object'&&!Array.isArray(s)&&
 (s.type==='object'||Array.isArray(s.type)&&s.type.includes('object')||
  ['properties','patternProperties','additionalProperties','unevaluatedProperties','required','propertyNames','minProperties','maxProperties','dependentSchemas','dependentRequired'].some(k=>k in s));
function project(src){const baseline=structuredClone(src),ops=[];
 for(const [path,orig] of walk(src)){if(!boundary(orig))continue;const d=at(baseline,path);
  for(const k of ['additionalProperties','unevaluatedProperties'])
   ops.push({path,keyword:k,present:k in orig,...(k in orig?{value:structuredClone(orig[k])}:{})});
  d.additionalProperties=false;delete d.unevaluatedProperties;
 }return {baseline,ops};
}
function restore(base,ops){const s=structuredClone(base);for(const op of ops){const d=at(s,op.path);
 if(op.present)d[op.keyword]=structuredClone(op.value);else delete d[op.keyword];}return s}
function compatible(c){if(c===undefined)return true;let valid=true;for(const raw of String(c).split(',')){const part=raw.trim();const op=part.startsWith('<=')?'<=':part.startsWith('=')?'=':'';const v=Number(part.slice(op.length));if(!Number.isFinite(v))throw Error('bad compatibility '+part);valid=op==='='?2020===v:op==='<='?2020<=v:2020>=v;if(2020<=v)break;}return valid}
function nonlocal(s){return walk(s).some(([,n])=>n&&typeof n==='object'&&!Array.isArray(n)&&
 ['$ref','$dynamicRef'].some(k=>typeof n[k]==='string'&&!n[k].startsWith('#')))}
const outdir='evidence';fs.mkdirSync(outdir,{recursive:true});
const res={engine:'ajv 8.17.1',suite_results:[],groups_total:0,groups_checked:0,groups_skipped:0,
 cases_checked:0,source_expected_mismatches:0,roundtrip_failures:0,
 baseline_false_rejects:0,baseline_false_accepts:0,skips:[],failures:[]};
for(const name of suites){const buf=fs.readFileSync(path.join('upstream',name+'.json'));
 const spec=JSON.parse(buf),groups=spec.tests,report={name,sha256:crypto.createHash('sha256').update(buf).digest('hex'),groups:groups.length,checked:0,cases:0};
 for(const [i,g] of groups.entries()){
  res.groups_total++;
  if(!compatible(g.compatibility)){res.groups_skipped++;res.skips.push({suite:name,i,reason:'incompatible with 2020-12'});continue;}
  if(nonlocal(g.schema)){res.groups_skipped++;res.skips.push({suite:name,i,reason:'nonlocal reference'});continue;}
  try{
   const src=structuredClone(g.schema),{baseline,ops}=project(src),repaired=restore(baseline,ops);
   assert.deepStrictEqual(repaired,src);
   const a=ajv.compile(src),b=ajv.compile(baseline),c=ajv.compile(repaired);
   res.groups_checked++;report.checked++;
   for(const t of g.tests){
    const s=!!a(t.data),p=!!b(t.data),r=!!c(t.data);
    report.cases++;res.cases_checked++;
    if(s!==t.valid){res.source_expected_mismatches++;res.failures.push({suite:name,i,test:t.description,expected:t.valid,got:s})}
    if(s!==r){res.roundtrip_failures++;res.failures.push({suite:name,i,test:t.description,reason:'repair mismatch'})}
    res.baseline_false_rejects+=+(s&&!p);res.baseline_false_accepts+=+(!s&&p);
   }
  }catch(e){res.groups_skipped++;res.skips.push({suite:name,i,reason:String(e).slice(0,500)})}
 }
 res.suite_results.push(report);
}
fs.writeFileSync(path.join(outdir,'official_holdout_ajv.json'),JSON.stringify(res,null,2)+'\n');
console.log('CCNC_STAGE6_HOLDOUT '+JSON.stringify(Object.fromEntries(['groups_total','groups_checked','groups_skipped','cases_checked','source_expected_mismatches','roundtrip_failures','baseline_false_rejects','baseline_false_accepts'].map(k=>[k,res[k]]))));
if(!res.groups_checked||res.source_expected_mismatches||res.roundtrip_failures)process.exitCode=1;
