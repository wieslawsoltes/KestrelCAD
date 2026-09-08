'use strict';
const fs=require('node:fs'),assert=require('node:assert/strict');
for(const n of ['math','geometry','model','exchange','production','kernel','native-curves'])require('../src/'+n+'.js');
const K=globalThis.Kestrel,C=K.NativeCurves,N=K.Kernel,G=K.Geo,tests=[];
function test(name,fn){try{fn();tests.push({name,status:'passed'});console.log('PASS',name);}catch(e){tests.push({name,status:'failed',error:e.stack});console.error('FAIL',name,e);}}
function near(a,b,epsilon=1e-9){assert(Math.abs(a-b)<=epsilon*Math.max(1,Math.abs(b)),[a,b]);}
const line={type:'LINE',points:[[0,0,0],[5,0,0]]};
const circle={type:'CIRCLE',center:[1,2,3],axisX:[5,0,0],axisY:[0,5,0],normal:[0,0,1],radius:5};
const spline={type:'SPLINE',controlPoints:[[0,0,0],[1,2,0],[3,0,0]],degree:2,knots:[0,0,0,1,1,1],weights:[1,.7,1],closed:false};
function native(){return N.body({provider:'OCCT',valid:true,brep:'QQ==',version:'synthetic-contract-fixture',volume:1,area:6,solidCount:1,tolerance:.1,mesh:G.box([0,0,0],1,1,1),edges:[{index:0,type:'LINE'}],faces:[],edgePolylines:[]});}
function fixture(){const d=new K.Drawing(),e=d.add(native());return {d,e,s:C.prepare(d,[e])};}
function report(){return {provider:'OCCT',operation:'extract-curves',schema:1,mode:'edges',bodyCount:1,curveCount:1,degenerateEdges:0,curves:[{sourceIndex:0,edgeIndex:0,entity:K.clone(line)}]};}
test('accept native analytic LINE',()=>assert.deepEqual(C.curve(line),line));
test('accept native full circle',()=>assert.deepEqual(C.curve(circle),circle));
test('accept finite circular arc',()=>C.curve({...circle,type:'ARC',startAngle:1,endAngle:2}));
test('accept oriented elliptical arc',()=>{const e={...circle,type:'ELLIPSE',axisY:[0,2,0],rx:5,ry:2,startAngle:0,endAngle:1};delete e.radius;C.curve(e);});
test('reject elliptic start without end trim',()=>{const e={...circle,type:'ELLIPSE',rx:5,ry:5,startAngle:1};delete e.radius;assert.throws(()=>C.curve(e));});
test('accept clamped rational spline',()=>assert.deepEqual(C.curve(spline),spline));
test('reject closed spline with separated endpoints',()=>assert.throws(()=>C.curve({...spline,closed:true})));
test('reject raw mesh carrier',()=>assert.throws(()=>C.curve({type:'MESH',vertices:[],faces:[]})));
test('reject injected entity identity',()=>assert.throws(()=>C.curve({...line,id:'existing'})));
test('reject nonfinite geometry before JSON cloning',()=>assert.throws(()=>C.curve({...line,points:[[0,0,0],[Infinity,0,0]]})));
test('reject mismatched analytic radius',()=>assert.throws(()=>C.curve({...circle,radius:7})));
test('reject nonorthogonal conic axes',()=>assert.throws(()=>C.curve({...circle,axisY:[3,4,0]})));
test('reject reversed curve parameter interval',()=>assert.throws(()=>C.curve({...circle,type:'ARC',startAngle:2,endAngle:1})));
test('reject empty knot range',()=>assert.throws(()=>C.curve({...spline,knots:[0,0,0,0,0,0]})));
test('reject nonclamped knots',()=>assert.throws(()=>C.curve({...spline,knots:[0,0,.1,.8,1,1]})));
test('reject excessive knot multiplicity',()=>assert.throws(()=>C.curve({...spline,knots:[0,0,0,0,1,1]})));
test('reject rational weight size mismatch',()=>assert.throws(()=>C.curve({...spline,weights:[1,2]})));
test('reject ill-conditioned rational weights',()=>assert.throws(()=>C.curve({...spline,weights:[1,1e-15,1]})));
test('exact spline endpoint is not clamped away from its final pole',()=>assert.deepEqual(G.nurbs(spline,1),[3,0,0]));
test('tiny valid knot spans are evaluated rather than discarded',()=>{const e={type:'SPLINE',degree:1,controlPoints:[[0,0,0],[2,0,0],[3,0,0]],knots:[0,0,1e-10,1,1]};near(G.nurbs(e,5e-11)[0],1);});
test('rational quarter circle retains locus',()=>{const e={...spline,controlPoints:[[1,0,0],[1,1,0],[0,1,0]],weights:[1,Math.SQRT1_2,1]};for(let i=0;i<=10;i++){const p=G.nurbs(e,i/10);near(p[0]*p[0]+p[1]*p[1],1);}});
test('native spline profile transfers control data, not sample points',()=>{const p=N.profile(spline);assert.equal(p.type,'spline');assert.deepEqual(p.weights,[1,.7,1]);p.controlPoints[0][0]=10;assert.equal(spline.controlPoints[0][0],0);});
test('legacy circle profile schema remains compatible',()=>assert.equal(N.profile(circle).type,'circle'));
test('partial ellipse is no longer silently used as a full closed profile',()=>assert.throws(()=>N.profile({type:'ELLIPSE',center:[0,0,0],rx:5,ry:2,startAngle:0,endAngle:1}),/open/));
test('spline profile accepts generated uniform knots',()=>assert.equal(N.profile({type:'SPLINE',points:[[0,0,0],[1,1,0],[3,0,0]]}).knots.length,6));
test('empty source selection rejects',()=>{const f=fixture();assert.throws(()=>C.prepare(f.d,[]));});
test('locked source is allowed for read-only extraction',()=>{const f=fixture();f.d.layer(f.e).locked=true;assert(C.prepare(f.d,[f.e]));});
test('hidden source rejects',()=>{const f=fixture();f.e.hidden=true;assert.throws(()=>C.prepare(f.d,[f.e]));});
test('mesh-only source rejects',()=>{const f=fixture();delete f.e.solid;assert.throws(()=>C.prepare(f.d,[f.e]));});
test('captured native geometry is independent',()=>{const f=fixture();f.s.inputs[0].brep='Qg==';assert.equal(f.e.solid.brep,'QQ==');});
test('invalid section normal rejects before request',()=>assert.throws(()=>C.options({mode:'section',origin:[0,0,0],normal:[0,0,0]})));
test('duplicate topology indices reject',()=>assert.throws(()=>C.options({edges:[1,1]})));
test('wrong source index rejects response',()=>{const f=fixture(),r=report();r.curves[0].sourceIndex=1;assert.throws(()=>C.validate(r,f.s));});
test('incomplete edge enumeration rejects response',()=>{const f=fixture(),r=report();r.curves=[];r.curveCount=0;assert.throws(()=>C.validate(r,f.s));});
test('unknown edge index rejects response',()=>{const f=fixture(),r=report();r.curves[0].edgeIndex=7;assert.throws(()=>C.validate(r,f.s));});
test('retention keeps authoritative source unchanged',()=>{const f=fixture(),before=JSON.stringify(f.e);C.retain(f.s,report());assert.equal(f.d.entities.length,2);assert.equal(JSON.stringify(f.e),before);assert(!f.d.entities[1].solid);});
test('extracted curves use the current layer',()=>{const f=fixture();f.d.currentLayer='construction';const added=C.retain(f.s,report());assert.equal(added[0].layer,'construction');});
test('extracted curves support one-step undo/redo',()=>{const f=fixture();C.retain(f.s,report());f.d.undo();assert.equal(f.d.entities.length,1);f.d.redo();assert.equal(f.d.entities.length,2);});
test('stale extraction cannot overwrite newer edits',()=>{const f=fixture();f.d.transaction('Edit',()=>f.d.add('POINT',{position:[0,0,0]}));assert.throws(()=>C.retain(f.s,report()),/changed/);});
test('locked output layer blocks writes',()=>{const f=fixture();f.d.layer(f.d.currentLayer).locked=true;assert.throws(()=>C.retain(f.s,report()),/unlocked/);});
test('invalid output rejects atomically',()=>{const f=fixture(),r=report(),before=f.d.snapshot();r.curves[0].entity.points[0][0]=NaN;assert.throws(()=>C.retain(f.s,r));assert.equal(f.d.snapshot(),before);});
test('no-section hit adds no history record',()=>{const f=fixture(),s=C.prepare(f.d,[f.e],{mode:'section',origin:[0,0,0],normal:[0,0,1]}),r={...report(),mode:'section',curves:[],curveCount:0},before=f.d.snapshot(),n=f.d.undoStack.length;assert.deepEqual(C.retain(s,r),[]);assert.equal(f.d.snapshot(),before);assert.equal(f.d.undoStack.length,n);});
test('native serialization preserves editable rational data',()=>{const d=new K.Drawing();d.add(spline);const e=K.Drawing.from(d.serialize()).entities[0];assert.deepEqual(e.weights,spline.weights);assert.deepEqual(e.knots,spline.knots);});
for(const degree of [0,1.5,11,Infinity])test('reject invalid explicit spline profile degree '+degree,()=>assert.throws(()=>N.profile({...spline,degree})));
test('DXF knot tolerance remains below very small valid knot spans',()=>{const d=new K.Drawing();d.add('SPLINE',{degree:1,controlPoints:[[0,0,0],[2,0,0],[3,0,0]],knots:[0,0,1e-10,1,1]});const tags=K.Exchange.writeDXF(d).split('\n');const start=tags.indexOf('AcDbSpline');let found;for(let i=start+1;i<tags.length-1;i+=2)if(tags[i]==='42'){found=Number(tags[i+1]);break;}assert(found>0&&found<1e-15,found);});
const failed=tests.filter(t=>t.status==='failed').length;fs.mkdirSync('tests/results',{recursive:true});fs.writeFileSync('tests/results/native-curves-client-results.json',JSON.stringify({passed:tests.length-failed,failed,tests},null,2));console.log('RESULT',tests.length-failed,'passed',failed,'failed');if(failed)process.exitCode=1;
