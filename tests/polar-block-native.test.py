#!/usr/bin/env python3
"""Real OCCT topology retained by native configurable block arrays."""
from pathlib import Path
import json,subprocess,sys,traceback
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'tools'))
import kernel as N
results=[]
def test(name,fn):
    try:fn();results.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
    except Exception as e:traceback.print_exc();results.append({'name':name,'status':'failed','error':str(e)})
def native(op,params=None,inputs=None):return N.execute({'op':op,'params':params or {},'inputs':inputs or []})
box=native('box',{'width':2,'depth':4,'height':6})
def expanded(rotate=True):
    code="""
for(const n of ['math','geometry','model','exchange','production','kernel','constraints','dynamic-blocks'])require('./src/'+n+'.js');
const K=globalThis.Kestrel,M=K.Math.M,args=JSON.parse(require('fs').readFileSync(0,'utf8')),d=new K.Drawing();d.currentLayer='0';
const member=K.Geo.transform({...K.Kernel.body(args.box),id:'part',layer:'0'},M.translation(10,0,0));
d.production.blocks.push({id:'parts',name:'Polar solids',entities:[member],attributes:[],dynamic:{version:1,parameters:[{name:'Count',type:'integer',default:4}],actions:[{type:'polar-array',targets:['part'],count:'Count',rotateItems:args.rotate,base:[10,0,0]}]}});
const e=d.add('INSERT',{block:'parts',matrix:Array.from(M.identity()),attributes:{},parameters:{}});
const a=K.Production.expand(d,e);for(const b of a)K.Kernel.validate(b);console.log(JSON.stringify(a.map(e=>e.solid)));
"""
    run=subprocess.run(['node','-e',code],cwd=ROOT,input=json.dumps({'box':box,'rotate':rotate}),text=True,capture_output=True,timeout=20)
    assert run.returncode==0,run.stderr
    return json.loads(run.stdout)
def geometry():
    a=expanded();assert len(a)==4 and all(b['brep']==box['brep'] for b in a)
    for b,p in zip(a,([11,2,3],[-2,11,3],[-11,-2,3],[2,-11,3])):
        mass=native('massprops',inputs=[b]);assert abs(mass['volume']-48)<1e-6
        assert all(abs(x-y)<1e-6 for x,y in zip(mass['centroid'],p)),mass['centroid']
test('polar block copies retain original BREP bytes and correct rotated mass centroids',geometry)
def unrotated():
    a=expanded(False)
    for b,p in zip(a,([11,2,3],[1,12,3],[-9,2,3],[1,-8,3])):
        mass=native('massprops',inputs=[b]);assert abs(mass['volume']-48)<1e-6
        assert all(abs(x-y)<1e-6 for x,y in zip(mass['centroid'],p)),mass['centroid']
test('nonrotating polar native copies preserve actual local shape orientation',unrotated)
def step():
    b=expanded()[1];s=native('export',{'format':'step'},[b]);again=native('import',{'format':'step','data':s['data']});mass=native('massprops',inputs=[again]);assert abs(mass['volume']-48)<1e-6
    assert all(abs(x-y)<1e-6 for x,y in zip(mass['centroid'],[-2,11,3]))
test('expanded polar native body retains world placement through a genuine STEP round trip',step)
failed=sum(r['status']=='failed' for r in results);(ROOT/'tests/results/polar-block-native-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'tests':results},indent=2)+'\n');raise SystemExit(bool(failed))
