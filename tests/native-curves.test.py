#!/usr/bin/env python3
"""Actual OCCT carriers, section geometry and rational-profile regression tests."""
from pathlib import Path
import json,math,sys,traceback,io
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'tools'))
import kernel as K,native_curves as C,cadquery as cq
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
from OCP.Geom import Geom_TrimmedCurve,Geom_Circle,Geom_Hyperbola,Geom_Parabola,Geom_BezierCurve,Geom_OffsetCurve
from OCP.GeomConvert import GeomConvert
from OCP.gp import gp_Pnt,gp_Dir,gp_Ax2,gp_Circ,gp_Hypr,gp_Parab
from OCP.TColgp import TColgp_Array1OfPnt
from OCP.GCPnts import GCPnts_AbscissaPoint
results=[]
def test(name,fn):
 try:fn();results.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
 except Exception as e:traceback.print_exc();results.append({'name':name,'status':'failed','error':str(e)})
def near(a,b,t=1e-8):assert abs(a-b)<=t*max(1,abs(b)),(a,b)
def reject(fn):
 try:fn()
 except (ValueError,TypeError):return
 raise AssertionError('Invalid input accepted')
def extract(shape,**params):return C.extract([shape],params)
def length(edge):
 a=BRepAdaptor_Curve(edge.wrapped);return GCPnts_AbscissaPoint.Length_s(a,a.FirstParameter(),a.LastParameter(),1e-10)
def points_match(e,data):
 rebuilt=C.spline_wire({**data,'type':'spline'},False);near(sum(length(v) for v in rebuilt.Edges()),length(e),1e-8)
 # Reparameterization is allowed for conics. Compare points to actual material curve.
 for t in [i/20 for i in range(21)]:
  for edge in rebuilt.Edges():
   a=BRepAdaptor_Curve(edge.wrapped);p=a.Value(a.FirstParameter()+(a.LastParameter()-a.FirstParameter())*t)
   assert cq.Vertex.makeVertex(*p.Coord()).distance(e)<1e-7
 return rebuilt
box=cq.Solid.makeBox(10,20,30);cylinder=cq.Solid.makeCylinder(4,12)
def cube():
 r=extract(box);assert r['curveCount']==12 and all(x['entity']['type']=='LINE' for x in r['curves'])
 near(sum(math.dist(*x['entity']['points']) for x in r['curves']),240)
test('box extracts twelve true LINE edges with exact total length',cube)
def circular():
 r=extract(cylinder);assert [x['entity']['type'] for x in r['curves']].count('CIRCLE')==2
 for x in r['curves']:
  if x['entity']['type']=='CIRCLE':near(x['entity']['radius'],4)
test('cylinder retains analytic circular edges and seam line',circular)
def circle():
 e=cq.Edge.makeCircle(6,(3,5,7),(0,1,0));d=C.extract_edge(e);assert d['type']=='CIRCLE';assert d['center']==[3,5,7];near(d['radius'],6);assert d['normal']==[0,1,0]
test('tilted circle retains its world center, axes and radius',circle)
def arc():
 e=cq.Edge.makeCircle(3,(0,0,0),(0,0,1),30,160);d=C.extract_edge(e);assert d['type']=='ARC';near(d['endAngle']-d['startAngle'],math.radians(130))
 for t in [0,.3,1]:
  a=d['startAngle']+(d['endAngle']-d['startAngle'])*t;p=[d['center'][i]+d['axisX'][i]*math.cos(a)+d['axisY'][i]*math.sin(a) for i in range(3)];assert cq.Vertex.makeVertex(*p).distance(e)<1e-9
test('trimmed circle transfers as ARC rather than a closed circle',arc)
def ellipse():
 e=cq.Edge.makeEllipse(8,3,(1,2,3),(0,0,1),(0,1,0),10,200);d=C.extract_edge(e);assert d['type']=='ELLIPSE';near(d['rx'],8);near(d['ry'],3);near(d['endAngle']-d['startAngle'],math.radians(190))
