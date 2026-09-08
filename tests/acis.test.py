#!/usr/bin/env python3
"""Real OCCT/SAT/SAB geometry tests; no codec or topology mocks."""
from pathlib import Path
import base64, io, json, math, sys, traceback
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'tools'))
import acis_exchange as A
import kernel as N
import cadquery as cq
from ezdxf.acis import api, entities as E
from ezdxf.math import Matrix44
from ezdxf.render import forms
results=[]
def test(name, fn):
    try: fn(); results.append({'name':name,'status':'passed'}); print('PASS',name,flush=True)
    except Exception as exc: traceback.print_exc(); results.append({'name':name,'status':'failed','error':str(exc)})
def near(a,b,tol=1e-8): assert abs(a-b)<tol*max(1,abs(b)), (a,b)
def invalid(fn, text=''):
    try: fn()
    except (ValueError,TypeError) as exc:
        assert text.lower() in str(exc).lower(),str(exc); return
    raise AssertionError('Invalid geometry/file was accepted')
def encoded(bodies,fmt='sat',unit=1): return A.encode_bodies(bodies,fmt,unit)
def roundtrip(shape, fmt='sat'):
    data=A.export_geometry([shape],fmt); restored,report=A.import_geometry(data,fmt)
    assert len(restored)==1 and restored[0].isValid(); out=restored[0]
    near(out.Area(),shape.Area()); near(out.Volume(),shape.Volume()); assert len(out.Faces())==len(shape.Faces()); return out
box=cq.Solid.makeBox(20,30,10)
for fmt in ('sat','sab'):
    def basic(f=fmt):
        out=roundtrip(box,f); assert len(out.Edges())==12 and len(out.Faces())==6 and len(out.Solids())==1
        assert all(face.geomType()=='PLANE' for face in out.Faces())
        assert all(edge.geomType()=='LINE' for edge in out.Edges())
    test(fmt.upper()+' box preserves actual six-face topology without triangulating it',basic)
    test(fmt.upper()+' rectangular through-hole retains inner face loops',lambda f=fmt: roundtrip(box.cut(cq.Solid.makeBox(4,6,20,(8,12,-5))).clean(),f))
    def cavity(f=fmt):
        out=roundtrip(box.cut(cq.Solid.makeBox(4,6,4,(8,12,3))).clean(),f); assert len(out.Shells())==2;near(out.Volume(),5904)
    test(fmt.upper()+' closed internal cavity preserves void shell and volume',cavity)
    test(fmt.upper()+' disconnected lumps preserve all components',lambda f=fmt: roundtrip(cq.Compound.makeCompound([box,box.translate((40,0,0))]),f))
    def surface(f=fmt):
        face=cq.Face.makeFromWires(cq.Wire.makePolygon([(0,0,0),(10,0,0),(10,10,0),(0,10,0)],close=True),[cq.Wire.makePolygon([(2,2,0),(8,2,0),(8,8,0),(2,8,0)],close=True)])
        out=roundtrip(face,f); assert not out.Solids();near(out.Area(),64)
    test(fmt.upper()+' bounded planar sheet with hole remains a surface, not a fake solid',surface)
    def multi(f=fmt):
        data=A.export_geometry([box,box.translate((70,0,0))],f);out,report=A.import_geometry(data,f);assert len(out)==2;near(out[1].Center().x,80)
    test(fmt.upper()+' multi-body file imports every root',multi)
    def external(f=fmt):
        b=api.body_from_mesh(forms.cube());data=('\n'.join(api.export_sat([b]))+'\n').encode() if f=='sat' else api.export_sab([b]);out,_=A.import_geometry(data,f);near(out[0].Volume(),1)
    test(fmt.upper()+' independently authored ezdxf cube imports as native solid',external)
    def inch(f=fmt):
        data=A.export_geometry([box],f,25.4);out,report=A.import_geometry(data,f,1);near(out[0].Volume(),6000*25.4**3);near(report['scale'],25.4)
        out,_=A.import_geometry(data,f,25.4);near(out[0].Volume(),6000)
    test(fmt.upper()+' file unit headers scale physical geometry explicitly',inch)
    def pose(f=fmt):
        shape=box.rotate((0,0,0),(1,2,3),37).translate((100.123456789,-2.234567891,8.876543219))
        out=roundtrip(shape,f);near(out.Center().x,shape.Center().x,1e-11)
    test(fmt.upper()+' rotated and translated planar body retains dimensional precision',pose)

def transformed():
    b=A.bodies_from_shapes([box])[0];b.transform=E.Transform();b.transform.matrix=Matrix44.translate(7,8,9)
    out,_=A.import_geometry(encoded([b]),'sat');near(out[0].Center().x,17);near(out[0].Center().y,23);near(out[0].Center().z,14)
test('source body transform applies exactly once',transformed)
def reflection():
    s=N.affine(box,[-1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]);out=roundtrip(s);near(out.Center().x,-10)
test('reflected planar B-rep retains outward orientation and positive volume',reflection)
def skew():
    s=N.affine(box,[2,0,0,0,.2,3,0,0,0,0,4,0,0,0,0,1])
    # OCCT GTransform promotes surfaces; no covert conversion to polygons.
    invalid(lambda:A.export_geometry([s]),'curved')
