#!/usr/bin/env python3
"""Actual OCCT bodies through the browser-independent 3D solver; not mocked BREP."""
from pathlib import Path
import json, subprocess, sys, traceback
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'tools'))
import kernel as N
results=[]
def test(name,fn):
    try:fn();results.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
    except Exception as e:traceback.print_exc();results.append({'name':name,'status':'failed','error':str(e)})
def near(a,b,t=1e-6):assert abs(a-b)<t*max(1,abs(b)),(a,b)
def native(op,params=None,inputs=None):return N.execute({'op':op,'params':params or {},'inputs':inputs or []})
box=native('box',{'width':10,'depth':20,'height':30})
header="""
for(const f of ['math','geometry','model','exchange','production','kernel','constraints','spatial-constraints'])require('./src/'+f+'.js');
const K=globalThis.Kestrel,C=K.SpatialConstraints,M=K.Math.M;
const source=JSON.parse(require('fs').readFileSync(0,'utf8')),d=new K.Drawing();d.currentLayer='0';const e=d.add(K.Kernel.body(source));
"""
def solve(script):
    result=subprocess.run(['node','-e',header+script+";K.Kernel.validate(d.byId.get(e.id));console.log(JSON.stringify(d.serialize()));"],cwd=ROOT,input=json.dumps(box),text=True,capture_output=True,timeout=20)
    if result.returncode:raise AssertionError(result.stderr)
    return json.loads(result.stdout)
def transformed():
    data=solve("C.add(d,{type:'fastened',a:{entity:e.id,local:[0,0,0]},b:{world:[40,50,60],axis:[1,0,0],xaxis:[0,1,0]}})")
    body=data['entities'][0]['solid'];assert body['brep']==box['brep'];props=native('massprops',inputs=[body]);near(props['volume'],6000)
    for a,b in zip(props['centroid'],[55,55,70]):near(a,b)
    assert data['entities'][0]['constraintFrame']==body['transform']
test('rigid spatial solve retains original native BREP and transforms authoritative mass properties',transformed)
def step():
    data=solve("C.add(d,{type:'coincident',a:{entity:e.id,local:[5,10,15]},b:{world:[100,200,300]}})")
    body=data['entities'][0]['solid'];encoded=native('export',{'format':'step'},[body]);again=native('import',{'format':'step','data':encoded['data']});props=native('massprops',inputs=[again])
    near(props['volume'],6000)
    for a,b in zip(props['centroid'],[100,200,300]):near(a,b)
test('constraint-solved native body survives genuine STEP export and reimport',step)
def after_fillet():
    data=solve("C.add(d,{type:'fastened',a:{entity:e.id},b:{world:[100,200,300]}})")
    body=data['entities'][0]['solid'];edited=native('fillet',{'edges':[0],'radius':1},[body]);assert edited['volume']<6000 and edited['solidCount']==1
    assert min(edited['mesh']['vertices'][0])>90
test('native edge operation accepts the solved world-space BREP transform',after_fillet)
def undo():
    data=solve("C.add(d,{type:'fastened',a:{entity:e.id},b:{world:[100,200,300]}});d.undo()")
    body=data['entities'][0]['solid'];assert body['brep']==box['brep'];props=native('massprops',inputs=[body])
    for a,b in zip(props['centroid'],[5,10,15]):near(a,b)
test('undo restores original native placement and body data',undo)
def fixed():
    data=solve("C.add(d,{type:'fixed-entity',a:{entity:e.id}});d.transaction('move',()=>d.transform([e.id],M.multiply(M.translation(40,50,60),M.rotation(.5,[1,2,3]))))")
    body=data['entities'][0]['solid'];props=native('massprops',inputs=[body])
    for a,b in zip(props['centroid'],[5,10,15]):near(a,b)
test('fixed native body rejects pose drift through ordinary rotate and move',fixed)
def mesh_edit():
    data=solve("C.add(d,{type:'hinge',a:{entity:e.id},b:{world:[10,20,30]}});const before=d.snapshot();let failed=false;try{d.transaction('bad grip',()=>{d.entities[0].vertices[0][0]+=1;});}catch(_){failed=true;}if(!failed||before!==d.snapshot())throw Error('Native integrity was not preserved');")
    assert data['entities'][0]['solid']['brep']==box['brep']
test('spatial integration does not bypass native mesh integrity guards',mesh_edit)
failed=sum(r['status']=='failed' for r in results);(ROOT/'tests/results/spatial-native-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'tests':results},indent=2));print('RESULT',len(results)-failed,'passed;',failed,'failed');sys.exit(bool(failed))