test('elliptical arc retains trimmed parameters and oriented axes',ellipse)
def selected():
 r=extract(box,edges=[4,1]);assert [x['edgeIndex'] for x in r['curves']]==[4,1]
test('explicit current topology edge indices retain requested order',selected)
for key,params in [('duplicate',{'edges':[1,1]}),('negative',{'edges':[-1]}),('invalid',{'edges':[99]}),('boolean',{'edges':[True]}),('empty',{'edges':[]})]:test('reject '+key+' edge indices',lambda p=params:reject(lambda:extract(box,**p)))
test('empty input rejected',lambda:reject(lambda:C.extract([],{})))
test('unknown extraction mode rejected',lambda:reject(lambda:extract(box,mode='sample')))
test('too many sources rejected',lambda:reject(lambda:C.extract([box]*33,{})))
test('one edge list cannot address multiple bodies',lambda:reject(lambda:C.extract([box,box],{'edges':[0]})))
test('section cannot silently accept edge index restriction',lambda:reject(lambda:extract(box,mode='section',edges=[0])))
def rectangle():
 r=extract(box,mode='section',origin=[0,0,5]);assert len(r['curves'])==4
 near(sum(math.dist(*x['entity']['points']) for x in r['curves']),60)
 assert all(abs(p[2]-5)<1e-9 for x in r['curves'] for p in x['entity']['points'])
test('planar body section creates editable line rectangle',rectangle)
def circle_section():
 r=extract(cylinder,mode='section',origin=[0,0,3]);assert len(r['curves'])==1;d=r['curves'][0]['entity'];assert d['type']=='CIRCLE';near(d['radius'],4);near(d['center'][2],3)
test('cylinder section is an analytic circle, not a fitted polyline',circle_section)
def tilted():
 r=extract(cylinder,mode='section',origin=[0,0,6],normal=[0,1,2]);d=r['curves'][0]['entity'];assert len(r['curves'])==1 and d['type']=='ELLIPSE';near(d['rx'],4*math.sqrt(1.25));near(d['ry'],4)
test('oblique cylinder section is a true ellipse',tilted)
def cavity():
 hollow=cylinder.cut(cq.Solid.makeCylinder(2,12));r=extract(hollow,mode='section',origin=[0,0,6]);assert sorted(round(x['entity']['radius']) for x in r['curves'])==[2,4]
test('section retains independent inner-hole and outer boundary circles',cavity)
test('missed section yields zero curves rather than invented geometry',lambda:near(extract(box,mode='section',origin=[0,0,99])['curveCount'],0))
test('zero section normal rejects',lambda:reject(lambda:extract(box,mode='section',normal=[0,0,0])))
def multiple():
 r=C.extract([box,box.translate((40,0,0))],{'mode':'section','origin':[0,0,4]});assert [x['sourceIndex'] for x in r['curves']]==[0]*4+[1]*4
test('multiple bodies keep source attribution for each section edge',multiple)
def transformed():
 src=K.pack(cylinder,.1);src['transform']=[1,0,0,0,0,1,0,0,0,0,1,0,20,30,40,1];before=json.dumps(src)
 r=K.execute({'op':'extract-curves','inputs':[src]});assert json.dumps(src)==before
 circles=[x['entity'] for x in r['curves'] if x['entity']['type']=='CIRCLE'];assert len(circles)==2;assert all(c['center'][:2]==[20,30] for c in circles)
test('serialized transformed body uses native world geometry and preserves source',transformed)
def affine():
 shape=K.affine(cylinder,[2,0,0,0,0,3,0,0,0,0,1,0,0,0,0,1]);r=extract(shape);assert any(x['entity']['type']=='SPLINE' for x in r['curves'])
 for row,edge in zip(r['curves'],shape.Edges()):
  if row['entity']['type']=='SPLINE':points_match(edge,row['entity'])
