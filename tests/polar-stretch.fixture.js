/* Original fixture, shared by numerical, browser and independent DXF checks. */
(function(root){
'use strict';
root.makePolarStretchFixture=function(options={}) {
 const K=root.Kestrel,doc=new K.Drawing('Polar stretch linkage');doc.currentLayer='0';
 const block={id:'arm-definition',name:'Adjustable arm',entities:[
  {id:'arm',type:'LINE',points:[[0,0,0],[10,0,0]],layer:'0',color:'byblock'},
  {id:'tip',type:'CIRCLE',center:[10,0,0],radius:1,layer:'0',color:'byblock'},
  {id:'pivot',type:'LINE',points:[[3,0,0],[5,0,0]],layer:'0'},
  {id:'fixed',type:'POINT',position:[40,0,0],layer:'0'}
 ],attributes:[{tag:'LABEL',value:'Reach ${Reach}',position:[10,-1,0],height:1}],dynamic:{version:1,
  parameters:[{name:'Reach',type:'length',default:10,min:.1,max:200},{name:'Angle',type:'angle',default:0,min:-360,max:360}],
  actions:[{type:'polar-stretch',targets:['arm','tip','pivot','attribute:LABEL'],rotateOnly:['pivot'],
   min:[8,-2,-2],max:[12,2,2],baseLength:10,length:'Reach',angle:'Angle',...options}]
 }};
 doc.transaction('Create linkage',()=>doc.production.blocks.push(block));
 const insert=K.Production.insertBlock(doc,block.id,[0,0,0]);
 return {doc,block:doc.production.blocks[0],insert};
};
})(typeof window!=='undefined'?window:globalThis);
