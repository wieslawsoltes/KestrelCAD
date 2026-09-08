'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs');
for(const n of ['math','geometry','model','exchange','production','kernel','native-analysis'])require('../src/'+n+'.js');
const K=globalThis.Kestrel,A=K.NativeAnalysis,N=K.Kernel,tests=[];
function test(name,fn){try{fn();tests.push({name,status:'passed'});console.log('PASS',name);}catch(e){tests.push({name,status:'failed',error:e.stack});console.error('FAIL',name,e);}}
// Deliberately synthetic transport fixture: native geometry is tested by Python and HTTP suites.
function body(volume=1){return {provider:'OCCT',valid:true,brep:'QQ==',mesh:K.Geo.box([0,0,0],1,1,1),version:'contract-fixture',volume,area:6,solidCount:1,tolerance:.1,edges:[],faces:[],edgePolylines:[]};}
function fixture(){const d=new K.Drawing();const es=[d.add(N.body(body())),d.add(N.body(body()))];return {d,es,s:A.prepare(d,es,{regions:true})};}
function report(){return {provider:'OCCT',schema:1,analysis:'interference-clearance',bodyCount:2,pairCount:1,clearance:0,contactTolerance:1e-6,pairs:[{first:0,second:1,status:'interference',distance:0,volume:1,witnesses:[[[0,0,0],[0,0,0]]],witnessCount:1,innerSolution:true}],counts:{interference:1,contact:0,clearance:0,separated:0},bodies:[{first:0,second:1,...body()}]};}
test('unique unordered pairs',()=>assert.deepEqual(A.pairs(3),[[0,1],[0,2],[1,2]]));
test('two-set overlap membership excluded',()=>assert.deepEqual(A.pairs(4,{first:[0,1],second:[1,2,3]}),[[0,2],[0,3],[1,2],[1,3]]));
test('bounded pair count',()=>assert.throws(()=>A.pairs(32),/128/));
test('duplicate indices rejected',()=>assert.throws(()=>A.pairs(3,{first:[0,0],second:[1]}),/indices/));
test('empty effective set rejected',()=>assert.throws(()=>A.pairs(2,{first:[0],second:[0]}),/pairs/));
for(const bad of [NaN,Infinity,-1,'2',true])test('reject invalid clearance '+bad,()=>assert.throws(()=>A.options({clearance:bad}),/clearance/));
test('capture clones authoritative inputs',()=>{const f=fixture();f.s.inputs[0].brep='Qg==';assert.equal(f.es[0].solid.brep,'QQ==');});
test('locked sources are readable',()=>{const f=fixture();f.d.layer(f.es[0]).locked=true;assert.equal(A.prepare(f.d,f.es).ids.length,2);});
test('hidden sources reject',()=>{const f=fixture();f.es[0].hidden=true;assert.throws(()=>A.prepare(f.d,f.es),/visible/);});
test('mesh-only body rejects',()=>{const f=fixture();delete f.es[0].solid;assert.throws(()=>A.prepare(f.d,f.es),/native/);});
test('duplicate source bodies reject',()=>{const f=fixture();assert.throws(()=>A.prepare(f.d,[f.es[0],f.es[0]]),/distinct/);});
test('valid complete response prepares native outputs',()=>assert.equal(A.validate(report(),2,{regions:true}).length,1));
for(const key of ['volume','distance'])test('reject nonfinite '+key,()=>{const r=report();r.pairs[0][key]=NaN;assert.throws(()=>A.validate(r,2,{regions:true}),/response/);});
test('wrong response pairs reject',()=>{const r=report();r.pairs[0].second=0;assert.throws(()=>A.validate(r,2,{regions:true}),/response/);});
test('missing overlap body rejects',()=>{const r=report();r.bodies=[];assert.throws(()=>A.validate(r,2,{regions:true}),/response/);});
test('incorrect summary counts reject',()=>{const r=report();r.counts.interference=0;assert.throws(()=>A.validate(r,2,{regions:true}),/response/);});
test('wrong material volume rejects',()=>{const r=report();r.bodies[0].volume=2;assert.throws(()=>A.validate(r,2,{regions:true}),/response/);});
test('wrong witness length rejects',()=>{const r=report();r.pairs[0].witnesses[0][1]=[20,0,0];assert.throws(()=>A.validate(r,2,{regions:true}),/response/);});
test('retain adds independent bodies and preserves inputs',()=>{const f=fixture(),before=JSON.stringify(f.es);A.retain(f.s,report());assert.equal(f.d.entities.length,3);assert.equal(JSON.stringify(f.es),before);});
test('retention undo and redo are atomic',()=>{const f=fixture();A.retain(f.s,report());f.d.undo();assert.equal(f.d.entities.length,2);f.d.redo();assert.equal(f.d.entities.length,3);});
test('invalid response cannot partially mutate',()=>{const f=fixture(),snapshot=f.d.snapshot(),r=report();r.bodies[0].valid=false;assert.throws(()=>A.retain(f.s,r));assert.equal(f.d.snapshot(),snapshot);});
test('stale analysis refuses retention',()=>{const f=fixture();f.d.transaction('Other',()=>f.d.add('POINT',{position:[0,0,0]}));assert.throws(()=>A.retain(f.s,report()),/changed/);});
test('locked current layer blocks result writes',()=>{const f=fixture();f.d.layer(f.d.currentLayer).locked=true;assert.throws(()=>A.retain(f.s,report()),/unlocked/);});
test('retained BREP persists in native project',()=>{const f=fixture();A.retain(f.s,report());const d=K.Drawing.from(f.d.serialize());assert.equal(d.entities[2].solid.brep,'QQ==');});
test('zero-gap line refuses coincident geometry',()=>{const f=fixture();assert.throws(()=>A.gapLine(f.s,report(),0),/positive/);});
test('gap line uses witness points and supports undo',()=>{const f=fixture(),r=report();r.bodies=[];r.counts={interference:0,contact:0,clearance:0,separated:1};Object.assign(r.pairs[0],{volume:0,status:'separated',distance:2,witnesses:[[[1,0,0],[3,0,0]]]});const line=A.gapLine(f.s,r,0);assert.deepEqual(line.points,[[1,0,0],[3,0,0]]);f.d.undo();assert.equal(f.d.entities.length,2);});
const failed=tests.filter(t=>t.status==='failed').length;fs.mkdirSync('tests/results',{recursive:true});fs.writeFileSync('tests/results/native-analysis-client-results.json',JSON.stringify({passed:tests.length-failed,failed,tests},null,2));if(failed)process.exitCode=1;
