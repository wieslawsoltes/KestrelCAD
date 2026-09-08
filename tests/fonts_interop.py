#!/usr/bin/env python3
"""Independent font-program endpoint and DXF STYLE checks; no font asset files."""
from pathlib import Path
import base64,json,subprocess,traceback
import ezdxf
from ezdxf.fonts import shapefile
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'tests/results';OUT.mkdir(exist_ok=True)
results=[]
def test(name,fn):
    try:fn();results.append({'name':name,'status':'passed'});print('PASS',name)
    except Exception as e:traceback.print_exc();results.append({'name':name,'status':'failed','error':str(e)})
def synthetic(unicode):
    value=json.loads(subprocess.check_output(['node','-e',"const {fixture}=require('./tests/font-fixture');for(const f of ['math','geometry','model','exchange','production','fonts'])require('./src/'+f+'.js');const bytes=fixture("+str(unicode).lower()+");const font=Kestrel.Fonts.parseSHX(bytes);console.log(JSON.stringify({bytes:Buffer.from(bytes).toString('base64'),glyphs:Object.fromEntries([65,66,67,68,69,70,71,72,73,74,75,76,77,78].map(c=>[c,Kestrel.Fonts.glyph(font,c)]))}));"],cwd=ROOT,text=True))
    font=shapefile.shx_load(base64.b64decode(value['bytes']))
    for key,glyph in value['glyphs'].items():
        path=font.render_shape(int(key))
        assert abs(path.end.x-glyph['advance'][0])<1e-7,(key,path.end,glyph['advance'])
        assert abs(path.end.y-glyph['advance'][1])<1e-7,(key,path.end,glyph['advance'])
    return font
for unicode in (False,True):test(('Unicode' if unicode else 'Legacy')+' synthetic SHX agrees with independent endpoint interpreter',lambda u=unicode:synthetic(u))
def styles():
    doc=ezdxf.readfile(ROOT/'tests/fixtures/font-styles.dxf');audit=doc.audit();assert not audit.errors and not audit.fixes,(audit.errors,audit.fixes)
    style=doc.styles.get('Engineering');assert style.dxf.font=='synthetic.shx';assert style.dxf.width==1
    text=list(doc.modelspace().query('TEXT'))[0];assert text.dxf.style=='Engineering';assert abs(text.dxf.width-1.8)<1e-9;assert text.dxf.oblique==15;assert text.dxf.text_generation_flag==2
    again=ROOT/'tests/fixtures/font-external.dxf'
    style.dxf.oblique=12;style.dxf.flags=4;style.dxf.bigfont='external-bigfont.shx';doc.saveas(again)
    result=json.loads(subprocess.check_output(['node','-e',"for(const f of ['math','geometry','model','exchange','production','fonts'])require('./src/'+f+'.js');console.log(JSON.stringify(Kestrel.Exchange.parseDXF(require('fs').readFileSync('tests/fixtures/font-external.dxf','utf8')).data.production.textstyles));"],cwd=ROOT,text=True));style=next(s for s in result if s['name']=='Engineering');assert style['vertical'] and style['oblique']==12 and style['bigFont']=='external-bigfont.shx'
test('Independent STYLE/TEXT audit and producer retain font dependencies and typography',styles)
failed=sum(t['status']=='failed' for t in results)
(OUT/'fonts-interop-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'tests':results},indent=2)+'\n')
print('RESULT',len(results)-failed,'passed;',failed,'failed');raise SystemExit(bool(failed))
