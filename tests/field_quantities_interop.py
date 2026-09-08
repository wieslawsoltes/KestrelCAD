#!/usr/bin/env python3
"""Independent audit of evaluated native quantity annotations in ASCII/binary DXF."""
from pathlib import Path
import json, subprocess, sys, traceback
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'tests/results';OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'tools'));import kernel
import ezdxf
body=kernel.execute({'op':'box','params':{'width':20,'depth':30,'height':10}})
modules=['math','geometry','model','exchange','production','kernel','constraints','spatial-constraints','dynamic-blocks','fonts','unicode-bidi','mtext','source-document','productivity','fields']
code=r'''
const fs=require('fs');for(const m of MODULES)require('./src/'+m+'.js');const K=Kestrel,F=K.Fields,d=new K.Drawing();
d.transaction('Actual native quantity fixture',()=>{d.units='mm';d.add({...K.Kernel.body(JSON.parse(fs.readFileSync(0,'utf8'))),id:'body'});d.add('TEXT',{id:'volume',position:[0,0,0],height:4,text:''});d.add('MTEXT',{id:'area',position:[0,20,0],height:4,width:100,text:''});});
F.setBinding(d,'volume',{version:1,target:'text',template:'Volume {{Value}} cm3',precision:4,sources:[{name:'Value',kind:'object',entity:'body',property:'volume',units:'cm'}]});
F.setBinding(d,'area',{version:1,target:'text',template:'{\\LArea {{Value}} cm2\\l}',precision:3,sources:[{name:'Value',kind:'object',entity:'body',property:'surfaceArea',units:'cm'}]});
F.linkedTable(d,['body'],[0,40,0],{columns:[{label:'Volume cm3',property:'volume',units:'cm'},{label:'Area cm2',property:'surfaceArea',units:'cm'}]});
d.transaction('Uniform native scale',()=>d.transform(['body'],K.Math.M.scale(2)));
const serialized=d.serialize();serialized.entities.find(e=>e.id==='volume').text='stale';const ascii=K.Exchange.writeDXF(serialized);
fs.writeFileSync('tests/results/native-quantities-ascii.dxf',ascii);fs.writeFileSync('tests/results/native-quantities-binary.dxf',K.SourceDocument.toBinary(ascii));
'''.replace('MODULES',json.dumps(modules))
subprocess.run(['node','-e',code],input=json.dumps(body),text=True,cwd=ROOT,check=True)
tests=[]
def test(name,fn):
    try:fn();tests.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
    except Exception as e:traceback.print_exc();tests.append({'name':name,'status':'failed','error':str(e)})
for mode in ['ascii','binary']:
    doc=ezdxf.readfile(OUT/f'native-quantities-{mode}.dxf')
    def audit():
        result=doc.audit();assert not result.errors and not result.fixes,[(v.code,v.message) for v in [*result.errors,*result.fixes]]
    test(mode+' native quantity output passes independent zero-repair audit',audit)
    def volume():assert any(e.dxf.text=='Volume 48.0000 cm3' for e in doc.modelspace().query('TEXT'))
    test(mode+' cached volume refreshes before static DXF serialization',volume)
    def area():
        m=next(iter(doc.modelspace().query('MTEXT')));assert m.plain_text(fast=False)=='Area 88.000 cm2';assert '\\L' in m.text;assert m.dxf.char_height==4
    test(mode+' transformed surface area retains MTEXT presentation',area)
    def table():
        values=[e.dxf.text for e in doc.modelspace().query('TEXT')];assert '48' in values and '88' in values;assert not any(e.dxftype()=='FIELD' for e in doc.objects)
    test(mode+' quantity schedule exports static evaluated cells, not invented FIELD records',table)
failed=sum(t['status']=='failed' for t in tests);(OUT/'field-quantities-interop-results.json').write_text(json.dumps({'passed':len(tests)-failed,'failed':failed,'tests':tests},indent=2)+'\n');sys.exit(bool(failed))
