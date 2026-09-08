#!/usr/bin/env python3
"""Actual OCCT material, transport payload, and failure-boundary checks."""
from pathlib import Path
import base64, io, json, math, sys, traceback
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'tools'))
import cadquery as cq
import kernel as K
import native_analysis as A
OUT=ROOT/'tests/results';OUT.mkdir(exist_ok=True);tests=[]
def test(name,fn):
    try:fn();tests.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
    except Exception as e:traceback.print_exc();tests.append({'name':name,'status':'failed','error':str(e)})
def near(a,b,tol=1e-6):assert abs(a-b)<=tol*max(1,abs(b)),(a,b)
def bad(fn,word=''):
    try:fn()
    except (ValueError,TypeError) as e:assert word.lower() in str(e).lower(),str(e);return
    raise AssertionError('Expected rejection')
def eq(a,b):assert a==b,(a,b)
box=cq.Solid.makeBox(10,10,10)
def pair(other,**p):return A.analyze([box,other],p)
def row(other,**p):return pair(other,**p)['pairs'][0]
def payload(shape,matrix=None):
    s=io.BytesIO();shape.exportBrep(s)
    return {'provider':'OCCT','brep':base64.b64encode(s.getvalue()).decode(),**({'transform':matrix} if matrix is not None else {})}
for shift,state in [(5,'interference'),(10,'contact'),(10.001,'clearance'),(13,'separated')]:
    test('classifies shift '+str(shift),lambda shift=shift,state=state:eq(row(box.translate((shift,0,0)),clearance=1)['status'],state))
test('exact overlapping cube volume',lambda:near(row(box.translate((5,0,0)))['volume'],500))
test('separated minimum distance, not center distance',lambda:near(row(box.translate((13,0,0)))['distance'],3))
def witnesses():
    r=row(box.translate((13,2,3)))
    for p,q in r['witnesses']:near(math.dist(p,q),r['distance'])
    assert r['witnessCount']>=len(r['witnesses'])
test('minimum-distance witness pairs agree',witnesses)
test('edge contact has zero volume',lambda:near(row(box.translate((10,10,0)))['volume'],0))
test('vertex contact is reported',lambda:eq(row(box.translate((10,10,10)))['status'],'contact'))
test('equal clearance threshold is not a violation',lambda:eq(row(box.translate((12,0,0)),clearance=2)['status'],'separated'))
test('positive tolerance gaps are contact, not overlap',lambda:eq(row(box.translate((10.00001,0,0)),contactTolerance=.0001)['status'],'contact'))
test('contact tolerance is not a fuzzy Boolean enlargement',lambda:near(row(box.translate((10.00001,0,0)),contactTolerance=.01)['volume'],0))
test('contained body has its material volume',lambda:near(row(cq.Solid.makeBox(2,2,2,(4,4,4)))['volume'],8))
test('identical bodies overlap exactly once',lambda:near(row(box.copy())['volume'],1000))
def hollow():
    shell=box.cut(cq.Solid.makeBox(8,8,8,(1,1,1)))
    result=A.analyze([shell,cq.Solid.makeBox(1,1,1,(4,4,4))],{})['pairs'][0]
    near(result['volume'],0);near(result['distance'],3);eq(result['status'],'separated')
test('body inside cavity is not an interference',hollow)
def spheres():
    sphere=cq.Solid.makeSphere(5,angleDegrees1=-90,angleDegrees2=90)
    r=A.analyze([sphere,sphere.translate((5,0,0))],{})['pairs'][0]
    near(r['volume'],math.pi*25*25/12,2e-5)
test('curved sphere intersection is integrated analytically',spheres)
def cylinders():
    s=cq.Solid.makeCylinder(3,10)
    near(A.analyze([s,s.translate((0,0,5))],{})['pairs'][0]['volume'],math.pi*9*5)
test('coaxial curved cylinder overlap',cylinders)
def regions():
    data=pair(box.translate((5,0,0)),regions=True)
    assert len(data['bodies'])==1
    solid=K.read_shape(data['bodies'][0]);near(solid.Volume(),500);assert solid.isValid()
    step=K.execute({'op':'export','inputs':[data['bodies'][0]],'params':{'format':'step'}})
    restored=K.execute({'op':'import','params':{'format':'step','data':step['data']}})
    near(restored['volume'],500)
test('retained overlap BREP survives actual STEP roundtrip',regions)
test('analysis without region generation omits BREP results',lambda:eq(pair(box.translate((5,0,0)))['bodies'],[]))
test('contact creates no false overlap solid',lambda:eq(pair(box.translate((10,0,0)),regions=True)['bodies'],[]))
def compound():
    source=cq.Compound.makeCompound([box,box.translate((5,0,0))])
    other=cq.Solid.makeBox(30,30,30,(-5,-5,-5))
    near(A.analyze([source,other],{})['pairs'][0]['volume'],1500)