test('nonuniform native transforms retain rational edge carriers',affine)
spline=cq.Edge.makeSpline([cq.Vector(0,0,0),cq.Vector(3,8,1),cq.Vector(7,-2,5),cq.Vector(10,0,8)])
test('freeform 3D spline control data round trips to native edge',lambda:points_match(spline,C.extract_edge(spline)))
def trim():
 from OCP.BRep import BRep_Tool
 a=BRepAdaptor_Curve(spline.wrapped);lo,hi=a.FirstParameter(),a.LastParameter();e=cq.Edge(BRepBuilderAPI_MakeEdge(BRep_Tool.Curve_s(spline.wrapped,0.,0.),lo+.2*(hi-lo),lo+.75*(hi-lo)).Edge());d=C.extract_edge(e);assert d['knots'][0]==0 and d['knots'][-1]==1;points_match(e,d)
test('trimmed spline is clamped to the actual edge interval',trim)
def periodic():
 e=cq.Edge.makeSpline([cq.Vector(0,0,0),cq.Vector(2,5,1),cq.Vector(4,0,3)],periodic=True);d=C.extract_edge(e);assert d['closed'];points_match(e,d)
test('periodic spline seam opens to an equivalent closed clamped spline',periodic)
def bezier():
 p=TColgp_Array1OfPnt(1,4)
 for i,pt in enumerate([(0,0,0),(2,4,1),(5,-1,3),(9,1,6)],1):p.SetValue(i,gp_Pnt(*pt))
 e=cq.Edge(BRepBuilderAPI_MakeEdge(Geom_BezierCurve(p),.1,.8).Edge());points_match(e,C.extract_edge(e))
test('trimmed Bezier edge transfers without fitting sampled points',bezier)
for name,carrier in [('hyperbola',Geom_Hyperbola(gp_Hypr(gp_Ax2(gp_Pnt(),gp_Dir(0,0,1)),4,2))),('parabola',Geom_Parabola(gp_Parab(gp_Ax2(gp_Pnt(),gp_Dir(0,0,1)),2)))]:
 def conic(c=carrier):
  edge=cq.Edge(BRepBuilderAPI_MakeEdge(c,-1.,1.).Edge());d=C.extract_edge(edge);assert d['degree']==2;points_match(edge,d)
 test('finite '+name+' converts to rational spline geometry',conic)
def closed_profile():
 c=GeomConvert.CurveToBSplineCurve_s(Geom_TrimmedCurve(Geom_Circle(gp_Circ(gp_Ax2(gp_Pnt(),gp_Dir(0,0,1)),4)),0,math.tau));e=cq.Edge(BRepBuilderAPI_MakeEdge(c).Edge());d=C.extract_edge(e);p={**d,'type':'spline'}
 out=K.execute({'op':'extrude','params':{'profile':p,'vector':[0,0,7]}});near(out['volume'],math.pi*16*7,1e-7)
 reopened=K.execute({'op':'import','params':{'format':'step','data':K.execute({'op':'export','inputs':[out],'params':{'format':'step'}})['data']}});near(reopened['volume'],out['volume'])
test('closed rational spline extrudes and STEP-round-trips actual solid material',closed_profile)
def open_path():
 d=C.extract_edge(cq.Edge.makeLine((0,0,0),(0,0,20)));p={'type':'spline','controlPoints':d['points'],'degree':1,'knots':[0,0,1,1]};out=K.execute({'op':'sweep','params':{'profile':{'type':'circle','radius':2},'path':p}});near(out['volume'],math.pi*80)
test('open clamped spline can drive an actual native sweep path',open_path)
def round_profile(origin=(0,0,0),normal=(0,0,1),radius=4):
 carrier=GeomConvert.CurveToBSplineCurve_s(Geom_TrimmedCurve(Geom_Circle(gp_Circ(gp_Ax2(gp_Pnt(*origin),gp_Dir(*normal)),radius)),0,math.tau))
 return {**C.extract_edge(cq.Edge(BRepBuilderAPI_MakeEdge(carrier).Edge())),'type':'spline'}
