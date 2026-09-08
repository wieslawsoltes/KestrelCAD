'use strict';
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
for(const file of ['math','geometry','model','exchange','production','kernel','constraints','spatial-constraints'])vm.runInThisContext(fs.readFileSync(path.join(__dirname,'../src',file+'.js'),'utf8'),{filename:file+'.js'});
const K=globalThis.Kestrel,C=K.SpatialConstraints,{V,M}=K.Math,results=[];
function test(name,fn){try{fn();results.push({name,status:'passed'});console.log('PASS',name);}catch(e){results.push({name,status:'failed',error:e.stack});console.error('FAIL',name,e.stack);}}
function near(a,b,t=1e-6){assert(Math.abs(a-b)<=t*Math.max(1,Math.abs(b)),`${a} != ${b}`);}
function fixture(type='slider',value=0,limits={enabled:true,min:-10,max:30},drive){
 const d=new K.Drawing();d.currentLayer='0';const e=d.add(K.Geo.box([0,0,0],10,20,30));
 d.transform([e.id],type==='slider'?M.translation(0,0,value):M.rotation(value*Math.PI/180,[0,0,1]));
 // A body-local origin is defined at the coordinate frame, not the box corner.
 d.byId.get(e.id).constraintFrame=Array.from(type==='slider'?M.translation(0,0,value):M.rotation(value*Math.PI/180,[0,0,1]));
 const spec={type,a:{entity:e.id,local:[0,0,0]},b:{world:[0,0,0]},...(limits?{limits}:{}),...(drive?{drive}:{})};
 C.add(d,spec);return{d,id:e.id,get c(){return C.state(d).constraints[0];}};
}
const report=f=>C.solve(f.d,{apply:false}),coordinate=f=>report(f).joints[0].coordinate;
for(const [type,start,want]of [['slider',-25,-10],['slider',55,30],['hinge',-55,-10],['hinge',70,30]])test(`${type} outside interval converges to ${want} stop`,()=>{const f=fixture(type,start);near(coordinate(f),want);near(K.Geo.volume(f.d.byId.get(f.id)),6000);});
for(const type of ['slider','hinge']){
 test(`${type} interior remains free and preserves current placement`,()=>{const f=fixture(type,7);near(coordinate(f),7);assert.equal(report(f).degreesOfFreedom,1);assert.equal(report(f).inequalities,2);});
 test(`${type} bound allows inward travel and reports unilateral stop`,()=>{const f=fixture(type,30),r=report(f);assert.equal(r.degreesOfFreedom,1);assert(r.joints[0].atMaximum);f.d.transaction('Move inward',()=>f.d.transform([f.id],type==='slider'?M.translation(0,0,-4):M.rotation(-4*Math.PI/180,[0,0,1])));near(coordinate(f),26);assert(!report(f).joints[0].atMaximum);});
 test(`${type} equal bounds lock one remaining coordinate`,()=>{const f=fixture(type,9,{enabled:true,min:15,max:15});near(coordinate(f),15);assert.equal(report(f).degreesOfFreedom,0);assert.equal(report(f).inequalities,0);});
 test(`${type} position driver removes remaining freedom`,()=>{const f=fixture(type,0,undefined,{enabled:true,value:20});near(coordinate(f),20);assert.equal(report(f).degreesOfFreedom,0);});
 test(`${type} disabled driver restores free travel`,()=>{const f=fixture(type,0,undefined,{enabled:true,value:20});f.d.transaction('Release driver',()=>f.c.drive.enabled=false);assert.equal(report(f).degreesOfFreedom,1);});
 test(`${type} one-sided interval clamps lower bound only`,()=>{const f=fixture(type,-50,{enabled:true,min:5});near(coordinate(f),5);assert.equal(report(f).inequalities,1);});
 test(`${type} disabled interval retains values without moving geometry`,()=>{const f=fixture(type,50,{enabled:false,min:0,max:10});near(coordinate(f),50);assert.equal(report(f).inequalities,0);});
 test(`${type} parameter update moves actual geometry`,()=>{const f=fixture(type,7);f.d.transaction('Parameters',()=>{C.state(f.d).parameters=[{name:'Stop',expression:'25'},{name:'Position',expression:'Stop / 2'}];f.c.limits.max='Stop';f.c.drive={enabled:true,value:'Position'};});near(coordinate(f),12.5);f.d.transaction('Change parameter',()=>C.state(f.d).parameters[0].expression='20');near(coordinate(f),10);});
 test(`${type} conflicting drive has atomic rollback`,()=>{const f=fixture(type,7),before=f.d.snapshot(),undo=f.d.undoStack.length;assert.throws(()=>f.d.transaction('Bad drive',()=>f.c.drive={enabled:true,value:100}),/outside/);assert.equal(f.d.snapshot(),before);assert.equal(f.d.undoStack.length,undo);});
 test(`${type} undo redo restores limits and solved pose`,()=>{const f=fixture(type,7),before=f.d.snapshot();f.d.transaction('Drive',()=>f.c.drive={enabled:true,value:20});const after=f.d.snapshot();f.d.undo();assert.equal(f.d.snapshot(),before);f.d.redo();assert.equal(f.d.snapshot(),after);});
 test(`${type} save load preserves intervals, expressions and driver`,()=>{const f=fixture(type,0,undefined,{enabled:true,value:20});assert.equal(K.Drawing.from(f.d.serialize()).snapshot(),f.d.snapshot());});
}
test('signed hinge driver supports negative rotation',()=>{const f=fixture('hinge',30,{enabled:true,min:-90,max:90},{enabled:true,value:-35});near(coordinate(f),-35);near(M.point(C.frame(f.d.byId.get(f.id)),[1,0,0])[1],Math.sin(-35*Math.PI/180));});
test('tilted 3D datum frames measure twist about their actual axis',()=>{const f=fixture('hinge',20,{enabled:true,min:-45,max:45}),rot=M.rotation(.7,[1,2,3]);f.d.transaction('Rotate world assembly',()=>{f.d.transform([f.id],rot);f.c.b.axis=M.point(rot,[0,0,1],0);f.c.b.xaxis=M.point(rot,[1,0,0],0);});near(coordinate(f),20);});
test('hinge can align an initially orthogonal rigid frame before driving twist',()=>{const f=fixture('hinge',0,{enabled:false,min:-70,max:70});f.d.transaction('Tilt and drive',()=>{f.d.transform([f.id],M.rotation(Math.PI/2,[0,1,0]));f.c.drive={enabled:true,value:25};});near(coordinate(f),25);});
test('slider limits preserve physical units',()=>{const f=fixture('slider',0,{enabled:true,min:0,max:50.8},{enabled:true,value:25.4});f.d.transaction('Unit conversion',()=>{C.convertUnits(f.d,'in',1/25.4,true);f.d.transform([f.id],M.scale(1/25.4));f.d.units='in';});near(coordinate(f),1);near(report(f).joints[0].maximum,2);});
test('hinge limits remain angular through physical units conversion',()=>{const f=fixture('hinge',0,{enabled:true,min:-90,max:90},{enabled:true,value:45});f.d.transaction('Unit conversion',()=>{C.convertUnits(f.d,'in',1/25.4,true);f.d.transform([f.id],M.scale(1/25.4));f.d.units='in';});near(coordinate(f),45);});
test('large slider driver participates in solver normalization',()=>{const f=fixture('slider',0,{enabled:true,min:0,max:1e8},{enabled:true,value:1e7});near(coordinate(f),1e7);});
test('diagnostics never apply candidate geometry',()=>{const f=fixture('slider',4),before=f.d.snapshot();report(f);assert.equal(f.d.snapshot(),before);});
test('locked rigid body cannot be pulled across a travel stop',()=>{const f=fixture('slider',20),before=f.d.snapshot();assert.throws(()=>f.d.transaction('Locked conflict',()=>{f.d.layers.find(l=>l.id==='0').locked=true;f.c.limits.max=10;}));assert.equal(f.d.snapshot(),before);});
test('suppression retains limits while allowing unrestricted motion',()=>{const f=fixture('slider',7);f.d.transaction('Suppress',()=>f.c.suppressed=true);f.d.transaction('Move',()=>f.d.transform([f.id],M.translation(0,0,90)));near(C.frame(f.d.byId.get(f.id))[14],97);assert.equal(f.c.limits.max,30);});
test('parameter-dependent limit conflict rolls back parameter and geometry',()=>{const f=fixture('slider',7);f.d.transaction('Parameters',()=>{C.state(f.d).parameters=[{name:'Stop',expression:'30'}];f.c.limits.max='Stop';f.c.drive={enabled:true,value:20};});const before=f.d.snapshot();assert.throws(()=>f.d.transaction('Bad parameter',()=>C.state(f.d).parameters[0].expression='10'));assert.equal(f.d.snapshot(),before);});
for(const [label,change]of [
 ['reversed bounds',c=>c.limits={enabled:true,min:20,max:10}],
 ['no bounds',c=>c.limits={enabled:true}],
 ['bad toggle',c=>c.limits={enabled:1,min:0}],
 ['unknown field',c=>c.limits={enabled:true,min:0,rest:3}],
 ['unsafe expression',c=>c.limits={enabled:true,min:'globalThis()'}],
 ['nonfinite bound',c=>c.limits={enabled:true,min:'1e999'}],
 ['invalid driver',c=>c.drive={enabled:'true',value:0}],
 ['missing driver expression',c=>c.drive={enabled:true}],
 ['wrong relation',c=>c.type='fastened']
])test('invalid '+label+' rejects without state loss',()=>{const f=fixture(),before=f.d.snapshot();assert.throws(()=>f.d.transaction('Invalid',()=>change(f.c)));assert.equal(f.d.snapshot(),before);});
test('hinge wrap seam is explicitly rejected rather than misinterpreted',()=>assert.throws(()=>fixture('hinge',0,{enabled:true,min:-180,max:180}),/strictly/));
test('collinear transverse axis is rejected only for configured hinge',()=>{const f=fixture('hinge',0);assert.throws(()=>f.d.transaction('Bad axis',()=>f.c.a.xaxis=[0,0,1]),/independent/);});
test('flexible anchors cannot masquerade as limited rigid joints',()=>{const d=new K.Drawing(),e=d.add('POINT',{position:[0,0,0]});assert.throws(()=>C.add(d,{type:'hinge',a:{entity:e.id},b:{world:[0,0,0]},limits:{enabled:true,min:-45,max:45}}),/rigid/);});
function copied(f,m){const d=new K.Drawing(),e=f.d.byId.get(f.id),out=d.add(K.Geo.transform(e,m)),ids=new Map([[f.id,out.id]]);d.transaction('Copy graph',()=>C.copyInto(d,f.d.serialize(),ids,m));return {d,id:out.id};}
test('clipboard scales slider expressions and world datums together',()=>{const f=fixture('slider',0,{enabled:true,min:-10,max:30},{enabled:true,value:20}),g=copied(f,M.multiply(M.translation(10,20,30),M.scale(2)));near(coordinate(g),40);near(report(g).joints[0].maximum,60);});
test('reflected clipboard reverses signed hinge drive and exchanges stops',()=>{const f=fixture('hinge',0,{enabled:true,min:-10,max:80},{enabled:true,value:30}),g=copied(f,M.scale(-1,1,1));near(coordinate(g),-30);near(report(g).joints[0].minimum,-80);near(report(g).joints[0].maximum,10);});
test('deleting joint geometry removes its travel and driver settings',()=>{const f=fixture();f.d.transaction('Delete',()=>f.d.remove([f.id]));assert.equal(C.state(f.d).constraints.length,0);f.d.undo();assert.equal(C.state(f.d).constraints[0].limits.max,30);});
const failed=results.filter(r=>r.status==='failed').length;fs.mkdirSync(path.join(__dirname,'results'),{recursive:true});fs.writeFileSync(path.join(__dirname,'results/joint-limits-results.json'),JSON.stringify({passed:results.length-failed,failed,tests:results},null,2));console.log('RESULT',results.length-failed,'passed;',failed,'failed');process.exitCode=failed?1:0;
