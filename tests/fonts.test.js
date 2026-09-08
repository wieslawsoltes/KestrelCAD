'use strict';const assert=require('node:assert/strict'),fs=require('node:fs'),{fixture}=require('./font-fixture');
for(const f of ['math','geometry','model','exchange','production','kernel','constraints','dynamic-blocks','fonts'])require('../src/'+f+'.js');
const K=globalThis.Kestrel,F=K.Fonts,P=K.Production,{M}=K.Math,tests=[];
const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-7,`${a} != ${b}`),test=(name,fn)=>{try{fn();tests.push({name,status:'passed'});console.log('PASS',name);}catch(e){tests.push({name,status:'failed',error:e.stack});console.error('FAIL',name,e);}};
const legacy=F.parseSHX(fixture()),uni=F.parseSHX(fixture(true));
function doc(){const d=new K.Drawing('Font fixture');d.production.textstyles=[...F.defaults(),{name:'Engineering',font:'synthetic.shx',height:0,width:1,oblique:0}];const e=d.add('TEXT',{text:'AA',position:[0,0,0],height:10,textStyle:'Engineering',layer:'0'});d.reindex();return {d,e};}
for(const [name,font]of [['legacy',legacy],['unicode',uni]]){
 test(name+' parser retains font metrics and glyph programs',()=>{assert.equal(font.above,10);assert.equal(font.below,2);assert.ok(font.glyphs.has(65));});
 test(name+' displacement instructions and glyph advance are real geometry',()=>{const g=F.glyph(font,65);assert.deepEqual(g.segments,[[[0,0],[0,10]],[[0,10],[6,0]]]);assert.deepEqual(g.advance,[8,0]);});
 test(name+' stacks and scale changes move without a connecting pen stroke',()=>{const g=F.glyph(font,66);assert.deepEqual(g.segments,[[[0,0],[4,6]]]);assert.deepEqual(g.advance,[8,0]);});
 test(name+' subshape calls reuse checked programs',()=>{assert.deepEqual(F.glyph(font,71),F.glyph(font,65));});
 test(name+' octant arc counterclockwise terminates correctly',()=>{const g=F.glyph(font,67);near(g.advance[0],-10);near(g.advance[1],0);assert.ok(g.segments.length>50);});
 test(name+' octant arc clockwise follows the correct side',()=>{const g=F.glyph(font,75);near(g.advance[0],-10);assert.ok(g.segments[5][1][1]<0);});
 test(name+' fractional arcs honor start and end offsets',()=>{const g=F.glyph(font,68),a=(45+56*45/256)*Math.PI/180,b=(90+28*45/256)*Math.PI/180;near(g.advance[0],3*(Math.cos(b)-Math.cos(a)));near(g.advance[1],3*(Math.sin(b)-Math.sin(a)));});
 test(name+' bulge arcs terminate exactly at requested displacement',()=>{const g=F.glyph(font,69);assert.deepEqual(g.advance,[10,0]);assert.ok(g.segments.some(s=>s[1][1]<-4.9));});
 test(name+' multiple bulges accept signed clockwise curvature',()=>{const g=F.glyph(font,70);assert.deepEqual(g.advance,[20,0]);assert.ok(g.segments.some(s=>s[1][1]>4.9));});
 test(name+' vertical conditional consumes an entire variable-length instruction',()=>{assert.deepEqual(F.glyph(font,78).advance,[3,0]);assert.deepEqual(F.glyph(font,78,true).advance,[5,0]);});
 test(name+' vertical displacement changes pen position only in vertical mode',()=>{assert.deepEqual(F.glyph(font,72).advance,[5,0]);assert.deepEqual(F.glyph(font,72,true).advance,[5,-10]);});
 test(name+' short vectors follow SHX nonunit direction table',()=>{assert.deepEqual(F.glyph(font,73).advance,[2,2]);});
 test(name+' pen-up arcs do not draw strokes',()=>{assert.deepEqual(F.glyph(font,76),{segments:[],advance:[10,0]});});
}
test('SHP source descriptions produce equivalent glyph programs',()=>{const f=F.parseSHP('*0,4,Synthetic\n10,2,2,0\n*65,12,A\n9,(0,10),(6,-10),(0,0),2,8,(2,0),0\n');assert.deepEqual(F.glyph(f,65),F.glyph(legacy,65));});
test('SHP short vectors use leading-zero hexadecimal notation',()=>{const f=F.parseSHP('*0,4,Synthetic\n10,2,2,0\n*73,3,I\n024,020,0\n');assert.deepEqual(F.glyph(f,73).advance,[2,2]);});
test('legacy dimension glyph remapping uses 256/257/258',()=>{const f=F.parseSHX(fixture(false,{256:[8,2,0,0],257:[8,3,0,0],258:[8,4,0,0]}));near(F.glyph(f,176).advance[0],2);near(F.glyph(f,177).advance[0],3);near(F.glyph(f,8709).advance[0],4);});
for(const [label,fn]of [
 ['truncated index',()=>F.parseSHX(fixture().subarray(0,31))],['truncated glyph',()=>F.parseSHX(fixture().subarray(0,90))],
 ['unsupported font signature',()=>F.parseSHX(new Uint8Array(30))],['Big Font is not disguised as Unicode',()=>F.parseSHX(Buffer.from('AutoCAD-86 bigfont 1.0'))],
 ['zero scale denominator',()=>F.parseSHX(fixture(false,{65:[3,0,0]}))],['missing glyph end',()=>F.parseSHX(fixture(false,{65:[8,1,1]}))],
 ['recursive subshapes',()=>F.parseSHX(fixture(false,{65:[7,65,0]}))],['missing subshape',()=>F.parseSHX(fixture(false,{65:[7,99,0]}))],
 ['reserved instruction',()=>F.parseSHX(fixture(false,{65:[15,0]}))],['invalid EOF',()=>{const b=fixture();b[b.length-1]=0;F.parseSHX(b);}],
 ['stack underflow',()=>F.glyph(F.parseSHX(fixture(false,{65:[6,0]})),65)],['unbalanced stack',()=>F.glyph(F.parseSHX(fixture(false,{65:[5,0]})),65)],
 ['SHP inconsistent byte count',()=>F.parseSHP('*0,4,F\n10,2,0,0\n*65,50,A\n8,1,1,0\n')]
])test('reject '+label,()=>assert.throws(fn));
F.register('synthetic.shx',legacy);
test('font resources resolve by basename case independently of filesystem path',()=>{F.register('C:\\fonts\\SYNTHETIC.SHX',legacy);assert.equal(F.registry.get('synthetic.shx'),legacy);});
test('font-backed text uses measured strokes rather than approximate browser glyphs',()=>{const {d,e}=doc(),g=d.geometry(e);assert.equal(g.texts.length,0);assert.equal(g.segments.length,4);near(g.segments[2][0][0],8);near(Math.max(...g.points.map(p=>p[1])),10);});
test('width and oblique are applied in text-local coordinates',()=>{const {d,e}=doc();e.widthFactor=2;e.oblique=45;const g=F.layout(e,d);near(g.segments[0][1][0],20);near(g.segments[0][1][1],10);});
test('text rotation and tilt map strokes onto the annotation plane',()=>{const {d,e}=doc();e.normal=[0,-1,0];e.direction=[1,0,0];const g=F.layout(e,d);near(g.segments[0][1][2],10);near(g.segments[0][1][1],0);});
test('backwards and upside-down transform stroke geometry',()=>{const {d,e}=doc();e.backwards=true;e.upsideDown=true;const g=F.layout(e,d);near(g.segments[0][1][1],-10);near(g.segments[1][1][0],-6);});
test('center alignment uses actual pen advance, not character count estimate',()=>{const {d,e}=doc();e.align='center';near(F.layout(e,d).segments[0][0][0],-8);});
test('multiline layout uses requested spacing and resets baseline',()=>{const {d,e}=doc();e.text='A\nA';e.lineSpacing=2;near(F.layout(e,d).segments[2][0][1],-20);});
test('native persistence preserves references without serializing user font bytes',()=>{const {d}=doc(),saved=d.serialize();assert.deepEqual(K.Drawing.from(saved).serialize(),saved);assert.ok(!JSON.stringify(saved).includes('glyphs'));});
test('missing fonts and glyphs produce explicit reports and visible placeholders',()=>{const {d,e}=doc();e.text='Z';assert.ok(F.layout(e,d).warnings[0].includes('U+5A'));d.production.textstyles[1].font='not-installed.shx';const g=F.layout(e,d);assert.ok(g.warnings[0].includes('Missing font'));assert.equal(g.texts.length,0);assert.equal(g.segments.length,5);});
test('style changes and undo invalidate stroke geometry',()=>{const {d,e}=doc();near(d.geometry(e).segments[1][1][0],6);d.transaction('width',()=>d.production.textstyles[1].width=2);near(d.geometry(d.byId.get(e.id)).segments[1][1][0],12);d.undo();near(d.geometry(d.byId.get(e.id)).segments[1][1][0],6);});
test('DXF STYLE and TEXT retain named fonts, width, slant and generation flags',()=>{const {d,e}=doc();e.widthFactor=1.8;e.oblique=15;e.backwards=true;const text=K.Exchange.writeDXF(d),again=K.Drawing.from(K.Exchange.parseDXF(text).data),other=again.entities[0];assert.equal(F.style(again,other.textStyle).font,'synthetic.shx');near(other.widthFactor,1.8);near(other.oblique,15);assert.equal(other.backwards,true);fs.mkdirSync('tests/fixtures',{recursive:true});fs.writeFileSync('tests/fixtures/font-styles.dxf',text);});
test('SVG stroke output does not depend on installed text glyphs',()=>{const {d}=doc();const svg=K.Exchange.writeSVG(d);assert.ok(svg.includes('<path'));assert.ok(!svg.includes('>AA<'));});
test('outline SVG preserves oblique, reflection and actual plane projection',()=>{const {d,e}=doc();e.textStyle='STANDARD';e.oblique=20;e.widthFactor=2;e.backwards=true;const svg=K.Exchange.writeSVG(d);assert.ok(svg.includes('transform="matrix('));assert.ok(svg.includes('data-font="browser default"'));});
for(const [label,change]of [['zero width',d=>d.production.textstyles[1].width=0],['unsafe angle',d=>d.production.textstyles[1].oblique=90],['duplicate style',d=>d.production.textstyles.push({...d.production.textstyles[1],name:'engineering'})],['missing standard',d=>d.production.textstyles.shift()],['NaN text width',d=>d.entities[0].widthFactor=NaN]])test('reject '+label,()=>{const {d}=doc();change(d);assert.throws(()=>K.Drawing.from(d.serialize()));});

