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
def slider():
    data=solve("C.add(d,{type:'slider',a:{entity:e.id},b:{world:[0,0,0]},limits:{enabled:true,min:10,max:50},drive:{enabled:true,value:30}})")
    body=data['entities'][0]['solid'];assert body['brep']==box['brep'];props=native('massprops',inputs=[body]);near(props['volume'],6000)
    for a,b in zip(props['centroid'],[5,10,45]):near(a,b)
test('joint driver preserves authoritative BREP and moves native mass properties',slider)
def hinge():
    data=solve("C.add(d,{type:'hinge',a:{entity:e.id},b:{world:[0,0,0]},limits:{enabled:true,min:-100,max:100},drive:{enabled:true,value:90}})")
    body=data['entities'][0]['solid'];assert body['brep']==box['brep'];props=native('massprops',inputs=[body]);near(props['volume'],6000)
    for a,b in zip(props['centroid'],[-10,5,15]):near(a,b)
test('signed hinge drive rotates native centroid without deforming its body',hinge)
def exchange():
    data=solve("C.add(d,{type:'slider',a:{entity:e.id},b:{world:[0,0,0]},limits:{enabled:true,min:10,max:50},drive:{enabled:true,value:30}})")
    encoded=native('export',{'format':'step'},[data['entities'][0]['solid']]);again=native('import',{'format':'step','data':encoded['data']});props=native('massprops',inputs=[again])
    near(props['volume'],6000)
    for a,b in zip(props['centroid'],[5,10,45]):near(a,b)
test('driven joint pose survives real STEP output and input',exchange)
def rollback():
    data=solve("C.add(d,{type:'slider',a:{entity:e.id},b:{world:[0,0,0]},limits:{enabled:true,min:10,max:50},drive:{enabled:true,value:30}});const before=d.snapshot();try{d.transaction('invalid',()=>C.state(d).constraints[0].drive.value=70);}catch(_){}if(d.snapshot()!==before)throw Error('Not atomic');")
    body=data['entities'][0]['solid'];props=native('massprops',inputs=[body]);near(props['centroid'][2],45)
test('failed driver change retains authoritative native placement',rollback)
failed=sum(r['status']=='failed' for r in results);(ROOT/'tests/results/joint-limits-native-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'tests':results},indent=2));print('RESULT',len(results)-failed,'passed;',failed,'failed');sys.exit(bool(failed))
