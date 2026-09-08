'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs');
for(const name of ['math','geometry','model','exchange','production','kernel','constraints','dynamic-blocks','fonts','source-document'])require('../src/'+name+'.js');
const K=globalThis.Kestrel,X=K.Exchange,S=K.SourceDocument,tests=[];
function test(name,fn){try{fn();tests.push({name,status:'passed'});console.log('PASS',name);}catch(e){tests.push({name,status:'failed',error:e.stack});console.error('FAIL',name,e);}}
const read=raw=>K.Drawing.from(X.parseDXF(raw).data),records=(raw,type)=>S.parseRaw(raw,typeof raw==='string').records.filter(r=>r.type===type);
function make(entities){const d=new K.Drawing('Fidelity');d.currentLayer='0';for(const e of entities)d.add(e);d.reindex();return d;}
for(const binary of [false,true]){
 const label=binary?'binary':'ASCII',convert=raw=>binary?S.toBinary(raw):raw;
 test(label+' coordinates retain every significant IEEE-754 digit',()=>{
  const p=[1.2345678901234567,-1.234567890123456e-11,987654321.9876543],d=make([{type:'POINT',position:p}]);
  assert.deepEqual(read(convert(X.writeDXF(d))).entities[0].position,p);
 });
 test(label+' changing one endpoint does not round the unedited endpoint',()=>{
  const first=[1.2345678901234567,3.141592653589793,0],d=read(convert(X.writeDXF(make([{type:'LINE',points:[first,[20,30,0]]}]))));
  d.transaction('Edit endpoint',()=>d.entities[0].points[1][0]=21.123456789012345);
  const again=read(S.exportPreserved(d).bytes);assert.deepEqual(again.entities[0].points[0],first);assert.equal(again.entities[0].points[1][0],21.123456789012345);
 });
 test(label+' leading and trailing Unicode TEXT spaces survive edits and conversion',()=>{
  const text='  Łódź 工程  ',d=read(convert(X.writeDXF(make([{type:'TEXT',position:[0,0,0],height:3,text}]))));
  assert.equal(d.entities[0].text,text);d.transaction('Place text',()=>d.entities[0].position[0]=13);
  assert.equal(read(S.exportPreserved(d).bytes).entities[0].text,text);assert.equal(read(convert(X.writeDXF(d))).entities[0].text,text);
 });
 test(label+' source polyline generation flags remain after geometry changes',()=>{
  const d=make([{type:'POLYLINE',points:[[0,0,0],[10,0,0],[10,5,0]],closed:true}]),raw=X.writeDXF(d).replace('90\n3\n70\n1\n','90\n3\n70\n129\n'),i=read(convert(raw));
  i.transaction('Open',()=>i.entities[0].closed=false);const out=S.exportPreserved(i).bytes;
  assert.equal(records(out,'LWPOLYLINE')[0].groups.find(g=>g.code===70).value,'128');
 });
 test(label+' unknown text generation flags survive editable orientation changes',()=>{
  const d=make([{type:'TEXT',position:[0,0,0],height:3,text:'A'}]);let raw=X.writeDXF(d);const r=records(raw,'TEXT')[0];
  const old=raw.slice(r.start,r.end),updated=old.replace(/71\n\d+\n/,'71\n8\n');assert.notEqual(old,updated);
  raw=raw.slice(0,r.start)+updated+raw.slice(r.end);const i=read(convert(raw));i.transaction('Backwards',()=>i.entities[0].backwards=true);
  assert.equal(records(S.exportPreserved(i).bytes,'TEXT')[0].groups.find(g=>g.code===71).value,'10');
 });
}
test('distinct Unicode blocks and attributes survive repeated compatibility round trips',()=>{
 let d=make([]);for(const [index,name]of ['工程甲','工程乙','Śruba'].entries()){
  const e=d.add('LINE',{points:[[index*10,0,0],[index*10+5,0,0]]});d.reindex();const b=K.Production.defineBlock(d,name,[e.id],[0,0,0]);
  b.attributes=[{tag:'ID',value:'  原值  ',position:[index*10,0,0],height:2}];d.entities.find(e=>e.block===b.id).attributes={ID:'  '+name+'  '};
 }
 for(let iteration=0;iteration<4;iteration++)d=read(X.writeDXF(d));
 assert.deepEqual(d.production.blocks.map(b=>b.name),['工程甲','工程乙','Śruba']);
 assert.equal(d.entities.length,3);assert.deepEqual(d.entities.map(e=>e.attributes.ID),['  工程甲  ','  工程乙  ','  Śruba  ']);
 assert.equal(d.production.blocks[0].attributes[0].value,'  原值  ');
});
test('model and paper containers are not imported as user blocks',()=>{
 const d=read(X.writeDXF(make([{type:'POINT',position:[0,0,0]}])));assert.equal(d.production.blocks.length,0);
});
test('unrelated source record bytes remain intact around precision and text edits',()=>{
 let raw=X.writeDXF(make([{type:'TEXT',position:[1,2,0],height:3,text:' A '}]));raw=raw.replace('0\nEOF\n','0\nSECTION\n2\nOBJECTS\n0\nXRECORD\n5\nF000\n100\nAcDbXrecord\n1\n  opaque  \n0\nENDSEC\n0\nEOF\n');
 const d=read(raw);d.transaction('Move',()=>d.entities[0].position[0]=Math.PI);const out=S.exportPreserved(d).bytes,r=records(raw,'XRECORD')[0],q=records(out,'XRECORD')[0];assert.equal(Buffer.from(out).subarray(q.start,q.end).toString(),raw.slice(r.start,r.end));
});
test('switching source color removes obsolete color-book names',()=>{
 let raw=X.writeDXF(make([{type:'POINT',position:[0,0,0],color:'#112233'}])).replace('AC1015','AC1018');raw=raw.replace('420\n1122867\n','420\n1122867\n430\nSample$Obsolete\n');
 const d=read(raw);d.transaction('ByLayer',()=>d.entities[0].color='bylayer');const out=S.exportPreserved(d).bytes;assert.equal(records(out,'POINT')[0].groups.some(g=>[62,420,430].includes(g.code)),false);
 assert.equal(read(out).entities[0].color,'bylayer');
});
const failed=tests.filter(t=>t.status==='failed').length;fs.mkdirSync('tests/results',{recursive:true});fs.writeFileSync('tests/results/exchange-fidelity-results.json',JSON.stringify({passed:tests.length-failed,failed,tests},null,2));console.log(`Exchange fidelity: ${tests.length-failed}/${tests.length} passed`);process.exitCode=failed?1:0;
