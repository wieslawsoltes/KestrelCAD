#!/usr/bin/env python3
"""Independent ezdxf audits of native-field evaluated ASCII/binary output."""
from pathlib import Path
import json, math, subprocess, traceback
import ezdxf
from ezdxf.lldxf.encoding import decode_dxf_unicode
from ezdxf.tools.text import plain_mtext
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'tests/results';OUT.mkdir(exist_ok=True)
results=[]
MODULES=['math','geometry','model','exchange','production','kernel','constraints','spatial-constraints','dynamic-blocks','fonts','unicode-bidi','mtext','source-document','productivity','fields']
def text(value):return decode_dxf_unicode(value).encode('utf-16','surrogatepass').decode('utf-16')
def node(body):
    code='const fs=require("fs");for(const m of '+json.dumps(MODULES)+')require("./src/"+m+".js");require("./tests/fields.fixture.js");const K=Kestrel,f=makeFieldsFixture(),d=f.doc;'+body
    run=subprocess.run(['node','-e',code],cwd=ROOT,capture_output=True,text=True,timeout=30)
    assert run.returncode==0,run.stderr
    return json.loads(run.stdout)
def read(path):
    d=ezdxf.readfile(path);a=d.audit();assert not a.errors and not a.fixes,[(e.code,e.message) for e in [*a.errors,*a.fixes]]
    return d
def output(name,body='',binary=False):
    path=OUT/name
    node(body+'const raw=K.Exchange.writeDXF(d);fs.writeFileSync('+json.dumps(str(path))+','+('K.SourceDocument.toBinary(raw)' if binary else 'raw')+');console.log("true");')
    return read(path)
def test(name,fn):
    try:fn();results.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
    except Exception as e:traceback.print_exc();results.append({'name':name,'status':'failed','error':str(e)})
def basic(binary=False):
    d=output('fields-independent-'+('binary' if binary else 'ascii')+'.dxf',binary=binary)
    assert any(e.dxf.text=='Length 5.000 cm' for e in d.modelspace().query('TEXT'))
    m=next(iter(d.modelspace().query('MTEXT')));assert 'Zażółć — שלום — مرحبا 🚀' in text(m.text)
    assert 'Cost '+format(math.pi*12.5,'.5f') in text(m.text)
    assert m.dxf.char_height==5 and m.dxf.width==200
    assert not any(e.dxftype()=='FIELD' for e in d.objects)
test('ASCII evaluated fields retain dimensions, Unicode and MTEXT controls with zero audit repairs',basic)
test('binary evaluated fields preserve the same independently decoded content',lambda:basic(True))
def refresh():
    d=output('fields-refreshed.dxf','d.transaction("Resize",()=>{f.line.points[1]=[0,250,0]});')
    assert any(e.dxf.text=='Length 25.000 cm' for e in d.modelspace().query('TEXT'))
    ref=next(iter(d.modelspace().query('INSERT')));assert ref.get_attrib_text('SIZE')=='L=250.0 mm'
test('source edits update both TEXT and actual INSERT attribute payloads',refresh)
def table():
    d=output('fields-table.dxf');labels=[e.dxf.text for e in d.modelspace().query('TEXT')]
    assert '50' in labels and '314.15927' in labels and '####' in labels
    assert 'Length mm' in labels and 'Area mm2' in labels
    assert all(not e.has_extension_dict for e in d.modelspace().query('TEXT'))
test('linked tables flatten to evaluated static graphics including explicit unavailable cells',table)
def stale():
    p=OUT/'fields-stale.dxf'
    result=node('const data=d.serialize();data.entities.find(e=>e.id===f.line.id).points[1]=[0,80,0];const before=JSON.stringify(data);fs.writeFileSync('+json.dumps(str(p))+',K.Exchange.writeDXF(data));console.log(JSON.stringify(before===JSON.stringify(data)));')
    assert result;doc=read(p);assert any(e.dxf.text=='Length 8.000 cm' for e in doc.modelspace().query('TEXT'))
test('serialized stale values are refreshed at static export without mutating caller data',stale)
def missing():
    d=output('fields-missing.dxf','d.transaction("Delete",()=>d.remove([f.line.id]));')
    assert any(e.dxf.text=='####' for e in d.modelspace().query('TEXT'))
    assert not any(e.dxf.text.startswith('Length ') and '5.000' in e.dxf.text for e in d.modelspace().query('TEXT'))
    assert next(iter(d.modelspace().query('INSERT'))).get_attrib_text('SIZE')=='####'
test('deleted source never exports a stale previous measurement',missing)
def noeval():
    data=node('const r=K.Exchange.parseDXF(K.Exchange.writeDXF(d));console.log(JSON.stringify(r.data));')
    assert all(not e.get('fieldBindings') for e in data['entities'])
    assert any(e.get('text')=='Length 5.000 cm' for e in data['entities'])
test('standard DXF reimport is readable static text, not an invented native evaluator',noeval)
def browser():
    p=OUT/'fields-browser.dxf'
    assert p.is_file(), 'Run tests/fields.browser.py first to produce the actual worker download.'
    doc=read(p);assert any('Revised pump' in text(e.text) for e in doc.modelspace().query('MTEXT'))
    assert any(e.dxf.text=='Double 40.0' for e in doc.modelspace().query('TEXT'))
test('actual browser-worker output passes independent zero-repair audit',browser)
failed=sum(r['status']=='failed' for r in results)
(OUT/'fields-interop-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'tests':results},indent=2)+'\n')
print('RESULT',len(results)-failed,'passed;',failed,'failed');raise SystemExit(bool(failed))
