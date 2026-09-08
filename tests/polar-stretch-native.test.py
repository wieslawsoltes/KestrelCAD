#!/usr/bin/env python3
"""Actual OCCT bodies follow explicit rigid polar-stretch member modes."""
from pathlib import Path
import json,subprocess,sys,traceback
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'tools'))
import kernel as N
results=[]
def test(name,fn):
    try:fn();results.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
    except Exception as e:traceback.print_exc();results.append({'name':name,'status':'failed','error':str(e)})
def native(op,params=None,inputs=None):return N.execute({'op':op,'params':params or {},'inputs':inputs or []})
box=native('box',{'width':2,'depth':2,'height':2})
def expand(mode):
    code="""
for(const n of ['math','geometry','model','exchange','production','kernel','constraints','dynamic-blocks'])require('./src/'+n+'.js');
const K=globalThis.Kestrel,M=K.Math.M,args=JSON.parse(require('fs').readFileSync(0,'utf8')),d=new K.Drawing();d.currentLayer='0';
const member=K.Geo.transform({...K.Kernel.body(args.box),id:'part',layer:'0'},M.translation(9,-1,-1));
const action={type:'polar-stretch',targets:['part'],baseLength:10,length:'Reach',angle:90,min:[8,-2,-2],max:[12,2,2]};
if(args.mode!=='frame')action[args.mode]=['part'];
d.production.blocks.push({id:'parts',name:'Polar solids',entities:[member],attributes:[],dynamic:{version:1,parameters:[{name:'Reach',type:'length',default:10}],actions:[action]}});
const e=d.add('INSERT',{block:'parts',matrix:Array.from(M.identity()),attributes:{},parameters:{}}),before=d.snapshot();
try{K.DynamicBlocks.setValues(d,e.id,{Reach:20});const b=K.Production.expand(d,d.byId.get(e.id))[0];K.Kernel.validate(b);console.log(JSON.stringify({solid:b.solid}));}
catch(e){console.log(JSON.stringify({error:e.message,unchanged:d.snapshot()===before}));}
"""
    run=subprocess.run(['node','-e',code],cwd=ROOT,input=json.dumps({'box':box,'mode':mode}),text=True,capture_output=True,timeout=20)
    assert run.returncode==0,run.stderr
    return json.loads(run.stdout)
def moving():
    b=expand('moveOnly')['solid'];assert b['brep']==box['brep'];m=native('massprops',inputs=[b]);assert abs(m['volume']-8)<1e-6
    assert all(abs(x-y)<1e-6 for x,y in zip(m['centroid'],[0,20,0]))
test('Move whole retains authoritative BREP with exact moved mass centroid',moving)
def rotating():
    b=expand('rotateOnly')['solid'];assert b['brep']==box['brep'];m=native('massprops',inputs=[b]);assert all(abs(x-y)<1e-6 for x,y in zip(m['centroid'],[0,10,0]))
test('Rotate only turns native topology without applying the reach delta',rotating)
def reject():
    r=expand('frame');assert r['unchanged'] and 'explicit' in r['error']
test('native members cannot use display meshes to guess stretch-frame inclusion',reject)
def step():
    b=expand('moveOnly')['solid'];s=native('export',{'format':'step'},[b]);again=native('import',{'format':'step','data':s['data']});m=native('massprops',inputs=[again]);assert abs(m['volume']-8)<1e-6
    assert all(abs(x-y)<1e-6 for x,y in zip(m['centroid'],[0,20,0]))
test('polar-stretched native placement survives real STEP interchange',step)
failed=sum(r['status']=='failed' for r in results);(ROOT/'tests/results/polar-stretch-native-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'tests':results},indent=2)+'\n');raise SystemExit(bool(failed))
