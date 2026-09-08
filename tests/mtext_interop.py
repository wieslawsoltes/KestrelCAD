#!/usr/bin/env python3
"""MTEXT producer/consumer checks using independent ezdxf, ASCII and binary."""
from pathlib import Path
import json,subprocess,traceback
import ezdxf
from ezdxf.lldxf.encoding import decode_dxf_unicode
from ezdxf.tools.text import plain_mtext
def unescape(s):return decode_dxf_unicode(s).encode("utf-16", "surrogatepass").decode("utf-16")
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'tests/results';OUT.mkdir(exist_ok=True)
results=[]
modules=['math','geometry','model','exchange','production','kernel','constraints','dynamic-blocks','fonts','unicode-bidi','mtext','source-document']
def node(body):
    source='const fs=require("fs");for(const m of '+json.dumps(modules)+')require("./src/"+m+".js");const K=Kestrel;'+body
    return json.loads(subprocess.check_output(['node','-e',source],cwd=ROOT,text=True))
def test(name,fn):
    try:fn();results.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
    except Exception as e:traceback.print_exc();results.append({'name':name,'status':'failed','error':str(e)})
def near(a,b):assert abs(a-b)<1e-8*max(1,abs(b)),(a,b)
def read_audit(p):
    d=ezdxf.readfile(p);a=d.audit();assert not a.errors and not a.fixes,(a.errors,a.fixes);return d
raw=r'  {\fArial|b1|i1;TITLE}\P{\C1;\LWARNING\l} \S3/8; in\PZażółć — שלום — مرحبا'
source=OUT/'mtext-external.dxf'
d=ezdxf.new('R2018');m=d.modelspace().add_mtext(raw,dxfattribs={'char_height':5,'width':100,'attachment_point':5,'line_spacing_style':2,'line_spacing_factor':1.2,'true_color':0x123456});m.set_location((15,20,25),rotation=35);m.set_bg_color((171,205,239),scale=1.4);m.set_xdata('ACAD',[(1000,'opaque retained metadata')]);d.saveas(source)
def imported():
    data=node('const r=K.Exchange.parseDXF(fs.readFileSync("tests/results/mtext-external.dxf"));console.log(JSON.stringify(r.data.entities[0]));')
    assert data['type']=='MTEXT' and data['text']==raw;assert data['color']=='#123456';assert data['background']['color']=='#abcdef';near(data['background']['padding'],.4);assert data['attachment']==5;near(data['spacingFactor'],1.2)
test('independent MTEXT producer imports raw controls, Unicode, placement and distinct mask/foreground colors',imported)
def converted(binary=False):
    out=OUT/('mtext-converted-binary.dxf' if binary else 'mtext-converted.dxf')
    node('const data=K.Exchange.parseDXF(fs.readFileSync("tests/results/mtext-external.dxf")).data;const text=K.Exchange.writeDXF(data);fs.writeFileSync('+json.dumps(str(out))+','+('K.SourceDocument.toBinary(text)' if binary else 'text')+');console.log("true");')
    doc=read_audit(out);a=list(doc.modelspace().query('MTEXT'));assert len(a)==1;v=a[0];assert unescape(v.text)==raw;near(v.dxf.width,100);near(v.dxf.char_height,5);assert v.dxf.attachment_point==5;near(v.dxf.line_spacing_factor,1.2);near(v.get_rotation(),35);assert v.dxf.bg_fill_true_color==0xabcdef;assert v.dxf.true_color==0x123456
    assert plain_mtext(unescape(v.text))==m.plain_text()
test('converted ASCII MTEXT round trip audits without repairs and retains semantic properties',converted)
test('converted binary MTEXT retains independent rich text semantics',lambda:converted(True))
def preserve(binary=False):
    inp=source
    if binary:inp=OUT/'mtext-external-binary.dxf';d.saveas(inp,fmt='bin')
    out=OUT/('mtext-patched-binary.dxf' if binary else 'mtext-patched.dxf')
    value=node('const data=K.Exchange.parseDXF(fs.readFileSync('+json.dumps(str(inp))+')).data,doc=K.Drawing.from(data);doc.transaction("edit rich source",()=>{doc.entities[0].text="{\\\\C3;Revised}\\\\PKept metadata";doc.entities[0].width=130;});const result=K.SourceDocument.exportPreserved(doc);fs.writeFileSync('+json.dumps(str(out))+',result.bytes);console.log(JSON.stringify({text:doc.entities[0].text}));')
    v=list(read_audit(out).modelspace().query('MTEXT'))[0];assert v.text==value['text'];assert v.get_xdata('ACAD')[0].value=='opaque retained metadata';near(v.dxf.width,130);assert v.dxf.bg_fill_true_color==0xabcdef and v.dxf.true_color==0x123456
for binary in [False,True]:test(('binary' if binary else 'ASCII')+' source-preserving rich edit retains XDATA and mask with zero independent audit repairs',lambda b=binary:preserve(b))
def long_content():
    out=OUT/'mtext-long.dxf';text=('Ą'+'🚀'+r'\C1;word ')*90
    node('const d=new K.Drawing();d.add("MTEXT",{position:[0,0,0],height:2,width:100,text:'+json.dumps(text)+'});fs.writeFileSync('+json.dumps(str(out))+',K.Exchange.writeDXF(d));console.log("true");')
    v=list(read_audit(out).modelspace().query('MTEXT'))[0];assert unescape(v.text)==text
    tags=out.read_text().splitlines();chunks=[tags[i+1] for i in range(0,len(tags)-1,2) if tags[i]=='3' and tags[i+1].startswith('\\U+')];assert chunks and all(len(t)==250 for t in chunks)
test('250-character groups preserve long Unicode and formatting strings across chunk boundaries',long_content)
def tilted():
    out=OUT/'mtext-tilted.dxf'
    node('const d=new K.Drawing();let e=d.add("MTEXT",{position:[1,2,3],height:2,width:30,text:"plane",normal:[0,1,0],direction:[1,0,0]});e=K.Geo.transform(e,K.Math.M.scale(3));d.replace(e.id,e);fs.writeFileSync('+json.dumps(str(out))+',K.Exchange.writeDXF(d));console.log("true");')
    v=list(read_audit(out).modelspace().query('MTEXT'))[0];assert v.dxf.insert.isclose((3,6,9));near(v.dxf.char_height,6);near(v.dxf.width,90);assert v.dxf.extrusion.isclose((0,1,0));assert v.dxf.text_direction.isclose((1,0,0))
test('tilted scaled MTEXT exchanges world-space placement and orthogonal axes',tilted)
failed=sum(r['status']=='failed' for r in results);(OUT/'mtext-interop-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'tests':results},indent=2)+'\n');print('RESULT',len(results)-failed,'passed;',failed,'failed');raise SystemExit(bool(failed))
