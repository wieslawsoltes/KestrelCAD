'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs');
for (const file of ['math','geometry','model','exchange','production','kernel','constraints','dynamic-blocks','fonts','source-document']) require('../src/' + file + '.js');
const K = globalThis.Kestrel, S = K.SourceDocument, X = K.Exchange, { M } = K.Math, tests = [];
function test(name, fn) { try { fn(); tests.push({ name, status: 'passed' }); console.log('PASS', name); } catch (e) { tests.push({ name, status: 'failed', error: e.stack }); console.error('FAIL', name, e); } }
const equalBytes = (a,b) => assert.ok(Buffer.from(a).equals(Buffer.from(b)), 'bytes differ');
const near = (a,b) => assert.ok(Math.abs(a-b)<1e-7, `${a} != ${b}`);
function source(entities) { const d = new K.Drawing('Preservation'); d.currentLayer='0'; for(const e of entities || [{type:'LINE',points:[[1,2,3],[5,6,7]]}])d.add(e); d.reindex(); return X.writeDXF(d).replace('AC1015','AC1018'); }
function imported(input) { return K.Drawing.from(X.parseDXF(input,'Preservation').data); }
function edited(d, fn) { d.transaction('Edit',()=>fn(d.entities[0],d)); return S.exportPreserved(d); }
function entityOf(output) { return imported(output.bytes).entities[0]; }
function records(input,type){return S.parseRaw(input,typeof input==='string').records.filter(r=>r.type===type);}
function extra(input) { return input.replace('0\nEOF\n','0\nSECTION\n2\nOBJECTS\n0\nACAD_PROXY_OBJECT\n5\nFEED\n100\nUninterpretedApplication\n160\n9007199254740993\n310\nDEADBEEF00FF\n1\nRetain spaces   \n0\nENDSEC\n0\nSECTION\n2\nCUSTOM_DATA\n0\nCUSTOM_RECORD\n5\nFEF0\n1000\nUntouched metadata\n0\nENDSEC\n0\nEOF\n'); }
function rawRecord(input,type){const s=S.parseRaw(input,typeof input==='string'),r=s.records.find(r=>r.type===type);return s.raw.subarray(r.start,r.end);}
const original=extra(source());
test('ASCII no-change export restores every original byte including whitespace',()=>{const raw=Buffer.from(original.replace(/\n/g,'\r\n')+'999\r\ntrailing comment\r\n'),d=imported(raw);equalBytes(S.exportPreserved(d).bytes,raw);assert.ok(d.sourceDocument);});
test('UTF8 BOM and exact raw Unicode source survive untouched native round trip',()=>{const raw=Buffer.from('\ufeff'+source([{type:'TEXT',position:[0,0,0],text:'工程 Łódź',height:3}]).replace('AC1018','AC1021'));const d=imported(raw),again=K.Drawing.from(JSON.parse(JSON.stringify(d.serialize())));equalBytes(S.original(again),raw);equalBytes(S.exportPreserved(again).bytes,raw);});
test('source archive is immutable and is not copied into undo snapshots',()=>{const d=imported(original),a=d.sourceDocument;edited(d,e=>e.points[0][0]=8);assert.ok(Object.isFrozen(a));assert.ok(!d.undoStack[0].state.includes('sourceDocument'));assert.strictEqual(d.sourceDocument,a);d.undo();assert.strictEqual(d.sourceDocument,a);equalBytes(S.exportPreserved(d).bytes,Buffer.from(original));d.redo();near(entityOf(S.exportPreserved(d)).points[0][0],8);});
test('failed edits restore native geometry without dropping archived source',()=>{const d=imported(original),snap=d.snapshot(),archive=d.sourceDocument;assert.throws(()=>d.transaction('Invalid',()=>d.entities[0].points=[]));assert.equal(d.snapshot(),snap);assert.strictEqual(d.sourceDocument,archive);});
test('applying an unrelated native drawing clears old provenance',()=>{const d=imported(original);d.apply(new K.Drawing('other').serialize());assert.equal(d.sourceDocument,null);});
test('line edits keep unknown sections and proxy objects byte-identical',()=>{const d=imported(original),o=edited(d,e=>e.points[1]=[10,20,30]);assert.deepEqual(entityOf(o).points[1],[10,20,30]);equalBytes(rawRecord(o.bytes,'ACAD_PROXY_OBJECT'),rawRecord(original,'ACAD_PROXY_OBJECT'));equalBytes(rawRecord(o.bytes,'CUSTOM_RECORD'),rawRecord(original,'CUSTOM_RECORD'));assert.equal(o.report.changed,1);});
test('extension control groups cannot masquerade as editable coordinate fields',()=>{const raw=original.replace('100\nAcDbLine\n','100\nAcDbLine\n102\n{CUSTOM\n10\n999\n20\n888\n102\n}\n'),d=imported(raw);assert.deepEqual(d.entities[0].points[0],[1,2,3]);const o=edited(d,e=>e.points[0]=[4,5,6]);assert.ok(Buffer.from(o.bytes).toString().includes('102\n{CUSTOM\n10\n999\n20\n888\n102\n}\n'));assert.deepEqual(entityOf(o).points[0],[4,5,6]);});
for (const [label,e,mutate,check] of [
 ['point',{type:'POINT',position:[1,2,3]},e=>e.position=[4,5,6],e=>assert.deepEqual(e.position,[4,5,6])],
 ['circle',{type:'CIRCLE',center:[1,2,0],radius:4},e=>e.radius=9,e=>near(e.radius,9)],
 ['arc',{type:'ARC',center:[0,0,0],radius:5,startAngle:.2,endAngle:2},e=>e.endAngle=3,e=>near(e.endAngle,3)],
 ['ellipse',{type:'ELLIPSE',center:[0,0,0],rx:10,ry:3},e=>{e.axisX=[0,12,0];e.axisY=[-4,0,0];},e=>near(K.Math.V.len(K.Geo.conicAxes(e).x),12)],
 ['polyline',{type:'POLYLINE',points:[[0,0,0],[10,0,0],[10,10,0]],bulges:[0,.2,0],closed:false},e=>{e.points[1]=[20,0,0];e.bulges=[.5,0,0];e.closed=true;},e=>{assert.equal(e.closed,true);near(e.bulges[0],.5);near(e.bulges[1],0);near(e.points[1][0],20);}],
 ['spline',{type:'SPLINE',controlPoints:[[0,0,0],[10,10,0],[20,0,0]],degree:2,weights:[1,2,1]},e=>{e.controlPoints[1]=[11,12,3];e.weights=[1,3,1];},e=>{assert.deepEqual(e.controlPoints[1],[11,12,3]);near(e.weights[1],3);}],
 ['text',{type:'TEXT',position:[0,0,0],text:'Before',height:3,align:'center'},e=>{e.text='After ±';e.height=5;e.widthFactor=2;e.oblique=15;},e=>{assert.equal(e.text,'After ±');near(e.height,5);near(e.widthFactor,2);near(e.oblique,15);}]
]) test('guarded '+label+' editing preserves actual entity behavior',()=>{const d=imported(source([e]));check(entityOf(edited(d,mutate)));});
test('arc rotation preserves circular subclasses and OCS data',()=>{const d=imported(source([{type:'ARC',center:[1,2,0],radius:5,startAngle:0,endAngle:Math.PI}]));d.transaction('Tilt',()=>d.transform([d.entities[0].id],M.rotation(Math.PI/3,[1,0,0])));const o=S.exportPreserved(d),a=entityOf(o);near(K.Math.V.dist(a.center,d.entities[0].center),0);const r=records(o.bytes,'ARC')[0];assert.equal(r.groups.filter(g=>g.code===100&&g.value==='AcDbArc').length,1);});
test('new simple entities get unique handles and original model-space owner',()=>{const d=imported(original);d.transaction('Add',()=>{d.add('CIRCLE',{center:[20,30,0],radius:3,layer:'0'});d.add('LINE',{points:[[0,0,0],[1,1,1]],layer:'0'});});const o=S.exportPreserved(d);assert.equal(o.report.added,2);const reread=imported(o.bytes);assert.equal(reread.entities.length,3);const r=S.parseRaw(o.bytes),handles=r.records.map(x=>x.handle).filter(Boolean);assert.equal(new Set(handles).size,handles.length);equalBytes(rawRecord(o.bytes,'ACAD_PROXY_OBJECT'),rawRecord(original,'ACAD_PROXY_OBJECT'));});
test('an unreferenced simple source entity can be deleted',()=>{const d=imported(original);d.transaction('Delete',()=>d.remove([d.entities[0].id]));const o=S.exportPreserved(d);assert.equal(o.report.deleted,1);assert.equal(imported(o.bytes).entities.length,0);equalBytes(rawRecord(o.bytes,'ACAD_PROXY_OBJECT'),rawRecord(original,'ACAD_PROXY_OBJECT'));});
test('dangling source object references block unsafe deletion',()=>{const handle=records(original,'LINE')[0].handle,raw=original.replace('100\nUninterpretedApplication\n','100\nUninterpretedApplication\n340\n'+handle+'\n'),d=imported(raw);d.transaction('Delete',()=>d.remove([d.entities[0].id]));assert.throws(()=>S.exportPreserved(d),/dangling handle/);equalBytes(S.original(d),Buffer.from(raw));});
test('changing type refuses source export rather than losing native ellipse data',()=>{const d=imported(source([{type:'CIRCLE',center:[0,0,0],radius:3}]));d.transaction('Scale',()=>d.transform([d.entities[0].id],M.scale(2,1,1)));assert.throws(()=>S.exportPreserved(d),/type change/);});
test('source entities without handles remain byte-preserving until edited',()=>{const raw='0\nSECTION\n2\nENTITIES\n0\nLINE\n10\n1\n20\n2\n11\n3\n21\n4\n0\nENDSEC\n0\nEOF\n',d=imported(raw);equalBytes(S.exportPreserved(d).bytes,Buffer.from(raw));d.transaction('Move',()=>d.entities[0].points[0][0]++);assert.throws(()=>S.exportPreserved(d),/unambiguous/);});
test('multiline conversion of a source TEXT refuses rather than flattening',()=>{const d=imported(source([{type:'TEXT',text:'A',position:[0,0,0],height:3}]));d.transaction('Multiline',()=>d.entities[0].text='A\nB');assert.throws(()=>S.exportPreserved(d),/multiline/);});
test('unknown property changes require explicit compatibility export',()=>{const d=imported(original);d.transaction('Group',()=>d.entities[0].group='assembly');assert.throws(()=>S.exportPreserved(d),/group/);});
test('new block definitions cannot silently disappear in preserved export',()=>{const d=imported(original);K.Production.defineBlock(d,'New',[d.entities[0].id]);assert.throws(()=>S.exportPreserved(d),/blocks/);});
test('source width metadata prevents a geometry rewrite that would lose it',()=>{const raw=source([{type:'POLYLINE',points:[[0,0,0],[5,0,0],[5,5,0]],closed:true}]).replace('100\nAcDbPolyline\n','100\nAcDbPolyline\n43\n2\n'),d=imported(raw);d.transaction('Move',()=>d.entities[0].points[0][0]=2);assert.throws(()=>S.exportPreserved(d),/width/);});
test('source extrusion thickness is not silently ignored by editing',()=>{const raw=source([{type:'CIRCLE',center:[0,0,0],radius:5}]).replace('100\nAcDbCircle\n','100\nAcDbCircle\n39\n10\n'),d=imported(raw);d.transaction('Radius',()=>d.entities[0].radius=6);assert.throws(()=>S.exportPreserved(d),/thickness/);});
test('existing entity and layer appearance edits retain unrelated records',()=>{const d=imported(original);d.transaction('Appearance',()=>{const e=d.entities[0];e.color='#112233';e.lineweight=.8;e.linetype='Dashed';const l=d.layer('0');l.color='#445566';l.locked=true;});const o=S.exportPreserved(d),r=imported(o.bytes);assert.equal(r.entities[0].color,'#112233');near(r.entities[0].lineweight,.8);assert.equal(r.layer('0').color,'#445566');assert.equal(r.layer('0').locked,true);});
test('layer rename cannot leave unknown layer references dangling',()=>{const d=imported(original);d.transaction('Rename',()=>d.layers[0].name='Renamed');assert.throws(()=>S.exportPreserved(d),/renaming/);});
test('new layer is rejected without silently dropping the layer table change',()=>{const d=imported(original);d.transaction('Layer',()=>d.addLayer('Another'));assert.throws(()=>S.exportPreserved(d),/Adding layers/);});
test('units header can be updated without regenerating original objects',()=>{const d=imported(original);d.transaction('Units',()=>d.units='cm');const o=S.exportPreserved(d);assert.equal(imported(o.bytes).units,'cm');equalBytes(rawRecord(o.bytes,'LINE'),rawRecord(original,'LINE'));});
const binary=S.toBinary(original);
test('binary DXF imports supported geometry with original-source provenance',()=>{const d=imported(binary);assert.deepEqual(d.entities[0].points,[[1,2,3],[5,6,7]]);assert.ok(d.sourceDocument.binary);equalBytes(S.exportPreserved(d).bytes,binary);});
test('binary int64 retains integers beyond the JavaScript safe number range',()=>{const g=S.parseRaw(binary).groups.find(g=>g.code===160);assert.equal(g.value,'9007199254740993');});
test('binary chunk encoding retains every byte including zero',()=>{const g=S.parseRaw(binary).groups.find(g=>g.code===310);assert.equal(g.value,'DEADBEEF00FF');});
test('binary edits retain original binary container and all proxy bytes',()=>{const d=imported(binary),o=edited(d,e=>e.points[0]=[10,20,30]);assert.ok(S.parseRaw(o.bytes).binary);assert.deepEqual(entityOf(o).points[0],[10,20,30]);equalBytes(rawRecord(o.bytes,'ACAD_PROXY_OBJECT'),rawRecord(binary,'ACAD_PROXY_OBJECT'));});
test('binary additions use the source code width and valid new handles',()=>{const d=imported(binary);d.transaction('New point',()=>d.add('POINT',{position:[9,8,7],layer:'0'}));const o=S.exportPreserved(d);assert.equal(imported(o.bytes).entities.length,2);assert.ok(S.parseRaw(o.bytes).binary);});
test('R12 binary uses one-byte group codes and extended-code escapes',()=>{const raw='0\nSECTION\n2\nHEADER\n9\n$ACADVER\n1\nAC1009\n0\nENDSEC\n0\nSECTION\n2\nENTITIES\n0\nPOINT\n5\n10\n10\n1\n20\n2\n30\n3\n1001\nAPP\n1071\n12345678\n0\nENDSEC\n0\nEOF\n',b=S.toBinary(raw),d=imported(b);assert.ok(S.parseRaw(b).legacy);equalBytes(S.exportPreserved(d).bytes,b);const o=edited(d,e=>e.position[2]=9);near(entityOf(o).position[2],9);assert.equal(S.parseRaw(o.bytes).groups.find(g=>g.code===1071).value,'12345678');});
test('raw CP1252 strings stay byte-identical around an unrelated geometry edit',()=>{const raw=Buffer.from(extra(source()).replace('Retain spaces   ','Café en façade'),'latin1'),d=imported(raw),o=edited(d,e=>e.points[0][0]=88);equalBytes(rawRecord(o.bytes,'ACAD_PROXY_OBJECT'),rawRecord(raw,'ACAD_PROXY_OBJECT'));});
test('native projects retain original DWG separately from converted DXF',()=>{const data=X.parseDXF(original).data,originalDWG=Buffer.from('AC1032\0synthetic-container-not-a-real-codec-output');S.withOriginalDWG(data,originalDWG,'original.dwg');const d=K.Drawing.from(JSON.parse(JSON.stringify(data)));equalBytes(S.original(d),originalDWG);equalBytes(S.exportPreserved(d).bytes,Buffer.from(original));assert.equal(S.info(d).format,'dwg');});
for(const [name,fn] of [
 ['missing EOF',()=>S.parseRaw('0\nSECTION\n2\nENTITIES\n0\nENDSEC\n')],
 ['odd pair',()=>S.parseRaw('0\nSECTION\n2\n')],
 ['invalid code',()=>S.parseRaw('NaN\nSECTION\n')],
 ['truncated binary',()=>S.parseRaw(binary.subarray(0,50))],
 ['unknown binary value type',()=>S.valueType(200)],
 ['bad base64',()=>S.decode64('@@@@')],
 ['bad archive baseline',()=>S.validate({schema:1,format:'dxf',name:'a',encoding:'utf-8',bytes:'AAAA',baseline:'{}'})],
 ['zero original DWG signature',()=>S.withOriginalDWG(X.parseDXF(original).data,Buffer.from('NO-DWG'),'bad.dwg')],
 ['binary int64 overflow',()=>S.encodePair(160,'9223372036854775808',{binary:true})],
 ['integer overflow',()=>S.encodePair(70,'65536',{binary:true})],
 ['binary raw newline',()=>S.encodePair(1,'a\nb',{binary:true})],
 ['binary malformed chunk',()=>S.encodePair(310,'XYZ',{binary:true})],
 ['raw null values',()=>S.encodePair(1,'a\0b',{binary:false,newline:'\n',encoding:'utf-8'})]
])test('reject '+name,()=>assert.throws(fn));