test('overlapping solids inside one compound are unioned before counting',compound)
def separate_compound():
    source=cq.Compound.makeCompound([box,box.translate((20,0,0))])
    other=cq.Solid.makeBox(40,30,30,(-5,-5,-5))
    near(A.analyze([source,other],{})['pairs'][0]['volume'],2000)
test('disconnected compound material is retained',separate_compound)
def transformed():
    data=payload(box,[1,0,0,0,0,1,0,0,0,0,1,0,13,0,0,1]);r=K.execute({'op':'interference','inputs':[payload(box),data]})
    near(r['pairs'][0]['distance'],3)
test('server execute reads authoritative transformed BREP',transformed)
def reflected():
    data=payload(box,[-1,0,0,0,0,1,0,0,0,0,1,0,15,0,0,1]);r=K.execute({'op':'interference','inputs':[payload(box),data]})
    near(r['pairs'][0]['volume'],500)
test('reflected placements preserve overlap volume',reflected)
def scaled():
    m=[2,0,0,0,0,1,0,0,0,0,1,0,5,0,0,1]
    r=K.execute({'op':'interference','inputs':[payload(box),payload(box,m)]})
    near(r['pairs'][0]['volume'],500)
test('nonuniform native placement is not approximated by mesh',scaled)
def immutable():
    inputs=[payload(box),payload(box.translate((5,0,0)))];before=json.dumps(inputs,sort_keys=True)
    K.execute({'op':'interference','inputs':inputs,'params':{'regions':True}})
    eq(json.dumps(inputs,sort_keys=True),before)
test('request BREP streams and placements remain unchanged',immutable)
test('AABB rejection avoids irrelevant Booleans but retains exact gap',lambda:eq(pair(box.translate((30,0,0)))['booleanChecks'],0))
test('overlapping boxes trigger native Boolean',lambda:eq(pair(box.translate((5,0,0)))['booleanChecks'],1))
test('all-pairs plan is unique',lambda:eq(A.pairs(3,{}),[(0,1),(0,2),(1,2)]))
test('two-set duplicate membership belongs only to A',lambda:eq(A.pairs(4,{'groups':{'first':[0,1],'second':[1,2,3]}}),[(0,2),(0,3),(1,2),(1,3)]))
test('same-only sets reject empty comparison',lambda:bad(lambda:A.pairs(2,{'groups':{'first':[0],'second':[0]}}),'pairs'))
test('pair safety limit refuses unbounded quadratic work',lambda:bad(lambda:A.pairs(32,{}),'128'))
test('split sets allow bounded subset of 32 inputs',lambda:eq(len(A.pairs(32,{'groups':{'first':[0],'second':list(range(1,32))}})),31))
test('duplicate indices rejected',lambda:bad(lambda:A.pairs(3,{'groups':{'first':[0,0],'second':[1]}}),'duplicate'))
test('boolean index rejected',lambda:bad(lambda:A.pairs(3,{'groups':{'first':[True],'second':[1]}}),'indices'))
test('unknown groups rejected',lambda:bad(lambda:A.pairs(3,{'groups':{'a':[0],'b':[1]}}),'groups'))
test('missing native body rejected',lambda:bad(lambda:A.analyze([box],{}),'2–32'))
test('surface rejected before volume classification',lambda:bad(lambda:A.analyze([box,box.Faces()[0]],{}),'pure'))
test('mixed compound cannot discard stray surface',lambda:bad(lambda:A.analyze([box,cq.Compound.makeCompound([box,box.Faces()[0]])],{}),'pure'))
for name,params in [('negative clearance',{'clearance':-1}),('nan clearance',{'clearance':math.nan}),('zero tolerance',{'contactTolerance':0}),('string toggle',{'regions':'yes'})]:
    test('reject '+name,lambda params=params:bad(lambda:A.analyze([box,box],params)))
def multisets():
    r=A.analyze([box,box.translate((5,0,0)),box.translate((40,0,0))],{'groups':{'first':[0,1],'second':[2]},'regions':True})
    eq(r['pairCount'],2);eq(r['counts']['separated'],2);eq(r['bodies'],[])
test('two-set execution reports exact operand indices',multisets)
failed=sum(t['status']=='failed' for t in tests)
(OUT/'native-analysis-results.json').write_text(json.dumps({'passed':len(tests)-failed,'failed':failed,'tests':tests},indent=2)+'\n')
print('RESULT',len(tests)-failed,'passed;',failed,'failed');sys.exit(bool(failed))
