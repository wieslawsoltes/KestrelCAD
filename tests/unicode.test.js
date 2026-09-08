/* Unicode 17 UAX #9: pinned, deterministic corpus. Full corpus via KESTREL_BIDI_FIXTURES. */
'use strict';
const fs=require('fs'),path=require('path'),zlib=require('zlib');
globalThis.Kestrel={};require('../src/unicode-bidi');const U=Kestrel.Unicode;
let samples=JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures/unicode-bidi-sample.json'))).cases;
if(process.env.KESTREL_BIDI_FIXTURES){
 const root=process.env.KESTREL_BIDI_FIXTURES; samples=[];
 for(const line of zlib.gunzipSync(fs.readFileSync(path.join(root,'BidiCharacterTest.txt.gz'))).toString().split('\n')){
  if(!line||line.startsWith('#'))continue;const f=line.split(';');if(f.length<5)continue;
  samples.push({kind:'characters',input:f[0].trim(),direction:Number(f[1]),para:Number(f[2]),levels:f[3].split(/\s+/).filter(Boolean),order:f[4].split(/\s+/).filter(Boolean).map(Number)});
 }
 let levels=[],order=[];
 for(const raw of zlib.gunzipSync(fs.readFileSync(path.join(root,'BidiTest.txt.gz'))).toString().split('\n')){
  const line=raw.trim();if(!line||line.startsWith('#'))continue;
  if(line.startsWith('@Levels:'))levels=line.slice(8).trim().split(/\s+/).filter(Boolean);
  else if(line.startsWith('@Reorder:'))order=line.slice(9).trim().split(/\s+/).filter(Boolean).map(Number);
  else if(line.includes(';')){const[a,b]=line.split(';');samples.push({kind:'types',input:a.trim(),bitset:Number(b),levels,order});}
 }
}
const names=new Map(U.BIDI_CLASS_NAMES.map((n,i)=>[n,i]));let cases=0,failures=0;const examples=[];
function check(sample,para,result){cases++;const actual=Array.from(result.levels,(v,i)=>result.removed[i]?'x':String(v));const order=result.order||U.reorderIndices(result.levels,result.removed);if(para!==sample.para&&sample.para!==undefined||actual.join(' ')!==sample.levels.join(' ')||order.join(' ')!==sample.order.join(' ')){failures++;if(examples.length<10)examples.push({input:sample.input,para,actual,expected:sample.levels,order,expectedOrder:sample.order});}}
for(const s of samples){
 if(s.kind==='characters'){const cps=Int32Array.from(s.input.split(/\s+/).map(v=>parseInt(v,16))),types=U.classify(cps),para=s.direction<2?s.direction:U.computeBaseLevel(types,0,types.length),res=U.resolveParagraph(types,cps,para);U.applyL1(types,res.levels,res.removed,para);check(s,para,res);}
 else{const types=Uint8Array.from(s.input.split(/\s+/),v=>names.get(v));for(const [bit,para]of [[1,U.baseLevelForTypes(types)],[2,0],[4,1]])if(s.bitset&bit)check(s,para,U.resolveByTypes(types,para));}
}
// One aggregate test report. The conformance case count is not a CAD-feature test count.
const report={passed:failures?0:1,failed:failures?1:0,unicodeVersion:U.UNICODE_VERSION,conformanceCases:cases,conformanceFailures:failures,tests:[{name:'Unicode bidi level/order conformance ('+cases+' cases)',status:failures?'failed':'passed',examples}]};
fs.mkdirSync(path.join(__dirname,'results'),{recursive:true});fs.writeFileSync(path.join(__dirname,'results/unicode-results.json'),JSON.stringify(report,null,2));console.log('Unicode cases:',cases,'failures:',failures,examples);process.exitCode=failures?1:0;
