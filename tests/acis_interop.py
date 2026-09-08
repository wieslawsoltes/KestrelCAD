#!/usr/bin/env python3
"""Independent ACIS/DXF decoding and topology checks, not commercial certification."""
from pathlib import Path
import io,json,sys,traceback
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'tools'))
import cadquery as cq
import ezdxf
from ezdxf.acis import api
import acis_exchange as A
results=[]
def test(name,fn):
    try:fn();results.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
    except Exception as e:traceback.print_exc();results.append({'name':name,'status':'failed','error':str(e)})
box=cq.Solid.makeBox(20,30,10).rotate((0,0,0),(1,2,3),33)
for version in ('R2000','R2010','R2013','R2018'):
    def check(v=version):
        data=A.export_dxf([box,box.translate((100,0,0))],v,'in')
        doc=ezdxf.read(io.StringIO(data.decode('cp1252')));audit=doc.audit()
        assert not audit.errors and not audit.fixes,(audit.errors,audit.fixes)
        assert doc.units==1 and len(doc.modelspace())==2
        for e in doc.modelspace():
            assert e.dxftype()=='3DSOLID';bodies=api.load_dxf(e);assert len(bodies)==1
            faces=bodies[0].lump.shell.faces()
            assert len(faces)==6 and all(f.surface.type=='plane-surface' for f in faces)
            assert sum(len(f.loop.coedges()) for f in faces)==24
            assert bool(e.sab)==(v in ('R2013','R2018'))
            out,_=A.import_geometry(e.sab if e.sab else ('\n'.join(e.sat)+'\n').encode(),'sab' if e.sab else 'sat',25.4)
            assert abs(out[0].Volume()-6000)<1e-5
    test(version+' genuine 3DSOLID payloads, units and zero-repair audit',check)
def high_precision():
    b=api.load(A.export_geometry([box]).decode())[0]
    for f in b.lump.shell.faces():
        for loop in f.loops():
            for c in loop.coedges():
                edge=c.edge
                assert (edge.curve.evaluate(edge.start_param)-edge.start_vertex.point.location).magnitude<1e-11
                assert abs((edge.start_vertex.point.location-f.surface.origin).dot(f.surface.normal))<1e-11
    assert len(api.mesh_from_body(b)[0].faces)==6
    from ezdxf.acis.sat import SatDataExporter
    assert SatDataExporter.write_double.__module__=='ezdxf.acis.sat'
test('External SAT decoder sees precise planes and vertices without a global writer mutation',high_precision)
def holes():
    shape=cq.Solid.makeBox(20,30,10).cut(cq.Solid.makeBox(4,6,20,(8,12,-5))).clean()
    faces=api.load(A.export_geometry([shape]).decode())[0].lump.shell.faces()
    assert len(faces)==10 and sum(len(f.loops())==2 for f in faces)==2
    assert sum(len(f.loops()) for f in faces)==12
test('External decoder retains two inner-loop faces for a rectangular through-hole',holes)
def surfaces():
    face=cq.Face.makeFromWires(cq.Wire.makePolygon([(0,0,0),(10,0,0),(10,10,0),(0,10,0)],close=True))
    doc=ezdxf.read(io.StringIO(A.export_dxf([face]).decode()));audit=doc.audit();assert not audit.errors and not audit.fixes
    e=next(iter(doc.modelspace()));assert e.dxftype()=='BODY'
    assert all(f.double_sided for f in api.load_dxf(e)[0].lump.shell.faces())
test('Open planar geometry is a two-sided BODY, not a falsely closed 3DSOLID',surfaces)
failed=sum(r['status']=='failed' for r in results);(ROOT/'tests/results/acis-interop-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'tests':results},indent=2)+'\n');print('RESULT',len(results)-failed,'passed;',failed,'failed');sys.exit(bool(failed))
