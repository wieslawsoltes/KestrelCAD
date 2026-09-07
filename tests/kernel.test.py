#!/usr/bin/env python3
"""Exercise the actual installed OCCT kernel; no kernel mocks or fake solids."""
from pathlib import Path
import base64, io, json, math, subprocess, sys, traceback
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'tools'))
import kernel as N
results=[]
def test(name,fn):
    try:fn();results.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
    except Exception as e:traceback.print_exc();results.append({'name':name,'status':'failed','error':str(e)})
def near(a,b,tol=1e-7):assert abs(a-b)<tol*max(1,abs(b)),(a,b)
def run(op,params={},inputs=[]):return N.execute({'op':op,'params':params,'inputs':inputs})
def invalid(fn):
    try:fn()
    except (ValueError,TypeError):return
    raise AssertionError('Invalid operation was accepted')
box=run('box',{'width':20,'depth':30,'height':10})
shift=[1,0,0,0,0,1,0,0,0,0,1,0,10,0,0,1]
test('box has native analytic topology and exact mass properties',lambda:(near(box['volume'],6000),near(box['area'],2200),near(len(box['edges']),12),near(len(box['faces']),6)))
test('cylinder volume uses analytic circular surfaces',lambda:near(run('cylinder',{'radius':10,'height':20})['volume'],math.pi*2000))
test('sphere includes both hemispheres',lambda:near(run('sphere',{'radius':10})['volume'],4*math.pi*1000/3))
test('cone analytical volume',lambda:near(run('cone',{'radius1':10,'height':10})['volume'],math.pi*1000/3))
test('torus analytical volume',lambda:near(run('torus',{'major':20,'minor':5})['volume'],2*math.pi**2*20*25))
def transform():
    s=run('transform',{'matrix':shift},[box]);near(s['volume'],6000);assert min(v[0] for v in s['mesh']['vertices'])>=10-1e-7
    m=[2,0,0,0,0,3,0,0,0,0,4,0,0,0,0,1];near(run('transform',{'matrix':m},[box])['volume'],144000)
test('native translation and nonuniform affine scaling',transform)
other=run('transform',{'matrix':shift},[box])
for op,volume in [('union',9000),('subtract',3000),('intersect',3000)]:test('B-rep '+op,lambda o=op,v=volume:near(run(o,inputs=[box,other])['volume'],v))
test('solid-edge fillet creates a curved face and correct volume',lambda:near(run('fillet',{'edges':[0],'radius':2},[box])['volume'],6000-(4-math.pi)*10))
test('solid-edge chamfer removes a triangular prism',lambda:near(run('chamfer',{'edges':[0],'distance':2},[box])['volume'],5980))
test('shell removes a selected face and hollows the solid',lambda:near(run('shell',{'faces':[5],'thickness':-1},[box])['volume'],6000-18*28*9))
def section():
    r=run('section',{'origin':[0,0,5]},[box]);assert r['valid'] and r['solidCount']==0 and len(r['edges'])==4;near(sum(e['length'] for e in r['edges']),100)
test('plane section contains native intersection curves',section)
rect={'type':'polyline','points':[[0,0,0],[20,0,0],[20,10,0],[0,10,0]]}
circle={'type':'circle','center':[10,5,0],'radius':2}
test('extrusion preserves an analytic inner hole',lambda:near(run('extrude',{'profile':rect,'holes':[circle],'vector':[0,0,10]})['volume'],2000-40*math.pi))
test('bulged polyline extrusion uses true arc edges',lambda:near(run('extrude',{'profile':{'type':'polyline','points':[[0,0,0],[10,0,0],[10,10,0],[0,10,0]],'bulges':[1,0,0,0]},'vector':[0,0,5]})['volume'],500+62.5*math.pi))
def revolve():
    p={'type':'polyline','points':[[10,0,0],[15,0,0],[15,0,8],[10,0,8]]};r=run('revolve',{'profile':p,'axisStart':[0,0,0],'axisEnd':[0,0,1]});near(r['volume'],math.pi*(225-100)*8)
