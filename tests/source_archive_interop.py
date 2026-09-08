#!/usr/bin/env python3
"""Independent ASCII/binary DXF producers and audits; no native DWG codec claim."""
from pathlib import Path
import io,json,subprocess,sys,traceback
import ezdxf
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'tests/results';OUT.mkdir(exist_ok=True)
results=[]
def test(name,fn):
    try:fn();results.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
    except Exception as error:traceback.print_exc();results.append({'name':name,'status':'failed','error':str(error)})
node=r'''
const fs=require('fs');for(const f of ['math','geometry','model','exchange','production','kernel','constraints','dynamic-blocks','fonts','source-archive'])require('./src/'+f+'.js');
const K=Kestrel,A=K.SourceArchive,raw=fs.readFileSync(process.argv[1]),d=K.Drawing.from(K.Exchange.parseDXF(raw).data);
if(!A.evaluate(d).unchanged)throw Error('Fresh import incorrectly differs from baseline');fs.writeFileSync(process.argv[2],A.write(d));
const line=d.entities.find(e=>e.type==='LINE');d.transaction('edit independent line',()=>d.transform([line.id],K.Math.M.translation(3,4,5)));
const report=A.evaluate(d);if(!report.canPreserve)throw Error(report.issues.join('; '));fs.writeFileSync(process.argv[3],A.write(d));
fs.writeFileSync(process.argv[4],A.binaryDXF(d));
'''
def roundtrip(version,binary):
    doc=ezdxf.new(version);m=doc.modelspace();line=m.add_line((1,2,3),(11,12,13));m.add_circle((40,50),7)
    if version!='R12':m.add_xline((7,9),(1,1))
    doc.appids.new('KESTREL_ARCHIVE_TEST');line.set_xdata('KESTREL_ARCHIVE_TEST',[(1000,'opaque marker'),(1040,3.141592653589793)])
    if version!='R12':
        x=line.new_extension_dict().add_xrecord('KEEP_RECORD');x.reset([(1,'untouched dictionary value'),(90,123456789)])
        doc.layouts.new('Keep paper space').add_text('Paper text retained',dxfattribs={'height':3})
    label=version+('-binary' if binary else '-ascii');src=OUT/(label+'-source.dxf');same=OUT/(label+'-unchanged.dxf');changed=OUT/(label+'-edited.dxf');converted=OUT/(label+'-converted-binary.dxf')
    if binary:
        with src.open('wb') as stream:doc.write(stream,fmt='bin')
    else:doc.saveas(src)
    subprocess.run(['node','-e',node,str(src),str(same),str(changed),str(converted)],cwd=ROOT,check=True,capture_output=True,text=True)
    assert src.read_bytes()==same.read_bytes(),'original bytes changed'
    edited=ezdxf.readfile(changed);audit=edited.audit();assert not audit.errors and not audit.fixes,(audit.errors,audit.fixes)
    result=edited.entitydb[line.dxf.handle];assert tuple(result.dxf.start)==(4,6,8);assert tuple(result.dxf.end)==(14,16,18)
    assert result.get_xdata('KESTREL_ARCHIVE_TEST')==line.get_xdata('KESTREL_ARCHIVE_TEST')
    if version!='R12':assert len(edited.modelspace().query('XLINE'))==1
    if version!='R12':
        assert result.get_extension_dict()['KEEP_RECORD'].tags==x.tags
        assert list(edited.layouts.get('Keep paper space').query('TEXT'))[0].dxf.text=='Paper text retained'
    converted_doc=ezdxf.readfile(converted);ca=converted_doc.audit();assert not ca.errors and not ca.fixes
    assert len(converted_doc.modelspace().query('LINE'))==1
for version in ['R12','R2000','R2018']:
    for binary in [False,True]:test(f'{version} {"binary" if binary else "ASCII"} retains opaque data and passes independent audit',lambda v=version,b=binary:roundtrip(v,b))
failed=sum(t['status']=='failed' for t in results);(OUT/'source-archive-interop-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'tests':results},indent=2));print('RESULT',len(results)-failed,'passed;',failed,'failed');sys.exit(bool(failed))
