/* Deterministic field-bearing drawing used by the independent DXF reader. */
'use strict';
globalThis.makeFieldsFixture=function(){
 const K=globalThis.Kestrel,F=K.Fields,d=new K.Drawing('Linked fabrication');let line,circle,text,rich,ref;
 d.transaction('Fixture',()=>{
  line=d.add('LINE',{id:'partLength',points:[[0,0,0],[30,40,0]]});
  circle=d.add('CIRCLE',{id:'partCircle',center:[90,10,0],radius:10});
  text=d.add('TEXT',{id:'lengthLabel',position:[0,80,0],height:3,text:'Pending'});
  rich=d.add('MTEXT',{id:'richLabel',position:[0,100,0],height:5,width:200,text:'Pending'});
  d.production.blocks.push({id:'titleBlock',name:'Title block',entities:[],attributes:[{tag:'SIZE',value:'?',position:[0,0,0],height:3}]});
  ref=d.add('INSERT',{id:'titleRef',block:'titleBlock',matrix:Array.from(K.Math.M.translation(0,120,0)),attributes:{}});
 });
 const bind=(entity,target,template,sources,extra={})=>F.setBinding(d,entity.id,{version:1,target,template,sources,precision:3,...extra});
 bind(text,'text','Length {{Value}} cm',[{name:'Value',kind:'object',entity:line.id,property:'length',units:'cm'}]);
 F.setProperties(d,[{name:'Title',value:'Zażółć — שלום — مرحبا 🚀'}]);
 bind(rich,'text','{\\L{{Title}}\\l}\\PCost {{Result}}',[{name:'Title',kind:'property',key:'Title'},{name:'Area',kind:'object',entity:circle.id,property:'area',units:'cm'},{name:'Rate',kind:'literal',value:12.5}],{expression:'Area * Rate',precision:5});
 bind(ref,'attribute:SIZE','L={{Value}} mm',[{name:'Value',kind:'object',entity:line.id,property:'length'}],{precision:1});
 const table=F.linkedTable(d,[line.id,circle.id],[0,-30,0],{columns:[{label:'Object',property:'type'},{label:'Length mm',property:'length',units:'mm'},{label:'Area mm2',property:'area',units:'mm'}],precision:5});
 return {doc:d,line,circle,text,rich,ref,table};
};
