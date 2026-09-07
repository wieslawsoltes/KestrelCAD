#!/usr/bin/env python3
"""Independent DXF producer/auditor. Requires ezdxf; not an app dependency.
Run before and after `node tests/core.test.js` to create/verify interop fixtures.
"""
from pathlib import Path
import json
import math
import sys
import ezdxf
from ezdxf.math import Vec3

ROOT=Path(__file__).resolve().parent.parent
FIXTURES=ROOT/'tests/fixtures'
RESULTS=ROOT/'tests/results'
FIXTURES.mkdir(exist_ok=True)
RESULTS.mkdir(exist_ok=True)
results=[]

def record(name,fn):
    try:
        detail=fn()
        results.append({'name':name,'status':'passed','detail':detail})
        print('PASS',name,detail or '')
    except Exception as exc:
        results.append({'name':name,'status':'failed','error':str(exc)})
        print('FAIL',name,repr(exc))

# A real independent producer, not the app's own DXF writer.
doc=ezdxf.new('R2000',setup=True)
doc.units=4
msp=doc.modelspace()
for name in ['EXTERNAL','OCS-CIRCLE','BLOCK-3D','ARRAY-SCALED','OCS-POLYLINE','MTEXT-DIRECTION']:
    doc.layers.new(name,dxfattribs={'color':3})
for i in range(12):
    msp.add_line((i*10,0,0),(i*10+5,40,3),dxfattribs={'layer':'EXTERNAL'})
msp.add_circle((3,4,5),radius=7,dxfattribs={'layer':'OCS-CIRCLE','extrusion':(0,1,1)})
msp.add_lwpolyline([(0,0,0,0,1),(10,0,0,0,0),(10,10,0,0,0)],format='xyseb',close=True,dxfattribs={'layer':'OCS-POLYLINE','elevation':5,'extrusion':(0,1,1)})
msp.add_open_spline([(0,0,0),(10,30,0),(20,-10,0),(30,0,0)],degree=3,dxfattribs={'layer':'EXTERNAL'})
msp.add_rational_spline([(1,0,0),(1,1,0),(0,1,0)],weights=[1,math.sqrt(.5),1],degree=2,dxfattribs={'layer':'EXTERNAL'})
msp.add_text('±BOLT · Żółć Ω 😀',dxfattribs={'insert':(0,-10,0),'height':3,'rotation':30,'layer':'EXTERNAL'})
msp.add_mtext('DIRECTION\\PSECOND LINE',dxfattribs={'insert':(30,-20,0),'char_height':4,'text_direction':(0,1,0),'layer':'MTEXT-DIRECTION'})
block=doc.blocks.new('TEST_BLOCK',base_point=(1,2,0))
block.add_line((1,2,0),(11,2,0))
block.add_circle((5,5,0),radius=2)
ins=msp.add_blockref('TEST_BLOCK',(20,30,4),dxfattribs={'layer':'BLOCK-3D','rotation':35,'xscale':2,'yscale':2,'zscale':2,'extrusion':(.2,.5,1)})
arr=msp.add_blockref('TEST_BLOCK',(100,0,0),dxfattribs={'layer':'ARRAY-SCALED','rotation':30,'xscale':2,'yscale':3})
arr.grid((2,3),(20,30))
expected={}
expected['BLOCK-3D']=[[list(e.dxf.start),list(e.dxf.end)] for e in ins.virtual_entities() if e.dxftype()=='LINE']
expected['ARRAY-SCALED']=[[list(e.dxf.start),list(e.dxf.end)] for instance in arr.multi_insert() for e in instance.virtual_entities() if e.dxftype()=='LINE']
hatch=msp.add_hatch(color=4,dxfattribs={'layer':'EXTERNAL'})
hatch.paths.add_polyline_path([(0,50),(20,50),(20,70),(0,70)],is_closed=True)
hatch.set_pattern_fill('ANSI31',scale=2)
bulged=msp.add_hatch(color=5,dxfattribs={'layer':'EXTERNAL'})
bulged.paths.add_polyline_path([(0,80,1),(20,80,0),(20,100,0),(0,100,0)],is_closed=True)
face=msp.add_polyface(dxfattribs={'layer':'EXTERNAL'})
face.append_faces([[(100,100,0),(110,100,0),(110,110,0),(100,110,0)],[(100,100,0),(100,100,10),(110,100,10),(110,100,0)]])
msp.add_aligned_dim(p1=(0,0),p2=(80,20),distance=10,dimstyle='EZDXF',dxfattribs={'layer':'EXTERNAL'}).render()
msp.add_linear_dim(base=(0,-30),p1=(0,0),p2=(80,20),angle=0,dimstyle='EZDXF',dxfattribs={'layer':'EXTERNAL'}).render()
doc.saveas(FIXTURES/'external.dxf')
(FIXTURES/'external-expected.json').write_text(json.dumps(expected,indent=2))

def audit(file):
    loaded=ezdxf.readfile(file)
    report=loaded.audit()
    assert not report.errors, [(str(e.code),e.message) for e in report.errors[:8]]
    assert not report.fixes, [(str(e.code),e.message) for e in report.fixes[:8]]
    return {'model_entities':len(loaded.modelspace()),'audit_errors':0,'audit_fixes':0}

for file in [FIXTURES/'external.dxf',FIXTURES/'analytic-roundtrip.dxf',ROOT/'examples/courtyard.dxf',ROOT/'examples/fixture.dxf',RESULTS/'browser-export.dxf']:
    if file.exists():record(file.name+' independent read/audit',lambda file=file:audit(file))

imported=RESULTS/'external-import.json'
if imported.exists():
    native=json.loads(imported.read_text())
    layers={l['id']:l['name'] for l in native['data']['layers']}
    def compare_insert(layer):
        actual=[e['points'] for e in native['data']['entities'] if e['type']=='LINE' and layers[e['layer']]==layer]
        assert len(actual)==len(expected[layer]),(len(actual),len(expected[layer]))
        for a,b in zip(actual,expected[layer]):
            for pa,pb in zip(a,b):
                assert (Vec3(pa)-Vec3(pb)).magnitude<1e-6,(pa,pb)
        return {'expanded_lines':len(actual),'coordinate_tolerance':1e-6}
    for layer in expected:record(layer+' matches independent INSERT expansion',lambda layer=layer:compare_insert(layer))
    def check_mtext():
        texts=[e for e in native['data']['entities'] if layers[e['layer']]=='MTEXT-DIRECTION']
        assert abs(texts[0]['rotation']-math.pi/2)<1e-9
        return 'Direction vector preserved'
    record('MTEXT direction vector',check_mtext)
    def check_unicode():
        assert any(e.get('text')=='±BOLT · Żółć Ω 😀' for e in native['data']['entities'])
        return 'Unicode code units and adjacent hexadecimal letters preserved'
    record('Unicode text round trip',check_unicode)
    def report_skips():
        assert not native['report']['skipped'],native['report']['skipped']
        return native['report']['warnings']
    record('External fixture imports without unsupported entities',report_skips)

(RESULTS/'dxf-interop-results.json').write_text(json.dumps({'suite':'independent ezdxf interoperability','ezdxf_version':ezdxf.__version__,'passed':sum(r['status']=='passed' for r in results),'failed':sum(r['status']=='failed' for r in results),'tests':results},indent=2))
sys.exit(any(r['status']=='failed' for r in results))