for(const [label,m]of [['nonuniform scale',M.scale(2,3,1)],['reflection',M.scale(-1,1,1)],['rotation in 3D',M.rotation(.5,[1,0,0])],['shear',(()=>{const m=M.identity();m[4]=.4;return m;})()]])test('text-local '+label+' preserves every glyph point',()=>{const {d,e}=doc();e.widthFactor=1.4;e.oblique=20;P.owners.set(e,d);const before=F.layout(e,d),after=F.layout(K.Geo.transform(e,m),d);assert.equal(before.segments.length,after.segments.length);for(let i=0;i<before.segments.length;i++)for(let j=0;j<2;j++){const p=M.point(m,before.segments[i][j]);p.forEach((v,k)=>near(v,after.segments[i][j][k]));}});
test('nested block attribute inherits its own named style through affine expansion',()=>{const {d}=doc();d.entities=[];d.production.textstyles[1].width=2;d.production.blocks=[{id:'b',name:'Styled',entities:[],attributes:[{tag:'TAG',value:'A',position:[0,0,0],height:10,textStyle:'Engineering'}]}];const insert=d.add('INSERT',{block:'b',matrix:Array.from(M.scale(2)),attributes:{}});d.reindex();const child=P.expand(d,insert)[0];assert.equal(child.textStyle,'Engineering');near(F.layout(child,d).segments[1][1][0],24);});
test('font replacement invalidates cached geometry outside the UI too',()=>{const {d,e}=doc();const before=d.geometry(e);F.register('synthetic.shx',F.parseSHX(fixture(false,{65:[8,5,0,0]})));const after=d.geometry(e);assert.notEqual(before,after);assert.equal(after.segments.length,2);F.register('synthetic.shx',legacy);});
const failed=tests.filter(t=>t.status==='failed').length;fs.writeFileSync('tests/results/fonts-results.json',JSON.stringify({passed:tests.length-failed,failed,tests},null,2)+'\n');console.log('Fonts:',tests.length-failed,'passed;',failed,'failed');process.exitCode=failed?1:0;
