'use strict';
// Original synthetic glyph programs, constructed in memory; not a bundled font asset.
function fixture(unicode=false,overrides={}){
 const shapes={32:[2,8,6,0,0],65:[9,0,10,6,-10,0,0,2,8,2,0,0],66:[5,4,2,8,2,3,6,3,2,2,8,8,0,0],67:[10,5,0x04,0],68:[11,56,28,0,3,0x12,0],69:[12,10,0,127,0],70:[13,10,0,127,10,0,129,0,0,0],71:[7,65,0],72:[14,8,0,246,8,5,0,0],73:[0x24,0x20,0],74:[9,1,2,3,4,0,0,0],75:[10,5,0x84,0],76:[2,12,10,0,127,0],77:[5,8,10,0,6,0],78:[14,9,1,0,1,0,0,0,8,3,0,0],...overrides};
 const ascii=s=>[...Buffer.from(s,'ascii')],u16=n=>[n&255,n>>8];
 if(unicode){const head=[...ascii('Synthetic'),0,10,2,2,0,0,0],records=Object.entries(shapes).map(([id,data])=>{if(+id===71)data=[7,65,0,0];const record=[0,...data];return [...u16(+id),...u16(record.length),...record];});return Uint8Array.from([...ascii('AutoCAD-86 unifont 1.0\r\n'),26,...u16(records.length+1),0,0,...u16(head.length),...head,...records.flat()]);}
 const records=[[0,[...ascii('Synthetic'),0,10,2,2,0]],...Object.entries(shapes).map(([id,codes])=>[+id,[0,...codes]])];
 return Uint8Array.from([...ascii('AutoCAD-86 shapes 1.0\r\n'),26,...u16(0),...u16(records.at(-1)[0]),...u16(records.length),...records.flatMap(([id,r])=>[...u16(id),...u16(r.length)]),...records.flatMap(([id,r])=>r),...ascii('EOF')]);
}
module.exports={fixture};
