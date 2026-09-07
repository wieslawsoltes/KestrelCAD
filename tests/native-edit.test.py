#!/usr/bin/env python3
"""Actual OCCT tests for surfaces, analytic slicing and integrated mass properties."""
from pathlib import Path
import io, json, math, sys, traceback
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'tools'))
import kernel as K
import cadquery as cq
results=[]
def test(name,fn):
    try:fn();results.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
    except Exception as e:traceback.print_exc();results.append({'name':name,'status':'failed','error':str(e)})
def near(a,b,tol=1e-6): assert abs(a-b)<=tol*max(1,abs(b)), (a,b)
def run(op,params=None,inputs=None):return K.execute({'op':op,'params':params or {},'inputs':inputs or []})
def reject(fn):
    try:fn()
    except (ValueError,TypeError):return
    raise AssertionError('Invalid request was accepted')
box=run('box',{'width':20,'depth':30,'height':10})
circle={'type':'circle','center':[0,0,0],'radius':10}
rect={'type':'polyline','points':[[0,0,0],[20,0,0],[20,30,0],[0,30,0]]}
surface=run('plane-surface',{'profile':circle})
test('closed analytic disk is a native surface, not a volume',lambda:(near(surface['area'],100*math.pi),near(surface['solidCount'],0)))
for thickness in [2,-2]:
    test('signed surface thickening '+str(thickness),lambda t=thickness:near(run('thicken',{'thickness':t},[surface])['volume'],200*math.pi))
def hole():
    s=run('plane-surface',{'profile':circle,'holes':[{'type':'circle','radius':3}]})
    near(s['area'],91*math.pi);near(run('thicken',{'thickness':4},[s])['volume'],364*math.pi)
test('surface holes remain analytic through thickening',hole)
def curved():
    cylinder=run('cylinder',{'radius':10,'height':20})
    index=next(f['index'] for f in cylinder['faces'] if f['type']=='CYLINDER')
    face=run('extract-faces',{'faces':[index]},[cylinder])['bodies'][0]
    near(face['solidCount'],0)
    near(run('thicken',{'thickness':2},[face])['volume'],math.pi*(12**2-10**2)*20)
test('extract and thicken a curved cylindrical face',curved)
def split(keep='both'):
    return run('slice',{'origin':[10,0,0],'normal':[1,0,0],'keep':keep},[box])['bodies']
test('analytic slice returns two independently serializable bodies',lambda:(near(len(split()),2),*[near(b['volume'],3000) for b in split()]))
for side in ['positive','negative']:
    def keep(s=side):
        bodies=split(s);assert len(bodies)==1 and bodies[0]['side']==s
        mass=run('massprops',inputs=bodies);near(mass['centroid'][0],15 if s=='positive' else 5)
    test('slice retains requested '+side+' half',keep)
def inclined():
    halves=run('slice',{'origin':[10,15,5],'normal':[2,3,4]},[box])['bodies']
    near(sum(h['volume'] for h in halves),6000);near(halves[0]['volume'],3000)
    for h in halves:assert K.read_shape(h).isValid()
test('inclined infinite plane conserves solid volume',inclined)
def diskslice():
    halves=run('slice',{'origin':[0,0,0],'normal':[1,0,0]},[surface])['bodies']
    near(sum(h['area'] for h in halves),surface['area']);assert all(h['solidCount']==0 for h in halves)
test('native surface slicing conserves area',diskslice)
def multiple():
    halves=run('slice',{'origin':[10,0,0],'normal':[1,0,0]},[box,box])['bodies']
    assert [h['sourceIndex'] for h in halves]==[0,0,1,1]
test('batch slices retain source correspondence',multiple)
def compound():
    c=cq.Compound.makeCompound([cq.Solid.makeBox(2,3,4),cq.Solid.makeBox(2,3,4).translate((10,0,0))])
    b=K.pack(c,.1);parts=run('separate',inputs=[b])['bodies'];assert len(parts)==2
    near(sum(p['volume'] for p in parts),48)
    step=run('export',{'format':'step'},[b]);again=run('import',{'format':'step','data':step['data']})
    assert again['solidCount']==2;near(again['volume'],48)
test('composite separation and STEP import retain all roots',compound)
def mass():
    p=run('massprops',{'density':2.5},[box]);near(p['mass'],15000);near(p['volume'],6000)
    assert p['centroid']==[10,15,5]
    for i,v in enumerate([500000,250000,650000]):near(p['inertia'][i][i],v*2.5)
    assert len(p['principalAxes'])==3
test('uniform-density centroidal inertia matches analytic box',mass)
def moved():
    b=dict(box,transform=[2,0,0,0,0,3,0,0,0,0,4,0,100,200,300,1])
    p=run('massprops',inputs=[b]);near(p['volume'],144000)
    assert all(abs(a-b)<1e-5 for a,b in zip(p['centroid'],[120,245,320]))
    near(p['inertia'][0][0],144000*(90**2+40**2)/12)
test('mass properties use authoritative affine-transformed solids',moved)
def additive():
    p=run('massprops',inputs=[box,box]);near(p['mass'],12000);assert 'additive' in p['overlapPolicy']
test('multiple bodies use explicit additive overlap policy',additive)
for name,call in [
    ('zero normal',lambda:run('slice',{'normal':[0,0,0]},[box])),
    ('nonintersecting plane',lambda:run('slice',{'origin':[100,0,0],'normal':[1,0,0]},[box])),
    ('tangent plane',lambda:run('slice',{'origin':[20,0,0],'normal':[1,0,0]},[box])),
    ('unknown side',lambda:run('slice',{'keep':'all'},[box])),
    ('zero thickness',lambda:run('thicken',{'thickness':0},[surface])),
    ('solid is not a thickenable face',lambda:run('thicken',{'thickness':2},[box])),
    ('surface has no volume mass',lambda:run('massprops',inputs=[surface])),
    ('negative density',lambda:run('massprops',{'density':-1},[box])),
    ('single solid cannot be separated',lambda:run('separate',inputs=[box])),
    ('duplicate face indices',lambda:run('extract-faces',{'faces':[0,0]},[box])),
    ('noncoplanar profile',lambda:run('plane-surface',{'profile':{'type':'polyline','points':[[0,0,0],[5,0,0],[5,5,2],[0,5,0]]}})),
]:test('reject '+name,lambda fn=call:reject(fn))
failed=sum(r['status']=='failed' for r in results)
(ROOT/'tests/results').mkdir(exist_ok=True)
(ROOT/'tests/results/native-edit-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'tests':results},indent=2))
print('RESULT',len(results)-failed,'passed;',failed,'failed');sys.exit(bool(failed))