test('general affine B-spline promotion rejects rather than chordalizes on export',skew)

def unitless():
    raw=A.export_geometry([box]).decode().splitlines();raw[2]='-1 1e-6 1e-10';data=('\n'.join(raw)+'\n').encode()
    invalid(lambda:A.import_geometry(data,'sat'),'unitless');out,_=A.import_geometry(data,'sat',1,25.4);near(out[0].Volume(),6000*25.4**3)
test('unitless source requires an explicit source-unit override',unitless)
for label,fn,text in [
 ('unknown format',lambda:A.import_geometry(b'abc','step'),'format'),
 ('invalid SAT stream',lambda:A.import_geometry(b'garbage','sat'),'invalid'),
 ('invalid SAB stream',lambda:A.import_geometry(b'garbage','sab'),'invalid'),
 ('empty stream',lambda:A.import_geometry(b'','sat'),'input'),
 ('oversized source',lambda:A.import_geometry(b'0'*(A.MAX_BYTES+1),'sat'),'input'),
 ('unsupported format version',lambda:A.import_geometry(A.export_geometry([box]).replace(b'700 ',b'800 ',1),'sat'),'version'),
 ('curved native cylinder',lambda:A.export_geometry([cq.Solid.makeCylinder(4,10)]),'curved'),
 ('mixed curved and planar bodies',lambda:A.export_geometry([box,cq.Solid.makeSphere(4)]),'curved'),
 ('ordinary source text cannot supply a path',lambda:N.execute({'op':'acis-import','params':{'format':'sat','path':'/etc/passwd'}}),'payload'),
 ('loose edges cannot disappear',lambda:A.export_geometry([cq.Compound.makeCompound([box,cq.Edge.makeLine((50,0,0),(60,0,0))])]),'loose'),
 ('invalid unit metadata',lambda:A.export_geometry([box],unit_mm=float('nan')),'unit'),
 ('no selected bodies',lambda:A.export_geometry([]),'bodies')
]: test(label+' is rejected',lambda f=fn,t=text:invalid(f,t))

def bad_geometry():
    data=A.export_geometry([box]).replace(b'plane-surface',b'spline-surface')
    invalid(lambda:A.import_geometry(data,'sat'),'curved')
test('unsupported source surface is rejected before any planar faces are returned',bad_geometry)
def bad_curve():
    data=A.export_geometry([box]).replace(b'straight-curve',b'intcurve-curve')
    invalid(lambda:A.import_geometry(data,'sat'),'curved')
test('unsupported source curve is rejected, not replaced by endpoint chords',bad_curve)
def bad_cycle():
    b=A.bodies_from_shapes([box])[0];f=b.lump.shell.face;f.next_face=f
    invalid(lambda:A.import_geometry(encoded([b]),'sat'),'cycle')
test('malformed face cycle terminates with a bounded validation error',bad_cycle)
def missing_partner():
    b=A.bodies_from_shapes([box])[0];b.lump.shell.face.loop.coedge.partner_coedge=E.NONE_REF
    invalid(lambda:A.import_geometry(encoded([b]),'sat'),'partner')
test('missing shared-edge partner cannot manufacture a falsely valid solid',missing_partner)
def wrong_param():
    b=A.bodies_from_shapes([box])[0];b.lump.shell.face.loop.coedge.edge.start_param=5
    invalid(lambda:A.import_geometry(encoded([b]),'sat'),'parameters')
test('edge parameters must agree with their actual endpoint vertices',wrong_param)
def open_solid():
    b=A.bodies_from_shapes([box])[0];b.lump.shell.face.next_face=E.NONE_REF
    invalid(lambda:A.import_geometry(encoded([b]),'sat'),'open')
test('open single-sided shell is not promoted to a closed solid',open_solid)
def native_ops():
    packed=N.pack(box,.1)
    out=N.execute({'op':'acis-export','inputs':[packed],'params':{'format':'sat'}})
    restored=N.execute({'op':'acis-import','params':{'format':'sat','data':out['data']}})
    assert restored['exchange']['geometryOnly'] and len(restored['exchange']['sha256'])==64
    body=restored['bodies'][0];near(body['volume'],6000);assert body['provider']=='OCCT'
    fillet=N.execute({'op':'fillet','inputs':[body],'params':{'edges':[0],'radius':1}});assert fillet['solidCount']==1 and fillet['volume']<6000
    step=N.execute({'op':'export','inputs':[body],'params':{'format':'step'}})
    check=N.execute({'op':'import','params':{'format':'step','data':step['data']}});near(check['volume'],6000)
test('SAT import feeds real native fillets and STEP export, not a display-only body',native_ops)
failed=sum(t['status']=='failed' for t in results)
out=ROOT/'tests/results';out.mkdir(exist_ok=True)
(out/'acis-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'tests':results},indent=2)+'\n')
print('RESULT',len(results)-failed,'passed;',failed,'failed');sys.exit(bool(failed))
