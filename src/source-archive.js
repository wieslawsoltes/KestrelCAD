/* Kestrel CAD — byte-retaining CAD source archives and conservative record editing.
 * Native geometry is a view of the source, not a replacement for unknown records.
 * No claim is made that opaque application dependencies are evaluated by this editor.
 */
(function(root) {
 'use strict';
 const K=root.Kestrel,E=K.Exchange,encoder=new TextEncoder(),stores=new WeakMap();
 const MAX=64*1024*1024,MAX_TAGS=3000000,SENTINEL='AutoCAD Binary DXF\r\n\x1a\0';
 const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
 const bytes=value=>typeof value==='string'?encoder.encode(value):value instanceof ArrayBuffer?new Uint8Array(value):ArrayBuffer.isView(value)?new Uint8Array(value.buffer,value.byteOffset,value.byteLength):(()=>{throw Error('Expected text or bytes.');})();
 function encode64(value){let s='';for(let i=0;i<value.length;i+=32768)s+=String.fromCharCode(...value.subarray(i,i+32768));return btoa(s);}
 function decode64(value){if(typeof value!=='string'||value.length>Math.ceil(MAX/3)*4||value.length%4!==0||/[^A-Za-z0-9+/=]/.test(value)||value.indexOf('=')>=0&&value.indexOf('=')<value.length-2||/=/.test(value.slice(0,-2))||value.endsWith('=')&&!/^[A-Za-z0-9+/](?:[A-Za-z0-9+/]=|==)$/.test(value.slice(-3)))throw Error('Invalid archived source bytes.');const s=atob(value);if(s.length>MAX)throw Error('Archived source exceeds 64 MiB.');return Uint8Array.from(s,c=>c.charCodeAt(0));}
 const hex=s=>/^[0-9A-F]{1,16}$/i.test(s);
 const escapeText=s=>String(s).replace(/[\r\n\0]/g,' ').replace(/[^\x20-\x7e]/g,c=>'\\U+'+c.charCodeAt(0).toString(16).padStart(4,'0').toUpperCase());
 function kind(code){
  if(code>=310&&code<=319||code===1004)return 'chunk';
  if(code>=290&&code<=299)return 'bool';
  if(code>=160&&code<=169)return 'int64';
  if(code>=10&&code<=59||code>=110&&code<=149||code>=210&&code<=239||code>=460&&code<=469||code>=1010&&code<=1059)return 'double';
  if(code>=60&&code<=79||code>=170&&code<=179||code>=270&&code<=289||code>=370&&code<=389||code>=400&&code<=409||code>=1060&&code<=1070)return 'int16';
  if(code>=90&&code<=99||code>=420&&code<=429||code>=440&&code<=459||code===1071)return 'int32';
  if(code>=0&&code<=9||[100,101,102,105,999].includes(code)||code>=300&&code<=369||code>=390&&code<=399||code>=410&&code<=419||code>=430&&code<=439||code>=470&&code<=481||code>=1000&&code<=1009)return 'string';
  throw Error('Unknown DXF group-code value type: '+code);
 }
 function sections(tags){let section='',table='',record=null;const records=[];let endEntities=-1,version='AC1009';
  for(let i=0;i<tags.length;i++){const t=tags[i];
   if(t.code===9&&t.value.trim()==='$ACADVER')version=tags[i+1]?.value.trim()||version;
   if(t.code===0){if(record)record.end=t.start;const type=t.value.trim().toUpperCase();if(type==='SECTION'){section=tags[i+1]?.code===2?tags[i+1].value.trim().toUpperCase():'';table='';}if(type==='TABLE')table=tags[i+1]?.code===2?tags[i+1].value.trim().toUpperCase():'';
    record={type,section,table,tags:[],start:t.start,end:t.end};records.push(record);
    if(type==='ENDSEC'){if(section==='ENTITIES')endEntities=t.start;section='';table='';}
    if(type==='ENDTAB')table='';
   }if(record){record.tags.push(t);record.end=t.end;}
  }
  if(!records.some(r=>r.type==='EOF')||endEntities<0)throw Error('Source preservation requires complete DXF ENTITIES and EOF records.');
  for(const r of records){let app=0,xdata=false;r.ordinary=[];for(const t of r.tags){if(t.code===1001)xdata=true;if(t.code===102){if(t.value.trim().startsWith('{'))app++;else if(t.value.trim()==='}')app=Math.max(0,app-1);continue;}if(!app&&!xdata)r.ordinary.push(t);}r.handle=r.ordinary.find(t=>t.code===5||t.code===105)?.value.trim().toUpperCase();}
  return {records,tags,version,endEntities};
 }
 function scanASCII(input){const data=bytes(input);if(data.length>MAX)throw Error('DXF exceeds 64 MiB.');
  const encoding=E.decodeDXF(data).encoding,decoder=new TextDecoder(encoding),tags=[];let p=data[0]===239&&data[1]===187&&data[2]===191?3:0;
  function line(){const start=p;while(p<data.length&&data[p]!==10&&data[p]!==13)p++;const valueEnd=p;if(data[p]===13)p++;if(data[p]===10)p++;return {start,valueEnd,end:p};}
  while(p<data.length){const c=line(),raw=new TextDecoder().decode(data.subarray(c.start,c.valueEnd)).trim();if(!raw&&p>=data.length)break;if(!/^\d{1,4}$/.test(raw))throw Error('Invalid DXF group code at byte '+c.start+'.');const code=Number(raw);if(code>1071)throw Error('DXF group code exceeds 1071.');if(p>=data.length)throw Error('Missing DXF group value.');const v=line();tags.push({code,value:decoder.decode(data.subarray(v.start,v.valueEnd)),start:c.start,valueStart:v.start,valueEnd:v.valueEnd,end:v.end});if(tags.length>MAX_TAGS)throw Error('DXF tag limit exceeded.');}
  return {...sections(tags),data,encoding,binary:false,wide:true,newline:data.includes(13)?'\r\n':'\n'};
 }
 function scanBinary(input){const data=bytes(input);if(data.length>MAX)throw Error('DXF exceeds 64 MiB.');if(new TextDecoder().decode(data.subarray(0,22))!==SENTINEL)throw Error('Invalid binary DXF sentinel.');
  const view=new DataView(data.buffer,data.byteOffset,data.byteLength),wide=data[23]===0,tags=[];let p=22,encoding='windows-1252';
  const need=n=>{if(p+n>data.length)throw Error('Truncated binary DXF at byte '+p+'.');};
  while(p<data.length){const start=p;need(wide?2:1);let code=wide?view.getUint16(p,true):data[p];p+=wide?2:1;if(!wide&&code===255){need(2);code=view.getUint16(p,true);p+=2;}const valueStart=p,type=kind(code);let value;
   if(type==='string'){while(p<data.length&&data[p])p++;need(1);value=new TextDecoder(encoding).decode(data.subarray(valueStart,p));p++;}
   else if(type==='chunk'){need(1);const n=data[p++];need(n);value=Array.from(data.subarray(p,p+n),x=>x.toString(16).padStart(2,'0')).join('').toUpperCase();p+=n;}
   else {const n=type==='bool'?1:type==='int16'?2:type==='int32'?4:8;need(n);value=type==='double'?view.getFloat64(p,true):type==='int16'?view.getInt16(p,true):type==='int32'?view.getInt32(p,true):type==='int64'?view.getBigInt64(p,true).toString():data[p];if(type==='double'&&!Number.isFinite(value)||type==='bool'&&value!==0&&value!==1)throw Error('Invalid binary DXF value.');value=String(value);p+=n;}
   tags.push({code,value,start,valueStart,valueEnd:p,end:p});if(tags.length>MAX_TAGS)throw Error('DXF tag limit exceeded.');
   if(tags.at(-2)?.code===9&&tags.at(-2).value==='$ACADVER'&&Number(value.replace('AC',''))>=1021)encoding='utf-8';
   if(tags.at(-2)?.code===9&&tags.at(-2).value==='$DWGCODEPAGE'&&encoding!=='utf-8'){const id=value.match(/ANSI_(\d+)/)?.[1];if(id)encoding=({'932':'shift_jis','936':'gbk','949':'euc-kr','950':'big5','874':'windows-874'})[id]||'windows-'+id;}
  }
  // Decode strings again with the final codepage, including records before HEADER.
  for(const t of tags)if(kind(t.code)==='string')t.value=new TextDecoder(encoding).decode(data.subarray(t.valueStart,t.end-1));
  return {...sections(tags),data,encoding,binary:true,wide};
 }
 const scan=value=>new TextDecoder().decode(bytes(value).subarray(0,18))==='AutoCAD Binary DXF'?scanBinary(value):scanASCII(value);
 function pairBytes(code,value,source){if(!source.binary)return encoder.encode(String(code)+source.newline+String(value)+source.newline);
  const type=kind(code);let val;if(type==='string')val=Uint8Array.from([...encoder.encode(escapeText(value)),0]);
  else if(type==='chunk'){const s=String(value).trim();if(!/^(?:[0-9a-f]{2})*$/i.test(s)||s.length>510)throw Error('Invalid binary chunk.');val=Uint8Array.from([s.length/2,...s.match(/../g)?.map(x=>parseInt(x,16))||[]]);}
  else {const n=type==='bool'?1:type==='int16'?2:type==='int32'?4:8;val=new Uint8Array(n);const v=new DataView(val.buffer);if(type==='double'){const x=Number(value);if(!Number.isFinite(x))throw Error('Non-finite binary DXF value.');v.setFloat64(0,x,true);}else if(type==='int64'){const x=BigInt(value);if(x<-(1n<<63n)||x>=(1n<<63n))throw Error('Binary integer out of range.');v.setBigInt64(0,x,true);}else{const x=Number(value),lo=type==='bool'?0:type==='int16'?-32768:-2147483648,hi=type==='bool'?1:type==='int16'?32767:2147483647;if(!Number.isInteger(x)||x<lo||x>hi)throw Error('Binary integer out of range.');if(type==='bool')v.setUint8(0,x);else if(type==='int16')v.setInt16(0,x,true);else v.setInt32(0,x,true);}}
  const header=source.wide?Uint8Array.of(code&255,code>>8):code<255?Uint8Array.of(code):Uint8Array.of(255,code&255,code>>8);const out=new Uint8Array(header.length+val.length);out.set(header);out.set(val,header.length);return out;
 }
 function concat(chunks){const size=chunks.reduce((s,b)=>s+b.length,0);if(size>MAX*2)throw Error('DXF output limit exceeded.');const out=new Uint8Array(size);let p=0;for(const c of chunks){out.set(c,p);p+=c.length;}return out;}
 function binaryDXF(data){const source=scanASCII(E.writeDXF(data));return concat([encoder.encode(SENTINEL),...source.tags.map(t=>pairBytes(t.code,t.value,{binary:true,wide:true}))]);}
 const baseline=data=>K.clone({entities:data.entities,layers:data.layers,production:data.production,units:data.units});
 function create(data,input,name='source.dxf'){const raw=bytes(input);if(raw.length>MAX)throw Error('Source archive exceeds 64 MiB.');const source=scan(raw);return {schema:1,name:String(name).slice(0,512),format:source.binary?'dxf-binary':'dxf-ascii',byteLength:raw.length,bytes:encode64(raw),baseline:baseline(data)};}
 function validate(archive){if(!archive||archive.schema!==1||!['dxf-ascii','dxf-binary','dwg'].includes(archive.format)||typeof archive.name!=='string'||archive.name.length>512)throw Error('Invalid CAD source archive.');const data=decode64(archive.bytes);if(data.length!==archive.byteLength)throw Error('Archived byte count mismatch.');if(!archive.baseline||!Array.isArray(archive.baseline.entities)||archive.baseline.entities.length>200000||!Array.isArray(archive.baseline.layers))throw Error('Invalid CAD archive baseline.');if(archive.baseline.sourceArchive||archive.baseline.sourceArchiveRef)throw Error('Recursive source archive.');K.validateProject({format:'kestrel-cad',version:2,...K.clone(archive.baseline)});if(archive.format==='dwg'){if(!/^AC\d{4}/.test(new TextDecoder().decode(data.subarray(0,6))))throw Error('Invalid archived DWG signature.');}else if(scan(data).binary!==(archive.format==='dxf-binary'))throw Error('Archived DXF format mismatch.');if(archive.original){if(archive.original.format!=='dwg'||typeof archive.original.name!=='string'||archive.original.name.length>512)throw Error('Invalid original DWG archive.');decode64(archive.original.bytes);}return archive;}
 function freeze(value){if(value&&typeof value==='object'&&!Object.isFrozen(value)){Object.freeze(value);for(const v of Object.values(value))freeze(v);}return value;}
 function state(doc){let s=stores.get(doc);if(!s){s={current:null,history:new Map()};stores.set(doc,s);}return s;}
 function serialize(doc,history=false){const s=state(doc);if(!s.current)return {};if(history)return {sourceArchiveRef:s.current.id};return {sourceArchive:s.current.value};}
 function restore(doc,data,history=false){const s=state(doc);if(data.sourceArchiveRef){if(!history||!s.history.has(data.sourceArchiveRef))throw Error('Unresolvable internal source history reference.');s.current=s.history.get(data.sourceArchiveRef);return;}if(data.sourceArchive){const value=freeze(validate(K.clone(data.sourceArchive))),entry={id:K.uid('source'),value};s.current=entry;s.history.set(entry.id,entry);}else s.current=null;}
 function original(doc){const a=state(doc).current?.value;if(!a)throw Error('This drawing has no archived source.');const value=a.original||a;return {bytes:decode64(value.bytes),name:value.name,format:value.format};}
 function withOriginal(data,input,name){const raw=bytes(input);if(raw.length>MAX||!/^AC\d{4}/.test(new TextDecoder().decode(raw.subarray(0,6))))throw Error('Invalid DWG source signature.');if(data.sourceArchive)data.sourceArchive.original={name,format:'dwg',bytes:encode64(raw)};else data.sourceArchive={schema:1,name,format:'dwg',bytes:encode64(raw),byteLength:raw.length,baseline:baseline(data)};return data;}
 const supported=new Set(['LINE','POINT','CIRCLE','ARC','ELLIPSE','LWPOLYLINE','SPLINE','TEXT']);
 function canonical(entity,document){if(entity.solid||entity.type==='INSERT'||entity.type==='MESH'||entity.type==='HATCH'||entity.type==='DIMENSION'||entity.type==='TABLE'||entity.type==='LEADER'||entity.type==='TEXT'&&entity.text.includes('\n'))throw Error('Source-preserving edits support simple single-record curves and single-line TEXT.');const p=K.Production.defaults();if(document.production?.textstyles)p.textstyles=K.clone(document.production.textstyles);const d=K.Drawing.from({format:'kestrel-cad',version:2,name:'record',units:document.units,currentLayer:entity.layer,layers:K.clone(document.layers),entities:[K.clone(entity)],production:p});const records=scanASCII(E.writeDXF(d)).records.filter(r=>r.section==='ENTITIES'&&r.type!=='SECTION'&&r.type!=='ENDSEC');if(records.length!==1||!supported.has(records[0].type))throw Error('Entity does not have a supported single-record representation.');return records[0];}
 const values=(record,code)=>record.ordinary.filter(t=>t.code===code).map(t=>[1,3,1000].includes(code)?t.value:t.value.trim());
 function applyPatches(source,patches){const ordered=patches.slice().sort((a,b)=>a.start-b.start||a.end-b.end),parts=[];let p=0;for(const patch of ordered){if(patch.start<p||patch.end<patch.start||patch.end>source.data.length)throw Error('Overlapping source edits were rejected.');parts.push(source.data.subarray(p,patch.start),patch.bytes);p=patch.end;}parts.push(source.data.subarray(p));return concat(parts);}
 function evaluate(doc,{write=false}={}){const entry=state(doc).current,a=entry?.value;if(!a)throw Error('This drawing has no source archive.');const current=baseline(doc.serialize()),old=a.baseline,issues=[],changes={modified:0,added:0,removed:0};
  if(a.format==='dwg')return {unchanged:equal(current,old),canPreserve:false,changes,issues:['DWG originals are available through SOURCEORIGINAL; source-preserving DXF export requires a DXF view.'],format:a.format};
  if(equal(current,old))return {unchanged:true,canPreserve:true,changes,issues,format:a.format,bytes:write?decode64(a.bytes):undefined};
  
  const source=scan(decode64(a.bytes)),patches=[],prior=new Map(old.entities.map(e=>[e.id,e])),now=new Map(current.entities.map(e=>[e.id,e]));
  if(!equal(current.layers,old.layers))issues.push('Layer table changes require a converted export.');if(current.units!==old.units)issues.push('Unit changes cannot be applied to opaque source geometry.');if(!equal(current.production,old.production))issues.push('Block/style/layout/constraint definition changes require a converted export.');
  const handleRecords=new Map();for(const r of source.records){if(r.handle){if(!handleRecords.has(r.handle))handleRecords.set(r.handle,[]);handleRecords.get(r.handle).push(r);}}
  const model=r=>r.section==='ENTITIES'&&!r.ordinary.some(t=>t.code===67&&Number(t.value)===1);
  const recordFor=e=>{const h=e.sourceHandle?.toUpperCase(),rs=handleRecords.get(h);if(!h||!rs||rs.length!==1||!model(rs[0]))throw Error('Entity lacks a unique model-space source handle.');return rs[0];};
  const replacedHandles=new Set(),deleted=new Set(),additions=[];
  for(const e of old.entities){const n=now.get(e.id);if(n&&equal(n,e))continue;changes[n?'modified':'removed']++;
   try{const r=recordFor(e);if(replacedHandles.has(r.handle))throw Error('Several native objects share one source record.');replacedHandles.add(r.handle);
    if(!n){if(!supported.has(r.type))throw Error('Deleting compound or opaque source entities is not supported.');deleted.add(r.handle);patches.push({start:r.start,end:r.end,bytes:new Uint8Array()});continue;}
    if(!equal(e.group,n.group)||!equal(e.opacity,n.opacity))throw Error('Native grouping/opacity changes are not encoded by source-preserving export.');
    const before=canonical(e,old),after=canonical(n,current);if(r.type!==before.type||r.type!==after.type)throw Error('Entity-type conversion would invalidate source metadata.');
    if(e.type==='POLYLINE'&&e.points.length!==n.points.length)throw Error('Changing vertex count requires converted export.');
    if(e.type==='SPLINE'&&(e.controlPoints||e.points).length!==(n.controlPoints||n.points).length)throw Error('Changing spline topology requires converted export.');
    // Reactors/application data can depend on edited geometry. Never claim that preserving
    // those bytes evaluates their private constraints or regenerates proxy graphics.
    if(r.tags.some(t=>t.code===102&&/REACTOR/i.test(t.value)))throw Error('Persistent reactors require their originating application for source-preserving edits.');
    const overrides=new Map();
    if(e.color!==n.color){const by=n.color==null||n.color==='bylayer';overrides.set(62,[by?'256':n.color==='byblock'?'0':'7']);overrides.set(420,by||n.color==='byblock'?[]:[String(parseInt(n.color.slice(1),16))]);overrides.set(430,[]);}
    if(e.linetype!==n.linetype){const label=n.linetype||'ByLayer';if(!['bylayer','byblock','continuous'].includes(label.toLowerCase())&&!source.records.some(t=>t.type==='LTYPE'&&values(t,2)[0]?.toLowerCase()===label.toLowerCase()))throw Error('The assigned linetype is not defined in the source file.');overrides.set(6,[label]);}
    const codes=new Set([...before.ordinary,...after.ordinary].map(t=>t.code));for(const c of overrides.keys())codes.add(c);const ignore=new Set([0,5,105,330,100]);
    const insertion=r.tags.find(t=>t.code===1001)?.start??r.end;const extra=[];
    for(const c of codes){if(ignore.has(c)||!overrides.has(c)&&equal(values(before,c),values(after,c)))continue;const originalTags=r.ordinary.filter(t=>t.code===c),newValues=overrides.get(c)||values(after,c);
     const mask=c===70&&r.type==='LWPOLYLINE'?1:c===70&&r.type==='SPLINE'?5:c===71&&r.type==='TEXT'?6:null;
     if(mask!==null&&newValues.length===1&&originalTags.length===1)newValues[0]=String((Number(originalTags[0].value)&~mask)|(Number(newValues[0])&mask));if(c===420&&newValues.length&&Number(source.version.slice(2))<1018)throw Error('True-color changes require DXF R2004 or later.');
     for(let i=0;i<originalTags.length;i++){const t=originalTags[i];patches.push({start:t.start,end:t.end,bytes:i<newValues.length?pairBytes(c,newValues[i],source):new Uint8Array()});}
     for(let i=originalTags.length;i<newValues.length;i++)extra.push(pairBytes(c,newValues[i],source));
    }if(extra.length)patches.push({start:insertion,end:insertion,bytes:concat(extra)});
   }catch(error){issues.push((n?'Edit ':'Delete ')+e.id+': '+error.message);}
  }
  for(const e of current.entities)if(!prior.has(e.id)){changes.added++;try{const r=canonical(e,current);if(Number(source.version.slice(2))<1015)throw Error('Adding entities requires R2000 or later in source-preserving mode.');if(Number(source.version.slice(2))<1018&&r.ordinary.some(t=>t.code===420))throw Error('Adding true-color entities requires DXF R2004 or later.');additions.push(r);}catch(error){issues.push('Add '+e.id+': '+error.message);}}
  for(const r of source.records){if(deleted.has(r.handle))continue;for(const t of r.tags)if(t.code>=320&&t.code<=369&&deleted.has(t.value.trim().toUpperCase()))issues.push('Deletion is referenced by '+r.type+' '+(r.handle||'')+'; preserve-source export blocked.');}
  if(additions.length){const owner=source.records.find(r=>r.type==='BLOCK_RECORD'&&values(r,2)[0]?.toUpperCase()==='*MODEL_SPACE')?.handle;
   if(!owner)issues.push('No model-space BLOCK_RECORD owner exists for new entities.');else{let next=0x100n;for(const r of source.records)if(r.handle&&hex(r.handle))next=next>BigInt('0x'+r.handle)?next:BigInt('0x'+r.handle);const chunks=[];
    for(const r of additions){const handle=(++next).toString(16).toUpperCase();for(const t of r.ordinary)chunks.push(pairBytes(t.code,t.code===5?handle:t.code===330?owner:t.value,source));}
    patches.push({start:source.endEntities,end:source.endEntities,bytes:concat(chunks)});
    const index=source.tags.findIndex(t=>t.code===9&&t.value.trim()==='$HANDSEED');if(index>=0&&source.tags[index+1]?.code===5){const t=source.tags[index+1];patches.push({start:t.start,end:t.end,bytes:pairBytes(5,(next+1n).toString(16).toUpperCase(),source)});}
   }
  }
  const unique=[...new Set(issues)];return {unchanged:false,canPreserve:!unique.length,changes,issues:unique,format:a.format,bytes:write&&!unique.length?applyPatches(source,patches):undefined};
 }
 function write(doc){const r=evaluate(doc,{write:true});if(!r.canPreserve)throw Error(r.issues.join('\n'));return r.bytes;}
 const parse=E.parseDXF;
 E.parseDXF=function(input,name='Imported drawing'){const raw=bytes(input),source=scan(raw),text=source.binary?source.tags.map(t=>t.code+'\n'+t.value).join('\n')+'\n':input;const result=parse(text,name);result.data.sourceArchive=create(result.data,raw,name.toLowerCase().endsWith('.dxf')?name:name+'.dxf');result.report.sourcePreserved=true;result.report.binary=source.binary;result.report.warnings.push('Original bytes and all opaque records are archived. The editable view is a supported subset; use Source report before a source-preserving export.');return result;};
 K.SourceArchive={MAX,scan,scanASCII,scanBinary,kind,pairBytes,binaryDXF,create,validate,serialize,restore,original,withOriginal,evaluate,write,encode64,decode64,has:doc=>!!state(doc).current};
})(typeof window!=='undefined'?window:globalThis);