test('native revolve creates an annular solid',revolve)
def loft():
    a={'type':'circle','radius':10,'center':[0,0,0]};b={'type':'circle','radius':20,'center':[0,0,30]};near(run('loft',{'profiles':[a,b]})['volume'],math.pi*30*(100+200+400)/3,1e-5)
test('native loft creates valid curved B-rep',loft)
def sweep():
    profile={'type':'circle','radius':2,'center':[0,0,0]};path={'type':'polyline','points':[[0,0,0],[0,0,50]]};near(run('sweep',{'profile':profile,'path':path})['volume'],math.pi*4*50)
test('native sweep along a path',sweep)
for fmt in ('brep','step'):
    def roundtrip(f=fmt):
        r=run('export',{'format':f},[box]);out=run('import',{'format':f,'data':r['data']});near(out['volume'],6000);assert out['solidCount']==1
    test(fmt.upper()+' genuine native round trip',roundtrip)
def step_units():
    r=run('export',{'format':'step','scale':25.4},[box]);out=run('import',{'format':'step','scale':1/25.4,'data':r['data']});near(out['volume'],6000)
test('STEP unit conversion round trip',step_units)
def iges():
    r=run('export',{'format':'iges'},[box]);out=run('import',{'format':'iges','data':r['data']});near(out['area'],2200);assert out['solidCount']==0  # surfaces are not falsely reported as closed solids
    assert out['valid']
test('IGES surface exchange is explicitly not certified solid topology',iges)
def stl():
    r=run('export',{'format':'stl'},[box]);assert r['bytes']>100;assert len(base64.b64decode(r['data']))==r['bytes']
test('STL export contains a real display tessellation',stl)
def protocol():
    p=subprocess.run([sys.executable,str(ROOT/'tools/kernel.py')],input=json.dumps({'op':'inspect','inputs':[box]}),text=True,capture_output=True,timeout=30);near(json.loads(p.stdout)['result']['volume'],6000)
test('subprocess protocol isolates native stdout diagnostics',protocol)
for name,fn in [
    ('unknown operation',lambda:run('python',{'code':'1+1'})),
    ('nonfinite dimension',lambda:run('box',{'width':float('nan'),'depth':1,'height':1})),
    ('negative radius',lambda:run('sphere',{'radius':-1})),
    ('singular transform',lambda:run('transform',{'matrix':[0]*16},[box])),
    ('missing body',lambda:run('fillet',{'radius':2,'edges':[0]})),
    ('bad topology index',lambda:run('fillet',{'radius':2,'edges':[999]},[box])),
    ('duplicate edge indices',lambda:run('chamfer',{'distance':2,'edges':[0,0]},[box])),
    ('mesh is not an exact solid',lambda:run('inspect',inputs=[{'provider':'MESH','brep':box['brep']}])),
    ('invalid native stream',lambda:run('inspect',inputs=[{'provider':'OCCT','brep':base64.b64encode(b'fake').decode()}])),
    ('empty intersection is rejected',lambda:run('intersect',inputs=[box,run('transform',{'matrix':[1,0,0,0,0,1,0,0,0,0,1,0,1000,0,0,1]},[box])])),
    ('zero extrusion',lambda:run('extrude',{'profile':rect,'vector':[0,0,0]})),
    ('unsupported SAT import',lambda:run('import',{'format':'sat','data':'YWJj'})),
    ('path input is not a file read',lambda:run('import',{'format':'step','path':'/etc/passwd'})),
]:test('reject '+name,lambda f=fn:invalid(f))
failed=sum(t['status']=='failed' for t in results)
(ROOT/'tests/results/kernel-results.json').write_text(json.dumps({'suite':'actual OCCT native kernel','passed':len(results)-failed,'failed':failed,'tests':results},indent=2)+'\n')
print(f'Kernel: {len(results)-failed} passed, {failed} failed')
raise SystemExit(bool(failed))
