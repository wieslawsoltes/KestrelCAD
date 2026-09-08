#!/usr/bin/env python3
"""Independent DXF reader verifies precision, whitespace and Unicode block names."""
from pathlib import Path
import json, subprocess, sys, traceback
import ezdxf
from ezdxf.lldxf.encoding import decode_dxf_unicode
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'tests/results';OUT.mkdir(exist_ok=True)
script=r'''
const fs=require('fs');for(const n of ['math','geometry','model','exchange','production','kernel','constraints','dynamic-blocks','fonts','source-document'])require('./src/'+n+'.js');
const K=globalThis.Kestrel,X=K.Exchange,S=K.SourceDocument,d=new K.Drawing('Precision');d.currentLayer='0';
d.add('POINT',{position:[1.2345678901234567,-1.234567890123456e-11,987654321.9876543]});
d.add('TEXT',{position:[1,2,0],height:3,text:'  Łódź 工程  '});
for(const name of ['工程甲','工程乙']){const e=d.add('LINE',{points:[[0,0,0],[10,0,0]]});d.reindex();const b=K.Production.defineBlock(d,name,[e.id]);b.attributes=[{tag:'ID',value:'  原值  ',position:[0,0,0],height:2}];d.entities.find(e=>e.block===b.id).attributes={ID:'  '+name+'  '};}
for(const binary of [false,true]){const fmt=binary?'binary':'ascii',raw=X.writeDXF(d),data=binary?S.toBinary(raw):raw;fs.writeFileSync('tests/results/fidelity-'+fmt+'.dxf',data);const i=K.Drawing.from(X.parseDXF(data).data);i.transaction('Edit point',()=>i.entities.find(e=>e.type==='POINT').position[0]=Math.PI);fs.writeFileSync('tests/results/fidelity-edited-'+fmt+'.dxf',S.exportPreserved(i).bytes);}
'''
subprocess.run(['node','-e',script],cwd=ROOT,check=True)
checks=[]
for fmt in ['ascii','binary']:
 for edited in [False,True]:
  label=('edited-' if edited else '')+fmt
  try:
   doc=ezdxf.readfile(OUT/f'fidelity-{label}.dxf');audit=doc.audit();assert not audit.errors and not audit.fixes,(audit.errors,audit.fixes)
   model=doc.modelspace();point=next(iter(model.query('POINT'))).dxf.location
   assert point.x==(3.141592653589793 if edited else 1.2345678901234567)
   assert point.y==-1.234567890123456e-11 and point.z==987654321.9876543
   assert decode_dxf_unicode(next(iter(model.query('TEXT'))).dxf.text)=='  Łódź 工程  '
   assert [decode_dxf_unicode(e.dxf.name) for e in model.query('INSERT')]==['工程甲','工程乙']
   assert [decode_dxf_unicode(e.attribs[0].dxf.text) for e in model.query('INSERT')]==['  工程甲  ','  工程乙  ']
   checks.append({'name':label+' precision and text, independent audit','status':'passed'});print('PASS',label,flush=True)
  except Exception as e:
   traceback.print_exc();checks.append({'name':label,'status':'failed','error':str(e)})
failed=sum(c['status']=='failed' for c in checks)
(OUT/'exchange-fidelity-interop-results.json').write_text(json.dumps({'passed':len(checks)-failed,'failed':failed,'tests':checks},indent=2))
sys.exit(bool(failed))
