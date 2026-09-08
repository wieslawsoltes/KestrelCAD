#!/usr/bin/env python3
"""Independent ezdxf decoding/audits of actual polar-block output."""
from pathlib import Path
import io,json,math,subprocess
import ezdxf
ROOT=Path(__file__).resolve().parent.parent;results=[]
def check(name,fn):
    try:fn();results.append({'name':name,'status':'passed'});print('PASS',name)
    except Exception as e:results.append({'name':name,'status':'failed','error':str(e)});print('FAIL',name,e)
def drawing(options=None,values=None):
    code="""
for(const n of ['math','geometry','model','exchange','production','kernel','constraints','dynamic-blocks'])require('./src/'+n+'.js');
require('./tests/polar-block.fixture.js');
const args=JSON.parse(require('fs').readFileSync(0,'utf8')),f=makePolarBlockFixture(args.options);
Kestrel.DynamicBlocks.setValues(f.doc,f.insert.id,args.values);
process.stdout.write(Kestrel.Exchange.writeDXF(f.doc));
"""
    run=subprocess.run(['node','-e',code],cwd=ROOT,input=json.dumps({'options':options or {},'values':values or {}}),text=True,capture_output=True,timeout=20)
    assert run.returncode==0,run.stderr
    d=ezdxf.read(io.StringIO(run.stdout));audit=d.audit();assert not audit.errors and not audit.fixes,[(a.code,a.message) for a in [*audit.errors,*audit.fixes]]
    return d
def full():
    d=drawing(values={'Count':5,'Variant':'Long'});insert=next(iter(d.modelspace()));r=list(insert.virtual_entities());circles=[e for e in r if e.dxftype()=='CIRCLE'];assert len(circles)==5
    for i,c in enumerate(circles):
        theta=2*math.pi*i/5
        assert c.dxf.center.isclose((10*math.cos(theta),10*math.sin(theta),0),abs_tol=1e-7)
        assert abs(c.dxf.radius-2)<1e-7
    assert len({e.dxf.handle for b in d.blocks for e in b})==sum(len(b) for b in d.blocks)
check('independent full-turn DXF has exact analytic circle centers and unique handles',full)
def partial():
    d=drawing(values={'Count':3,'Sweep':-180});r=[e for e in next(iter(d.modelspace())).virtual_entities() if e.dxftype()=='LINE'];assert len(r)==3
    assert r[1].dxf.end.isclose((0,-12,0),abs_tol=1e-7);assert r[-1].dxf.end.isclose((-12,0,0),abs_tol=1e-7)
check('independent partial clockwise array retains endpoints and direction',partial)
def upright():
    d=drawing({'rotateItems':False,'base':[10,0,0]});r=[e for e in next(iter(d.modelspace())).virtual_entities() if e.dxftype()=='LINE']
    assert all((e.dxf.end-e.dxf.start).isclose((2,0,0),abs_tol=1e-7) for e in r)
    assert r[1].dxf.end.isclose((2,10,0),abs_tol=1e-7)
check('independent reader sees untranslated orientation for unrotated copies',upright)
def spatial():
    d=drawing({'axis':[0,1,0]});r=[e for e in next(iter(d.modelspace())).virtual_entities() if e.dxftype()=='CIRCLE']
    assert r[1].ocs().to_wcs(r[1].dxf.center).isclose((0,0,-10),abs_tol=1e-7);assert r[1].dxf.extrusion.isclose((1,0,0),abs_tol=1e-7)
check('independent 3D circular array retains analytic OCS orientation',spatial)
def annotations():
    d=drawing(values={'Variant':'Long'});r=list(next(iter(d.modelspace())).virtual_entities());text=[e for e in r if e.dxftype()=='TEXT'];assert len(text)==4
    assert all(e.dxf.text=='Long / 4' for e in text)
    assert all(e.dxf.color==0 for e in r if e.dxftype()=='LINE')
check('evaluated lookup labels and ByBlock styling survive standard exchange',annotations)
failed=sum(r['status']=='failed' for r in results);(ROOT/'tests/results/polar-block-interop-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'tests':results},indent=2)+'\n');raise SystemExit(bool(failed))
