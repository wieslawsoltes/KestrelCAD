'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs');
for(const f of ['math','geometry','model','exchange','production','kernel'])require('../src/'+f+'.js');
const K=globalThis.Kestrel,N=K.Kernel,M=K.Math.M;const results=[];
function test(name,fn){try{fn();results.push({name,status:'passed'});console.log('PASS',name);}catch(e){results.push({name,status:'failed',error:e.stack});console.error('FAIL',name,e);}}
// Synthetic transport fixture: client integrity tests, not native-kernel validation.
function body(){return N.body({provider:'OCCT',valid:true,version:'test',brep:'YWJj',volume:1,area:6,solidCount:1,mesh:{type:'MESH',vertices:[[0,0,0],[1,0,0],[0,1,0]],faces:[[0,1,2]]},edges:[],faces:[],edgePolylines:[]});}
function doc(){const d=new K.Drawing();d.add(body());return d;}
test('native metadata survives project serialization',()=>{const d=doc(),copy=K.Drawing.from(d.serialize());assert.equal(copy.entities[0].solid.brep,'YWJj');});
test('ordinary move updates native matrix and display mesh together',()=>{const e=body(),m=M.translation(10,20,30),t=K.Geo.transform(e,m);assert.deepEqual(t.vertices[0],[10,20,30]);assert.deepEqual(t.solid.transform,Array.from(m));N.validate(t);});
test('matrix composition survives successive transformations',()=>{let e=body();e=K.Geo.transform(e,M.translation(10,0,0));e=K.Geo.transform(e,M.scale(2));assert.equal(e.solid.transform[12],20);N.validate(e);});
test('mesh-only grip edit fails atomically',()=>{const d=doc(),before=d.snapshot();assert.throws(()=>d.transaction('bad grip',()=>d.entities[0].vertices[0][0]=100),/display mesh/);assert.equal(d.snapshot(),before);});
test('detach and undo restore native data',()=>{const d=doc();d.transaction('detach',()=>delete d.entities[0].solid);assert.equal(d.entities[0].solid,undefined);d.undo();N.validate(d.entities[0]);assert.equal(d.entities[0].solid.provider,'OCCT');});
test('native transform is undoable',()=>{const d=doc();d.transaction('move',()=>d.transform([d.entities[0].id],M.translation(40,0,0)));assert.equal(d.entities[0].vertices[0][0],40);d.undo();assert.equal(d.entities[0].vertices[0][0],0);});
test('ordinary mesh cannot impersonate a native input',()=>assert.throws(()=>N.input({type:'MESH',vertices:[],faces:[]}),/native/));
test('corrupt native matrix is rejected',()=>{const e=body();e.solid.transform=[0];assert.throws(()=>N.validate(e),/transform/);});
test('native circles remain analytical profiles',()=>{const p=N.profile({type:'CIRCLE',center:[0,0,0],radius:2});assert.equal(p.type,'circle');assert.equal(p.radius,2);});
test('unsupported mesh profile is explicit',()=>assert.throws(()=>N.profile(body()),/profile/));
const failed=results.filter(t=>t.status==='failed').length;fs.writeFileSync('tests/results/kernel-client-results.json',JSON.stringify({passed:results.length-failed,failed,tests:results},null,2));process.exitCode=failed?1:0;
