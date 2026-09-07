/* Run: node tests/core.test.js — no npm dependencies. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
for(const f of ['math','geometry','model','csg','exchange','examples'])require('../src/'+f+'.js');
const K=globalThis.Kestrel,{V,M,TAU}=K.Math,G=K.Geo,X=K.Exchange;
const results=[];let failures=0;
function test(name,fn){try{fn();results.push({name,status:'passed'});console.log('PASS',name);}catch(error){failures++;results.push({name,status:'failed',error:error.message});console.error('FAIL',name,'\n ',error.stack);}}
function near(a,b,epsilon=1e-6){assert.ok(Math.abs(a-b)<=epsilon,`${a} != ${b} (tolerance ${epsilon})`);}
function vec(a,b,eps=1e-6){assert.equal(a.length,b.length);a.forEach((v,i)=>near(v,b[i],eps));}
function drawing(entities=[]){const d=new K.Drawing('Test drawing');entities.forEach(e=>d.add(e));return d;}
const square=[[0,0,0],[10,0,0],[10,10,0],[0,10,0]];
const triangle=[[0,0,0],[10,0,0],[0,10,0]];

test('vector cross product and normal',()=>{vec(V.cross([1,0,0],[0,1,0]),[0,0,1]);vec(V.norm([0,3,4]),[0,.6,.8]);});
test('matrix inverse preserves transformed 3D points',()=>{const m=M.multiply(M.translation(1e6,-5,72),M.multiply(M.rotation(1.3,[2,3,4]),M.scale(2,3,4)));vec(M.point(M.inverse(m),M.point(m,[17,-9,6])),[17,-9,6],1e-8);});
test('matrix rotation about an arbitrary center',()=>vec(M.point(M.around([5,5,0],M.rotation(Math.PI/2)),[10,5,0]),[5,10,0]));
test('singular matrix inverse returns null',()=>assert.equal(M.inverse(M.scale(0)),null));
test('camera projection/unprojection in orthographic top and iso',()=>{const c=new K.Camera();c.resize(1200,750);for(const view of ['top','iso']){c.setView(view);c.zoom=3;c.target=[60,50,0];c.update();for(const p of [[0,0,0],[100,200,0],[-120,4,8]]){const s=c.project(p);vec(c.unproject(s[0],s[1],p[2]),p,1e-7);}}});
test('perspective camera projection/unprojection',()=>{const c=new K.Camera();c.setView('iso');c.perspective=true;c.update();const p=[100,100,5],s=c.project(p);vec(c.unproject(s[0],s[1],5),p,1e-5);});
test('zoom retains the mouse anchor',()=>{const c=new K.Camera();const p=c.unproject(100,100);c.zoomAt(2,100,100);vec(c.unproject(100,100),p,1e-7);});
test('camera pan moves content by the requested screen delta',()=>{const c=new K.Camera(),p=c.project([100,20,0]);c.pan(40,-30);vec(c.project([100,20,0]).slice(0,2),[p[0]+40,p[1]-30]);});
test('camera fit contains every vertex',()=>{const c=new K.Camera(),b=G.box([-100,-70,-50],230,140,200);c.setView('iso');c.fit(b.vertices);for(const p of b.vertices){const s=c.project(p);assert.ok(s[0]>0&&s[0]<c.width&&s[1]>0&&s[1]<c.height);}});
test('line intersections return segment parameters',()=>{const h=K.Math.lineIntersection([0,0],[10,10],[0,10],[10,0]);vec(h.point,[5,5,0]);near(h.t,.5);near(h.u,.5);});
test('concave polygon triangulation conserves area',()=>{const p=[[0,0,0],[10,0,0],[10,4,0],[4,4,0],[4,10,0],[0,10,0]];const triangles=K.Math.triangulate(p);assert.equal(triangles.length,4);near(triangles.reduce((s,t)=>s+Math.abs(K.Math.polygonArea(t.map(i=>p[i]))),0),64);});
test('triangulation also works in a vertical plane',()=>{const p=square.map(([x,y])=>[0,x,y]);assert.equal(K.Math.triangulate(p).length,2);});
test('circle path stays on analytic circle',()=>{const e={type:'CIRCLE',center:[5,7,3],radius:11};for(const p of G.path(e))near(V.dist(p,e.center),11);});
test('three-point arc goes through all supplied points',()=>{const a=[10,0,0],b=[0,10,0],c=[-10,0,0],e=G.arcThrough(a,b,c);near(e.radius,10);vec(e.center,[0,0,0]);near(K.Math.sweep(e.startAngle,e.endAngle),Math.PI);});
test('collinear three-point arc is rejected',()=>assert.throws(()=>G.arcThrough([0,0,0],[1,0,0],[2,0,0]),/collinear/));
test('bulge semicircle is tessellated at the correct radius',()=>{const p=G.path({type:'POLYLINE',points:[[0,0,0],[10,0,0]],bulges:[1,0]});assert.ok(p.length>4);for(const q of p)near(V.dist(q,[5,0,0]),5);assert.ok(p.some(q=>q[1]<-4.9));});
test('rational quadratic NURBS represents a quarter circle',()=>{const e={type:'SPLINE',degree:2,controlPoints:[[1,0,0],[1,1,0],[0,1,0]],weights:[1,Math.SQRT1_2,1]};for(const t of [0,.2,.5,.8,1])near(V.len(G.nurbs(e,t)),1,1e-9);vec(G.nurbs(e,1),[0,1,0],1e-8);});
test('nonuniform circle transform becomes an analytic ellipse',()=>{const e=G.transform({type:'CIRCLE',center:[0,0,0],radius:5},M.scale(2,1,1));assert.equal(e.type,'ELLIPSE');near(e.rx,10);near(e.ry,5);});
test('reflected mesh keeps positive volume',()=>near(G.volume(G.transform(G.box([0,0,0],10,10,10),M.scale(-1,1,1))),1000));
test('line offset is parallel and has requested distance',()=>{const e=G.offset({type:'LINE',points:[[0,0,0],[10,0,0]]},3);vec(e.points[0],[0,3,0]);vec(e.points[1],[10,3,0]);});
test('closed outward offset expands both polygon orientations',()=>{for(const points of [square,square.slice().reverse()]){const e=G.offset({type:'POLYLINE',points,closed:true},2);near(Math.abs(K.Math.polygonArea(e.points)),196);}});
test('nonpositive circle offset is rejected',()=>assert.throws(()=>G.offset({type:'CIRCLE',radius:5,center:[0,0,0]},-6),/non-positive/));
test('hatch line clipping stays inside its boundary',()=>{const g=G.geometry({type:'HATCH',points:square,pattern:'cross',spacing:2,angle:Math.PI/4});assert.ok(g.segments.length>8);for(const s of g.segments)for(const p of s)assert.ok(p[0]>=-1e-6&&p[0]<=10+1e-6&&p[1]>=-1e-6&&p[1]<=10+1e-6);});
test('solid hatch produces filled triangles',()=>assert.equal(G.geometry({type:'HATCH',points:square,pattern:'solid'}).triangles.length,2));
test('aligned dimension computes the true distance',()=>{const d=G.dimension({type:'DIMENSION',points:[[0,0,0],[3,4,0]],offset:10,textHeight:2,precision:3});assert.equal(d.text.text,'5.000');assert.equal(d.segments.length,7);});
test('box has expected volume and 12 feature edges',()=>{const e=G.box([0,0,0],10,20,30);near(G.volume(e),6000);assert.equal(G.geometry(e).segments.length,12);assert.equal(G.geometry(e).triangles.length,12);});
test('cylinder volume converges to analytic volume',()=>near(G.volume(G.cylinder([0,0,0],10,20,128)),Math.PI*100*20,3));
test('cone volume converges to analytic volume',()=>near(G.volume(G.cylinder([0,0,0],10,20,128,0)),Math.PI*100*20/3,1));
test('sphere volume converges to analytic volume',()=>near(G.volume(G.sphere([0,0,0],10,64,32)),4/3*Math.PI*1000,20));
test('torus volume converges to analytic volume',()=>near(G.volume(G.torus([0,0,0],10,2,96,32)),2*Math.PI**2*10*4,8));
test('positive and negative extrusion preserve enclosed volume',()=>{for(const h of [7,-7])near(G.volume(G.extrude(square,h,[0,0,1])),700);});
test('concave extrusion has valid cap area',()=>near(G.volume(G.extrude([[0,0,0],[10,0,0],[10,4,0],[4,4,0],[4,10,0],[0,10,0]],5)),320));
test('degenerate extrusion is rejected',()=>assert.throws(()=>G.extrude([[0,0,0],[1,0,0],[2,0,0]],2),/degenerate/));
test('revolved rectangular profile matches annular cylinder volume',()=>{const e=G.revolve([[5,0,0],[10,0,0],[10,0,20],[5,0,20]],[0,0,0],[0,0,1],360,128);near(G.volume(e),Math.PI*(100-25)*20,2);});
test('partial revolution includes closed caps',()=>{const e=G.revolve([[5,0,0],[10,0,0],[10,0,20],[5,0,20]],[0,0,0],[0,0,1],180,128);near(G.volume(e),Math.PI*(100-25)*10,1);});
for(const [op,volume]of [['union',1500],['subtract',500],['intersect',500]])test('BSP '+op+' of overlapping boxes',()=>near(G.volume(K.CSG.boolean(G.box([0,0,0],10,10,10),G.box([5,0,0],10,10,10),op)),volume,1e-6));
test('BSP disjoint intersection is empty',()=>assert.equal(K.CSG.boolean(G.box([0,0,0],10,10,10),G.box([20,0,0],10,10,10),'intersect').faces.length,0));
test('BSP subtraction operand order is meaningful',()=>{const big=G.box([0,0,0],10,10,10),small=G.box([2,2,2],3,3,3);near(G.volume(K.CSG.boolean(big,small,'subtract')),973);assert.equal(K.CSG.boolean(small,big,'subtract').faces.length,0);});
test('native round trip preserves entities and layers',()=>{const d=drawing([{type:'CIRCLE',center:[10,20,0],radius:5}]);d.camera=new K.Camera().serialize();assert.deepEqual(K.Drawing.from(d.serialize()).serialize(),d.serialize());});
test('transaction undo and redo restore exact geometry',()=>{const d=drawing();d.transaction('line',()=>d.add('LINE',{points:[[0,0,0],[10,0,0]]}));const id=d.entities[0].id;d.transaction('move',()=>d.transform([id],M.translation(5,7)));vec(d.entities[0].points[0],[5,7,0]);assert.equal(d.undo(),'move');vec(d.entities[0].points[0],[0,0,0]);assert.equal(d.redo(),'move');vec(d.entities[0].points[0],[5,7,0]);});
test('failed transaction rolls back atomically',()=>{const d=drawing();assert.throws(()=>d.transaction('bad',()=>{d.add('POINT',{position:[1,2,3]});throw Error('rollback');}),/rollback/);assert.equal(d.entities.length,0);assert.equal(d.undoStack.length,0);});
test('new edits invalidate redo history',()=>{const d=drawing();d.transaction('a',()=>d.add('POINT',{position:[1,0,0]}));d.undo();d.transaction('b',()=>d.add('POINT',{position:[2,0,0]}));assert.equal(d.redo(),null);});
test('selection order follows picking order for Boolean operands',()=>{const d=drawing([{type:'POINT',position:[0,0,0]},{type:'POINT',position:[1,0,0]}]);d.selection=new Set([d.entities[1].id,d.entities[0].id]);assert.equal(d.selected()[0],d.entities[1]);});
test('locked and hidden layers are not editable',()=>{const d=drawing([{type:'POINT',position:[0,0,0]}]),e=d.entities[0];d.layer(e).locked=true;assert.equal(d.editable(e),false);d.layer(e).locked=false;d.layer(e).visible=false;assert.equal(d.editable(e),false);});
test('duplicate and unsafe native identifiers are rejected',()=>{const d=drawing([{type:'POINT',position:[0,0,0]}]).serialize();d.entities.push(K.clone(d.entities[0]));assert.throws(()=>K.validateProject(d),/duplicate/);d.entities.pop();d.entities[0].id='\" onclick=\"bad';assert.throws(()=>K.validateProject(d),/identifier/);});
test('native malformed coordinates, mesh indices and camera are rejected',()=>{const d=drawing([G.box([0,0,0],1,1,1)]).serialize();const bad=K.clone(d);bad.entities[0].vertices[0][0]=Infinity;assert.throws(()=>K.validateProject(bad),/coordinates/);d.entities[0].faces[0][0]=999;assert.throws(()=>K.validateProject(d),/face/);const p=drawing().serialize();p.camera={target:[0,0,0],zoom:-1,yaw:0,pitch:0};assert.throws(()=>K.validateProject(p),/camera/);});
test('spatial index finds screen-near geometry',()=>{const d=drawing([{type:'LINE',points:[[0,0,0],[100,0,0]]}]),c=new K.Camera(),i=new K.SpatialIndex();i.build(d,c);const p=c.project([50,0,0]);assert.equal(i.near(p[0],p[1],2).length,1);assert.equal(i.near(-10000,-10000).length,0);});
function analyticDrawing(){return drawing([{type:'LINE',points:[[0,0,0],[20,30,4]]},{type:'POLYLINE',points:square,closed:true,bulges:[.3,0,0,0]},{type:'CIRCLE',center:[30,40,0],radius:8},{type:'ARC',center:[50,40,0],radius:9,startAngle:.2,endAngle:2.1},{type:'ELLIPSE',center:[60,40,0],rx:12,ry:5,rotation:.3},{type:'SPLINE',controlPoints:[[0,0,0],[5,10,0],[10,-5,0],[20,0,0]],degree:3},{type:'SPLINE',degree:2,controlPoints:[[1,0,0],[1,1,0],[0,1,0]],weights:[1,Math.SQRT1_2,1]},{type:'TEXT',position:[5,5,0],text:'Kestrel · Żółć Ω ± ⌀',height:2,rotation:.4},{type:'HATCH',points:square,pattern:'cross',spacing:2,angle:.3},{type:'DIMENSION',points:[[0,0,0],[50,0,0]],offset:-10,textHeight:2,precision:2},G.box([70,0,0],10,10,10)]);}
let roundtrip;
test('DXF writer emits complete ASCII R2000 sections',()=>{const text=X.writeDXF(analyticDrawing());assert.ok(text.includes('AC1015'));assert.ok(text.endsWith('0\nEOF\n'));fs.writeFileSync(path.join(__dirname,'fixtures','analytic-roundtrip.dxf'),text);roundtrip=X.parseDXF(text);assert.deepEqual(roundtrip.report.skipped,{});});
test('DXF imports unweighted and rational splines as valid native entities',()=>{const d=K.Drawing.from(roundtrip.data);assert.equal(d.entities.filter(e=>e.type==='SPLINE').length,2);for(const e of d.entities.filter(e=>e.type==='SPLINE'))assert.ok(G.path(e).every(p=>p.every(Number.isFinite)));});
test('DXF round trip preserves units, Unicode and layer names',()=>{const d=K.Drawing.from(roundtrip.data);assert.equal(d.units,'mm');assert.equal(d.entities.find(e=>e.type==='TEXT').text,'Kestrel · Żółć Ω ± ⌀');assert.equal(d.layer(d.entities[0]).name,'A-WALL');});
test('DXF conics survive tilted OCS and reflections',()=>{for(const entity of [{type:'CIRCLE',center:[10,20,30],radius:12},{type:'ARC',center:[10,20,30],radius:12,startAngle:.2,endAngle:2.5}]){const e=G.transform(entity,M.multiply(M.rotation(.7,[1,2,3]),M.scale(-1,1,1))),d=drawing([e]),out=X.parseDXF(X.writeDXF(d)).data.entities[0];const a=G.path(e),b=G.path(out);assert.equal(a.length,b.length);if(e.type==='ARC')for(let i=0;i<a.length;i++)vec(a[i],b[i],1e-6);else {near(V.dist(e.center,out.center),0);near(out.radius,e.radius);}}});
test('binary DXF input is explicitly rejected',()=>assert.throws(()=>X.parseDXF('AutoCAD Binary DXF\r\n'),/Binary DXF/));
test('malformed DXF group code is rejected',()=>assert.throws(()=>X.parseDXF('nonsense\nSECTION\n'),/group code/));
test('unsupported DXF entity types are reported',()=>{const r=X.parseDXF('0\nSECTION\n2\nENTITIES\n0\n3DSOLID\n8\n0\n0\nENDSEC\n0\nEOF\n');assert.equal(r.report.skipped['3DSOLID'],1);assert.equal(r.data.entities.length,0);});
test('SVG escapes text and attribute values',()=>{const d=drawing([{type:'TEXT',position:[0,0,0],text:'<script>alert("x")</script> &',height:4}]);const svg=X.writeSVG(d);assert.ok(!svg.includes('<script>'));assert.ok(svg.includes('&lt;script&gt;'));assert.ok(svg.includes('viewBox="0 0 1600 1000"'));});
test('both example projects validate and export',()=>{for(const [name,doc]of [['courtyard',K.Examples.courtyard()],['fixture',K.Examples.fixture()]]){K.Drawing.from(doc.serialize());const text=X.writeDXF(doc),parsed=X.parseDXF(text);assert.deepEqual(parsed.report.skipped,{});K.Drawing.from(parsed.data);fs.writeFileSync(path.join(__dirname,'..','examples',name+'.kcad'),JSON.stringify(doc.serialize()));fs.writeFileSync(path.join(__dirname,'..','examples',name+'.dxf'),text);}});

if(fs.existsSync(path.join(__dirname,'fixtures','external.dxf')))test('independent producer DXF imports valid geometry',()=>{const r=X.parseDXF(fs.readFileSync(path.join(__dirname,'fixtures','external.dxf')));const d=K.Drawing.from(r.data);assert.ok(d.entities.length>20);fs.writeFileSync(path.join(__dirname,'results','external-import.json'),JSON.stringify({data:d.serialize(),report:r.report},null,2));});
fs.writeFileSync(path.join(__dirname,'results','core-results.json'),JSON.stringify({suite:'dependency-free Node core tests',passed:results.length-failures,failed:failures,tests:results},null,2));
console.log(`\n${results.length-failures}/${results.length} tests passed.`);process.exitCode=failures?1:0;
