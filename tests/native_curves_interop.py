#!/usr/bin/env python3
"""Independent ezdxf evaluation of genuine native-edge drafting exports."""
from pathlib import Path
import json,math,sys,subprocess,traceback
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'tests/results';OUT.mkdir(exist_ok=True);sys.path.insert(0,str(ROOT/'tools'))
import native_curves as C,cadquery as cq,ezdxf
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.Geom import Geom_Hyperbola
from OCP.gp import gp_Hypr,gp_Ax2,gp_Pnt,gp_Dir
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
sources=[cq.Edge.makeLine((1,2,3),(5,7,9)),cq.Edge.makeCircle(4,(2,3,5),(0,1,0)),cq.Edge.makeCircle(5,(1,2,3),(0,0,1),20,200),cq.Edge.makeEllipse(8,3,(1,2,3),(0,1,0),(1,0,0),10,230),cq.Edge.makeSpline([cq.Vector(0,0,0),cq.Vector(2,5,1),cq.Vector(4,0,3)],periodic=True),cq.Edge(BRepBuilderAPI_MakeEdge(Geom_Hyperbola(gp_Hypr(gp_Ax2(gp_Pnt(),gp_Dir(0,0,1)),4,2)),-1.,1.).Edge())]
curves=[C.extract_edge(e) for e in sources];input_file=OUT/'native-curves-fixture.json';input_file.write_text(json.dumps(curves));output=OUT/'native-curves.dxf';reoutput=OUT/'native-curves-roundtrip.dxf'
script=r'''
const fs=require('fs');for(const n of ['math','geometry','model','exchange','production','kernel','native-curves'])require('./src/'+n+'.js');
const K=globalThis.Kestrel,d=new K.Drawing();for(const e of JSON.parse(fs.readFileSync(process.argv[1],'utf8')))d.add(K.NativeCurves.curve(e));
fs.writeFileSync(process.argv[2],K.Exchange.writeDXF(d.serialize()));const parsed=K.Exchange.parseDXF(fs.readFileSync(process.argv[2],'utf8'),'native curves');
fs.writeFileSync(process.argv[3],K.Exchange.writeDXF(parsed.data));
const tiny=new K.Drawing();tiny.add('SPLINE',{degree:1,controlPoints:[[0,0,0],[2,0,0],[3,0,0]],knots:[0,0,1e-10,1,1]});fs.writeFileSync('tests/results/native-curves-tiny.dxf',K.Exchange.writeDXF(tiny));
'''
subprocess.run(['node','-e',script,str(input_file),str(output),str(reoutput)],cwd=ROOT,check=True)
doc=ezdxf.readfile(output);entities=list(doc.modelspace());results=[]
def test(name,fn):
 try:fn();results.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
 except Exception as e:traceback.print_exc();results.append({'name':name,'status':'failed','error':str(e)})
def near(a,b):assert abs(a-b)<1e-8*max(1,abs(b)),(a,b)
def audit():
 a=doc.audit();assert not a.errors and not a.fixes
 assert [e.dxftype() for e in entities]==['LINE','CIRCLE','ARC','ELLIPSE','SPLINE','SPLINE']
test('native carriers export as actual supported DXF types with zero audit fixes',audit)
def line():
 e=entities[0]
 for a,b in zip((*e.dxf.start,*e.dxf.end),(1,2,3,5,7,9)):near(a,b)
test('LINE contains original native world endpoints',line)
def circle():
 e=entities[1];assert tuple(e.ocs().to_wcs(e.dxf.center))==(2,3,5);near(e.dxf.radius,4);assert tuple(e.dxf.extrusion)==(0,1,0)
test('tilted CIRCLE uses correct OCS and world center',circle)
def arc():
 e=entities[2];near(e.dxf.start_angle,20);near(e.dxf.end_angle,200)
test('ARC preserves actual native trim extent',arc)
def ellipse():
 e=entities[3];near(e.dxf.ratio,3/8);near(e.dxf.start_param,math.radians(10));near(e.dxf.end_param,math.radians(230));near(e.dxf.major_axis.magnitude,8)
 for p in e.vertices([e.dxf.start_param+(e.dxf.end_param-e.dxf.start_param)*i/20 for i in range(21)]):assert cq.Vertex.makeVertex(*p).distance(sources[3])<1e-7
test('independent ELLIPSE points lie on the original native trimmed edge',ellipse)
for index,label in [(4,'closed periodic carrier'),(5,'rational hyperbola')]:
 def check(i=index):
  e=entities[i];tool=e.construction_tool();assert len(e.knots)==len(e.control_points)+e.dxf.degree+1
  for t in [j/30 for j in range(31)]:
   if i==4:
    # Clamping preserves the periodic curve parameter; compare actual evaluations
    # instead of relying on a nearest-point projection with its own tolerance.
    a=BRepAdaptor_Curve(sources[i].wrapped);p=a.Value(a.FirstParameter()+t*(a.LastParameter()-a.FirstParameter()))
    assert (tool.point(t)-ezdxf.math.Vec3(p.X(),p.Y(),p.Z())).magnitude<1e-10
   else:assert cq.Vertex.makeVertex(*tool.point(t)).distance(sources[i])<1e-7
 test('independent SPLINE evaluation preserves '+label,check)
def roundtrip():
 d=ezdxf.readfile(reoutput);a=d.audit();assert not a.errors and not a.fixes
 assert [e.dxftype() for e in d.modelspace()]==[e.dxftype() for e in entities]
 for a,b in zip(entities,d.modelspace()):
  if a.dxftype()=='SPLINE':assert list(a.knots)==list(b.knots) and list(a.weights)==list(b.weights)
test('browser-style DXF import and reexport preserves rational knots and weights',roundtrip)
def tiny_span():
 d=ezdxf.readfile(OUT/'native-curves-tiny.dxf');a=d.audit();assert not a.errors and not a.fixes
 e=list(d.modelspace())[0];assert 0<e.dxf.knot_tolerance<1e-15
 t=e.construction_tool();near(t.point(5e-11).x,1,);near(t.point(1).x,3)
test('independent reader retains tiny knot spans and their exact interpolation',tiny_span)
failed=sum(r['status']=='failed' for r in results);(OUT/'native-curves-interop-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'tests':results},indent=2)+'\n');print('RESULT',len(results)-failed,'passed',failed,'failed');sys.exit(bool(failed))
