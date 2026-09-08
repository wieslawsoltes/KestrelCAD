#!/usr/bin/env python3
"""Independent DXF checks for replaced rich text and per-instance attributes."""
from pathlib import Path
import io,json,subprocess,sys,traceback
import ezdxf
from ezdxf.lldxf.encoding import decode_dxf_unicode
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'tests/results';OUT.mkdir(exist_ok=True);tests=[]
modules=['math','geometry','model','exchange','production','kernel','constraints','spatial-constraints','dynamic-blocks','fonts','unicode-bidi','mtext','source-document','productivity','fields','text-search']
source=r'''
const fs=require('fs');for(const m of MODULES)require('./src/'+m+'.js');
const K=Kestrel,d=new K.Drawing('Search exchange');d.transaction('Fixture',()=>{
 d.add('TEXT',{position:[0,0,0],height:3,text:'Valve valve'});
 d.add('MTEXT',{position:[0,20,0],height:3,width:100,text:'Va{\\C1;lve}\\PTorque = 8'});
 d.production.blocks.push({id:'b',name:'Title',entities:[],attributes:[{tag:'TITLE',value:'Valve',position:[0,0,0],height:3}]});
 d.add('INSERT',{block:'b',matrix:Array.from(K.Math.M.identity()),attributes:{}});
});K.TextSearch.replace(d,K.TextSearch.search(d,'Valve'),'Zażółć Ω');
const text=K.Exchange.writeDXF(d);console.log(JSON.stringify({text,binary:Array.from(new Uint8Array(K.SourceDocument.toBinary(text)))}));
'''.replace('MODULES',json.dumps(modules))
data=json.loads(subprocess.check_output(['node','-e',source],cwd=ROOT,text=True))
path=OUT/'text-search-binary.dxf';path.write_bytes(bytes(data['binary']))
def test(name,fn):
    try:fn();tests.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
    except Exception as e:traceback.print_exc();tests.append({'name':name,'status':'failed','error':str(e)})
for name,doc in [('ASCII',ezdxf.read(io.StringIO(data['text']))),('binary',ezdxf.readfile(path))]:
    def audit(doc=doc):
        a=doc.audit();assert not a.errors and not a.fixes
    test(name+' replaced drawing audits without repairs',audit)
    def plain(doc=doc):assert decode_dxf_unicode(next(iter(doc.modelspace().query('TEXT'))).dxf.text)=='Zażółć Ω Zażółć Ω'
    test(name+' replacement Unicode plain text survives a separate consumer',plain)
    # ezdxf's fast extractor skips Unicode controls followed by a semicolon scope;
    # use its full MTEXT parser, then the standard DXF Unicode decoder.
    def rich(doc=doc):
        e=next(iter(doc.modelspace().query('MTEXT')));assert decode_dxf_unicode(e.plain_text(fast=False))=='Zażółć Ω\nTorque = 8';assert '\\C1;' in e.text
    test(name+' rich scopes and paragraphs survive replacement and interchange',rich)
    def attributes(doc=doc):
        e=next(iter(doc.modelspace().query('INSERT')));assert decode_dxf_unicode(e.attribs[0].dxf.text)=='Zażółć Ω';assert doc.blocks['Title'].query('ATTDEF')[0].dxf.text=='Valve'
    test(name+' static attribute replacement does not rewrite its shared default',attributes)
failed=sum(t['status']=='failed' for t in tests);(OUT/'text-search-interop-results.json').write_text(json.dumps({'passed':len(tests)-failed,'failed':failed,'tests':tests},indent=2));sys.exit(bool(failed))
