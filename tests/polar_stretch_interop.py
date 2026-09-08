#!/usr/bin/env python3
"""Independent ezdxf checks of evaluated polar-stretch geometry."""
from pathlib import Path
import io,json,subprocess
import ezdxf
ROOT=Path(__file__).resolve().parent.parent;results=[]
def check(name,fn):
    try:fn();results.append({'name':name,'status':'passed'});print('PASS',name)
    except Exception as e:results.append({'name':name,'status':'failed','error':str(e)});print('FAIL',name,e)
def entities(options=None,values=None):
    code="""
for(const n of ['math','geometry','model','exchange','production','kernel','constraints','dynamic-blocks'])require('./src/'+n+'.js');
require('./tests/polar-stretch.fixture.js');const a=JSON.parse(require('fs').readFileSync(0,'utf8')),f=makePolarStretchFixture(a.options);
Kestrel.DynamicBlocks.setValues(f.doc,f.insert.id,a.values);process.stdout.write(Kestrel.Exchange.writeDXF(f.doc));
"""
    p=subprocess.run(['node','-e',code],cwd=ROOT,input=json.dumps({'options':options or {},'values':values or {'Reach':20,'Angle':90}}),text=True,capture_output=True,timeout=20)
    assert p.returncode==0,p.stderr
    d=ezdxf.read(io.StringIO(p.stdout));audit=d.audit();assert not audit.errors and not audit.fixes
    return list(next(iter(d.modelspace())).virtual_entities())
def straight():
    e=entities();line=next(x for x in e if x.dxftype()=='LINE');assert line.dxf.end.isclose((0,20,0),abs_tol=1e-7);assert line.dxf.start.isclose((0,0,0),abs_tol=1e-7)
check('independent DXF reader sees the final stretched and rotated endpoints',straight)
def conic():
    circle=next(e for e in entities() if e.dxftype()=='CIRCLE');assert circle.ocs().to_wcs(circle.dxf.center).isclose((0,20,0),abs_tol=1e-7);assert circle.dxf.radius==1
check('whole conic remains a genuine circle of unchanged radius',conic)
def spatial():
    line=next(e for e in entities({'axis':[0,1,0]}) if e.dxftype()=='LINE');assert line.dxf.end.isclose((0,0,-20),abs_tol=1e-7)
check('free-space polar action survives standard block transformation',spatial)
def text():
    t=next(e for e in entities() if e.dxftype()=='TEXT');assert t.dxf.text=='Reach 20';assert t.dxf.insert.isclose((1,20,0),abs_tol=1e-7)
check('evaluated attribute value and moved insertion survive exchange',text)
failed=sum(r['status']=='failed' for r in results);(ROOT/'tests/results/polar-stretch-interop-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'tests':results},indent=2)+'\n');raise SystemExit(bool(failed))
