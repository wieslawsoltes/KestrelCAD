#!/usr/bin/env python3
"""Independent ezdxf-produced files and audits of source-preserving modifications."""
from pathlib import Path
import base64, io, json, math, subprocess, sys, tempfile, traceback
import ezdxf
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'tests/results';OUT.mkdir(exist_ok=True)
results=[]
NODE=r"""
for(const f of ['math','geometry','model','exchange','production','kernel','constraints','dynamic-blocks','fonts','source-document'])require('./src/'+f+'.js');
const K=globalThis.Kestrel,S=K.SourceDocument,input=JSON.parse(require('fs').readFileSync(0,'utf8'));
const raw=Buffer.from(input.bytes,'base64'),doc=K.Drawing.from(K.Exchange.parseDXF(raw,'Independent').data);
if(input.edit)doc.transaction('Translate',()=>doc.transform(doc.entities.map(e=>e.id),K.Math.M.translation(7,11,13)));
if(input.add)doc.transaction('Add',()=>doc.add('CIRCLE',{center:[50,60,0],radius:8,layer:doc.layers.find(l=>l.name==='0').id}));
const output=S.exportPreserved(doc);
console.log(JSON.stringify({bytes:Buffer.from(output.bytes).toString('base64'),report:output.report,entities:doc.entities,archive:S.info(doc)}));
"""
def run(raw,**options):
    p=subprocess.run(['node','-e',NODE],input=json.dumps({'bytes':base64.b64encode(raw).decode(),**options}),text=True,capture_output=True,cwd=ROOT,timeout=30)
    if p.returncode:raise RuntimeError(p.stderr)
    obj=json.loads(p.stdout);return base64.b64decode(obj['bytes']),obj

def test(name,fn):
    try:fn();results.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
    except Exception as e:traceback.print_exc();results.append({'name':name,'status':'failed','error':str(e)})

def sample(version='R2010'):
    d=ezdxf.new(version);m=d.modelspace();m.add_line((1,2,3),(4,5,6));m.add_point((8,9,10));m.add_circle((20,30,0),5);m.add_arc((40,50,0),10,20,140)
    if version!='R12':
        m.add_lwpolyline([(0,0,.2),(10,0,0),(10,10,0)],format='xyb',close=True)
        m.add_ellipse((10,20,30),major_axis=(12,0,0),ratio=.3)
        m.add_open_spline([(0,0,0),(5,10,0),(10,5,0),(15,0,0)],degree=3)
    m.add_text('Independent text ±',dxfattribs={'insert':(12,34,0),'height':3,'width':1.2,'oblique':12})
    if version!='R12':
        xr=d.rootdict.add_xrecord('KESTREL_UNINTERPRETED')
        xr.reset([(1,'Application payload not interpreted by editor'),(160,9007199254740993),(310,b'\0\xde\xad\xbe\xef\0')])
        d.appids.new('KESTREL_TEST');m.query('LINE')[0].set_xdata('KESTREL_TEST',[(1000,'Keep this literal extension'),(1071,123456789)])
    return d

def encoded(d,binary=False):
    stream=io.BytesIO() if binary else io.StringIO();d.write(stream,fmt='bin' if binary else 'asc');return stream.getvalue() if binary else stream.getvalue().encode(d.output_encoding)

def read(raw):
    with tempfile.TemporaryDirectory() as tmp:
        file=Path(tmp)/'result.dxf';file.write_bytes(raw);return ezdxf.readfile(file)

def unchanged(binary):
    raw=encoded(sample(),binary);out,info=run(raw);assert raw==out;assert info['archive']['binary']==binary
for binary in (False,True):test(('binary' if binary else 'ASCII')+' independent original round trip is byte-identical',lambda b=binary:unchanged(b))

def changed(binary):
    d=sample();raw=encoded(d,binary);out,info=run(raw,edit=True);new=read(out);audit=new.audit();assert not audit.errors and not audit.fixes,(audit.errors,audit.fixes)
    before=list(d.modelspace());after=list(new.modelspace());assert len(before)==len(after)
    for a,b in zip(before,after):
        assert a.dxftype()==b.dxftype() and a.dxf.handle==b.dxf.handle
        typ=a.dxftype()
        if typ=='LINE':assert b.dxf.start.isclose(a.dxf.start+(7,11,13)) and b.dxf.end.isclose(a.dxf.end+(7,11,13))
        elif typ=='POINT':assert b.dxf.location.isclose(a.dxf.location+(7,11,13))
        elif typ in ('CIRCLE','ARC','ELLIPSE'):assert b.dxf.center.isclose(a.dxf.center+(7,11,13))
        elif typ=='LWPOLYLINE':
            assert list(b.get_points('xyb'))==[(p[0]+7,p[1]+11,p[2]) for p in a.get_points('xyb')];assert b.dxf.elevation==13
        elif typ=='SPLINE':assert all(abs(float(b.control_points[i][j])-float(a.control_points[i][j])-(7,11,13)[j])<1e-7 for i in range(len(a.control_points)) for j in range(3))
        elif typ=='TEXT':assert b.dxf.insert.isclose(a.dxf.insert+(7,11,13));assert b.dxf.text==a.dxf.text;assert abs(b.dxf.width-a.dxf.width)<1e-7;assert abs(b.dxf.oblique-a.dxf.oblique)<1e-7
    assert list(new.rootdict['KESTREL_UNINTERPRETED'].tags)==list(d.rootdict['KESTREL_UNINTERPRETED'].tags)
    assert list(new.modelspace().query('LINE')[0].get_xdata('KESTREL_TEST'))==list(d.modelspace().query('LINE')[0].get_xdata('KESTREL_TEST'))
    (OUT/('independent-edited-binary.dxf' if binary else 'independent-edited-ascii.dxf')).write_bytes(out)
for binary in (False,True):test(('binary' if binary else 'ASCII')+' independent curve edits audit without repairs and retain XRECORD/XDATA',lambda b=binary:changed(b))

def added():
    raw=encoded(sample());out,_=run(raw,add=True);d=read(out);a=d.audit();assert not a.errors and not a.fixes,(a.errors,a.fixes);assert len(d.modelspace().query('CIRCLE'))==2;assert d.modelspace().query('CIRCLE')[-1].dxf.radius==8
    ids=[e.dxf.handle for e in d.entitydb.values()];assert len(ids)==len(set(ids))
test('independent source accepts appended entities with valid ownership and unique handles',added)

def legacy():
    raw=encoded(sample('R12'),True);out,_=run(raw,edit=True);d=read(out);a=d.audit();assert not a.errors and not a.fixes,(a.errors,a.fixes);assert d.modelspace().query('LINE')[0].dxf.start.isclose((8,13,16))
test('independent R12 binary edits retain one-byte group encoding',legacy)
failed=sum(t['status']=='failed' for t in results)
(OUT/'source-interop-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'tests':results},indent=2))
print('Source interchange:',len(results)-failed,'passed;',failed,'failed');sys.exit(bool(failed))
