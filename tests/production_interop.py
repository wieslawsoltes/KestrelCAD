#!/usr/bin/env python3
"""Independent ezdxf checks of the actual production DXF fixtures."""
from pathlib import Path
import json,math
import ezdxf
ROOT=Path(__file__).resolve().parent.parent
results=[]
def check(name,fn):
    try:fn();results.append({'name':name,'status':'passed'});print('PASS',name)
    except Exception as e:results.append({'name':name,'status':'failed','error':str(e)});print('FAIL',name,e)
def clean(file):
    d=ezdxf.readfile(ROOT/'tests/fixtures'/file);a=d.audit();assert not a.errors and not a.fixes,[(x.code,x.message) for x in [*a.errors,*a.fixes]]
for file in ('production-blocks.dxf','production-attributes.dxf','production-holes.dxf','production-dimensions.dxf'):
    check('independent audit: '+file,lambda f=file:clean(f))
def block():
    d=ezdxf.readfile(ROOT/'tests/fixtures/production-blocks.dxf');e=list(d.modelspace())[0];assert e.dxftype()=='INSERT';assert e.dxf.name=='Plate';line=list(e.virtual_entities())[0];assert line.dxftype()=='LINE';assert line.dxf.start.isclose((10,20,0));assert line.dxf.end.isclose((110,20,0))
check('standard INSERT resolves to expected transformed LINE',block)
def attributes():
    d=ezdxf.readfile(ROOT/'tests/fixtures/production-attributes.dxf');e=list(d.modelspace())[0];assert e.get_attrib_text('PART')=='X-5';assert d.blocks['Plate'].get_attdef('PART').dxf.text=='D'
check('standard ATTDEF and ATTRIB preserve tag/default/instance value',attributes)
def holes():
    d=ezdxf.readfile(ROOT/'tests/fixtures/production-holes.dxf');e=list(d.modelspace())[0];assert e.dxftype()=='HATCH';assert len(e.paths)==2;assert len(e.paths[0].vertices)==4;assert len(e.paths[1].vertices)==4
check('standard HATCH contains two editable polyline boundary paths',holes)
def dimension():
    d=ezdxf.readfile(ROOT/'tests/fixtures/production-dimensions.dxf');e=list(d.modelspace())[0];assert e.dxftype()=='DIMENSION';assert e.dxf.dimtype&7==0;assert math.isclose(e.get_measurement(),30)
check('standard rotated dimension reports projected measurement 30',dimension)
failed=sum(r['status']=='failed' for r in results)
(ROOT/'tests/results/production-interop-results.json').write_text(json.dumps({'suite':'independent production DXF checks','passed':len(results)-failed,'failed':failed,'tests':results},indent=2)+'\n')
raise SystemExit(1 if failed else 0)