def region():
 out=K.execute({'op':'plane-surface','params':{'profile':round_profile()}});near(out['area'],math.pi*16);assert out['solidCount']==0 and out['valid']
test('rational spline closed profile creates a validated native planar region',region)
def loft():
 out=K.execute({'op':'loft','params':{'profiles':[round_profile(),round_profile((0,0,7))]}});near(out['volume'],math.pi*16*7,1e-7);assert out['solidCount']==1
test('rational spline profiles drive native loft with independent volume check',loft)
def revolve():
 out=K.execute({'op':'revolve','params':{'profile':round_profile((10,0,0),(0,1,0),2),'axisStart':[0,0,0],'axisEnd':[0,0,1],'angle':360}});near(out['volume'],2*math.pi**2*10*4,1e-7)
test('rational spline profile revolves into toroidal material of known volume',revolve)
def hollow_profile():
 out=K.execute({'op':'extrude','params':{'profile':round_profile(),'holes':[round_profile(radius=2)],'vector':[0,0,7]}});near(out['volume'],math.pi*12*7,1e-7)
test('rational inner spline profile preserves an actual hollow extrusion',hollow_profile)
def cubic_path():
 path=C.extract_edge(cq.Edge.makeSpline([cq.Vector(0,0,0),cq.Vector(0,0,5),cq.Vector(2,0,10),cq.Vector(3,1,15)]))
 out=K.execute({'op':'sweep','params':{'profile':{'type':'circle','radius':.25},'path':{**path,'type':'spline'}}});assert out['solidCount']==1 and out['valid'] and out['volume']>0
 exported=K.execute({'op':'export','inputs':[out],'params':{'format':'step'}})
 reopened=K.execute({'op':'import','params':{'format':'step','data':exported['data']}});near(reopened['volume'],out['volume'],1e-6)
test('free-space cubic spline sweep remains native through STEP interchange',cubic_path)
def unsupported_offset():
 carrier=Geom_OffsetCurve(Geom_Circle(gp_Circ(gp_Ax2(gp_Pnt(),gp_Dir(0,0,1)),3)),1,gp_Dir(0,0,1))
 return cq.Edge(BRepBuilderAPI_MakeEdge(carrier,0,math.pi).Edge())
test('unsupported offset carrier rejects rather than silently fitting samples',lambda:reject(lambda:C.extract_edge(unsupported_offset())))
def failed_group():
 import io
 before=io.BytesIO();box.exportBrep(before);reject(lambda:C.extract([box,unsupported_offset()],{}));after=io.BytesIO();box.exportBrep(after);assert before.getvalue()==after.getvalue()
test('one unsupported carrier aborts the whole extraction without modifying originals',failed_group)
base={'type':'spline','degree':2,'controlPoints':[[0,0,0],[1,2,0],[3,0,0]],'knots':[0,0,0,1,1,1],'weights':[1,.7,1]}
for name,change in [('weight count',{'weights':[1]}),('zero weight',{'weights':[1,0,1]}),('nonfinite pole',{'controlPoints':[[0,0,0],[1,float('inf'),0],[3,0,0]]}),('unclamped knots',{'knots':[0,0,.1,.5,1,1]}),('reversed knots',{'knots':[0,0,0,1,0,1]}),('wrong count',{'knots':[0,0,1,1]}),('boolean degree',{'degree':True}),('too high degree',{'degree':11})]:test('reject spline '+name,lambda c=change:reject(lambda:C.spline_wire({**base,**c},False)))
test('open spline refuses closed profile without inserting an invented closing segment',lambda:reject(lambda:C.spline_wire(base,True)))
failed=sum(t['status']=='failed' for t in results);out=ROOT/'tests/results';out.mkdir(exist_ok=True);(out/'native-curves-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'tests':results},indent=2)+'\n');print('RESULT',len(results)-failed,'passed',failed,'failed');sys.exit(bool(failed))
