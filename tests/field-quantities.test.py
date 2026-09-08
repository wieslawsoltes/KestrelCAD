#!/usr/bin/env python3
"""Actual OCCT-backed field quantities, transforms, units, history and schedules."""
from pathlib import Path
import json, subprocess, sys
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'tools'))
import cadquery as cq
import kernel
OUT=ROOT/'tests/results';OUT.mkdir(exist_ok=True)
box=cq.Solid.makeBox(20,30,10)
hollow=box.cut(cq.Solid.makeBox(10,20,4).translate((5,5,3)))
shapes={'box':box,'hollow':hollow,'sphere':cq.Solid.makeSphere(5),'sheet':cq.Face.makePlane(20,30)}
fixtures={key:kernel.pack(shape,.1) for key,shape in shapes.items()}
# These independent native values exercise curved material and a cavity, not meshes.
fixtures['expected']={key:{'volume':shape.Volume() if shape.Solids() else 0,'area':shape.Area()} for key,shape in shapes.items()}
modules=['math','geometry','model','exchange','production','kernel','constraints','spatial-constraints','dynamic-blocks','fonts','unicode-bidi','mtext','source-document','productivity','fields']
code=r'''
const fs=require('fs'),assert=require('assert/strict');
for(const m of MODULES)require('./src/'+m+'.js');
const K=Kestrel,F=K.Fields,M=K.Math.M,data=JSON.parse(fs.readFileSync(0,'utf8')),tests=[];
const near=(a,b)=>assert(Math.abs(a-b)<=Math.max(1,Math.abs(b))*1e-9,`${a} != ${b}`);
function fixture(key='box'){const doc=new K.Drawing();doc.transaction('Fixture',()=>{doc.units='mm';doc.add({...K.Kernel.body(data[key]),id:'body'});doc.add('TEXT',{id:'label',position:[0,0,0],height:3,text:''});});return doc;}
function bind(doc,property='volume',extra={},field={}){F.setBinding(doc,'label',{version:1,target:'text',template:'{{Value}}',precision:6,trimZeros:true,sources:[{name:'Value',kind:'object',entity:'body',property,...extra}],...field});return doc.byId.get('label').text;}
function test(name,fn){try{fn();tests.push({name,status:'passed'});console.log('PASS',name);}catch(e){tests.push({name,status:'failed',error:e.stack});console.error('FAIL',name,e.stack);}}
test('body volume and surface area equal actual kernel values',()=>{const d=fixture();near(+bind(d),6000);near(+bind(d,'surfaceArea'),2200);});
test('curved solid quantities do not use the display tessellation',()=>{const d=fixture('sphere');near(+bind(d),data.expected.sphere.volume);near(+bind(d,'surfaceArea'),data.expected.sphere.area);});
test('cavity material quantities equal actual native properties',()=>{const d=fixture('hollow');near(+bind(d),data.expected.hollow.volume);near(+bind(d,'surfaceArea'),data.expected.hollow.area);});
test('uniform placement scales volume cubically and area quadratically',()=>{const d=fixture();d.transaction('Scale',()=>d.transform(['body'],M.scale(2)));near(+bind(d),48000);near(+bind(d,'surfaceArea'),8800);assert.equal(d.byId.get('body').solid.brep,data.box.brep);});
test('reflection preserves positive quantities',()=>{const d=fixture();d.transaction('Reflect',()=>d.transform(['body'],M.scale(-2,2,2)));near(+bind(d),48000);near(+bind(d,'surfaceArea'),8800);});
test('general affine volume uses determinant, not a sampled bounding box',()=>{const d=fixture(),m=M.scale(2,3,4);m[4]=.7;d.transaction('Affine',()=>d.transform(['body'],m));near(+bind(d),144000);assert.equal(d.byId.get('body').solid.brep,data.box.brep);});
test('nonuniform surface area authoring rejects without editing the drawing',()=>{const d=fixture();d.transaction('Nonuniform',()=>d.transform(['body'],M.scale(2,3,4)));const before=d.snapshot();assert.throws(()=>bind(d,'surfaceArea'),/native recomputation/);assert.equal(d.snapshot(),before);});
test('a later unsupported placement becomes unresolved and undo restores quantity',()=>{const d=fixture();bind(d,'surfaceArea');d.transaction('Scale',()=>d.transform(['body'],M.scale(2,3,4)));assert.equal(d.byId.get('label').text,'####');assert(d.fieldReport[0].error.includes('nonuniform'));d.undo();near(+d.byId.get('label').text,2200);});
test('volume converts output units by the cube of length scale',()=>{const d=fixture();near(+bind(d,'volume',{units:'cm'}),6);});
test('surface area converts output units by the square of length scale',()=>{const d=fixture();near(+bind(d,'surfaceArea',{units:'cm'}),22);});
test('unitless drawings refuse fabricated physical quantities',()=>{const d=fixture();d.units='unitless';assert.throws(()=>bind(d,'volume',{units:'cm'}),/Unitless/);});
test('sheets expose area but never a fictitious solid volume',()=>{const d=fixture('sheet');near(+bind(d,'surfaceArea'),data.expected.sheet.area);assert.throws(()=>bind(d),/closed native solid/);});
test('plain meshes are not treated as authoritative native geometry',()=>{const d=fixture();delete d.byId.get('body').solid;assert.throws(()=>bind(d),/authoritative/);});
test('projective placements cannot use affine native mass formulas',()=>{const d=fixture();d.byId.get('body').solid.transform[3]=.001;assert.throws(()=>bind(d),/affine/);});
test('corrupted display mesh is rejected instead of remeasured',()=>{const d=fixture(),e=d.byId.get('body');e.vertices[0][0]+=.01;assert.throws(()=>F.nativeQuantity(e,'volume'),/edited independently/);});
test('source scaling and its native field form one undo redo step',()=>{const d=fixture();bind(d);const n=d.undoStack.length;d.transaction('Scale',()=>d.transform(['body'],M.scale(2)));near(+d.byId.get('label').text,48000);assert.equal(d.undoStack.length,n+1);d.undo();near(+d.byId.get('label').text,6000);d.redo();near(+d.byId.get('label').text,48000);});
test('native load refreshes derived quantities without changing BREP bytes',()=>{const d=fixture();bind(d);const serialized=d.serialize();serialized.entities.find(e=>e.id==='label').text='obsolete';const restored=K.Drawing.from(serialized);near(+restored.byId.get('label').text,6000);assert.equal(restored.byId.get('body').solid.brep,data.box.brep);});
test('a complete copy remaps native quantity references',()=>{const d=fixture();bind(d);let ids;d.transaction('Copy',()=>ids=d.transform(['body','label'],M.scale(2),true));near(+d.byId.get(ids[1]).text,48000);assert.equal(d.byId.get(ids[1]).fieldBindings[0].sources[0].entity,ids[0]);});
test('linked native schedules retain squared and cubed output units',()=>{const d=fixture();const table=F.linkedTable(d,['body'],[0,0,0],{columns:[{label:'Volume cm³',property:'volume',units:'cm'},{label:'Area cm²',property:'surfaceArea',units:'cm'}]});assert.deepEqual(table.cells[1],['6','22']);d.transaction('Scale',()=>d.transform(['body'],M.scale(2)));assert.deepEqual(table.cells[1],['48','88']);});
test('aggregate native volumes remain raw numeric formula operands',()=>{const d=fixture();d.transaction('Copy',()=>{const body=K.Geo.transform(d.byId.get('body'),M.scale(2));d.add({...body,id:'other'});});F.setBinding(d,'label',{version:1,target:'text',template:'{{Result}}',precision:3,sources:[{name:'Q',kind:'aggregate',entities:['body','other'],method:'sum',property:'volume',units:'cm'}],expression:'Q / 2'});assert.equal(d.byId.get('label').text,'27.000');});
test('DXF exporter refreshes quantities rather than writing stale field text',()=>{const d=fixture();bind(d,'volume',{units:'cm'},{template:'Volume {{Value}} cm3'});const raw=d.serialize();raw.entities.find(e=>e.id==='label').text='stale';const out=K.Exchange.writeDXF(raw);assert(out.includes('Volume 6 cm3'));assert.equal(raw.entities.find(e=>e.id==='label').text,'stale');});
const failed=tests.filter(t=>t.status==='failed').length;
fs.writeFileSync('tests/results/field-quantities-results.json',JSON.stringify({passed:tests.length-failed,failed,basis:'actual OCCT-created native geometry',tests},null,2));
console.log('RESULT',tests.length-failed,'passed',failed,'failed');process.exitCode=Number(!!failed);
'''.replace('MODULES',json.dumps(modules))
r=subprocess.run(['node','-e',code],input=json.dumps(fixtures),text=True,cwd=ROOT,timeout=35)
sys.exit(r.returncode)