test('source entity visibility survives compatibility and guarded round trips',()=>{
 const raw=source([{type:'POINT',position:[1,2,3],hidden:true}]),d=imported(raw);assert.equal(d.entities[0].hidden,true);
 assert.equal(d.visible(d.entities[0]),false);const out=edited(d,e=>delete e.hidden);assert.notEqual(entityOf(out).hidden,true);
});
test('new source objects reject native-only fields instead of silently dropping them',()=>{
 const d=imported(original);d.transaction('Add grouped point',()=>d.add('POINT',{position:[0,0,0],group:'group'}));assert.throws(()=>S.exportPreserved(d),/added property/);
});
test('legacy source lineweights reject rather than emitting newer-version fields',()=>{
 const raw='0\nSECTION\n2\nHEADER\n9\n$ACADVER\n1\nAC1009\n0\nENDSEC\n0\nSECTION\n2\nENTITIES\n0\nPOINT\n5\n10\n10\n1\n20\n2\n30\n3\n0\nENDSEC\n0\nEOF\n';
 const d=imported(raw);d.transaction('Weight',()=>d.entities[0].lineweight=.5);assert.throws(()=>S.exportPreserved(d),/Lineweight/);
});

const failed=tests.filter(t=>t.status==='failed').length;
fs.mkdirSync('tests/results',{recursive:true});fs.writeFileSync('tests/results/source-document-results.json',JSON.stringify({passed:tests.length-failed,failed,tests},null,2));
fs.writeFileSync('tests/results/source-fixture.dxf',original);fs.writeFileSync('tests/results/source-binary-fixture.dxf',binary);
const editedFixture=imported(original);editedFixture.transaction('Move',()=>editedFixture.transform([editedFixture.entities[0].id],M.translation(10,0,0)));fs.writeFileSync('tests/results/source-edited-fixture.dxf',S.exportPreserved(editedFixture).bytes);
console.log(`Source documents: ${tests.length-failed}/${tests.length} passed`);process.exitCode=failed?1:0;
