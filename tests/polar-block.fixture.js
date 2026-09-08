/* Original synthetic geometry shared by numerical, browser and interchange checks. */
(function(root) {
    root.makePolarBlockFixture=function(options={}) {
        const K=root.Kestrel,doc=new K.Drawing('Polar blocks and table matching');doc.currentLayer='0';
        const block={id:'polarBlock',name:'Radial fitting',entities:[
            {id:'radial',type:'LINE',points:[[10,0,0],[12,0,0]],layer:'0',color:'byblock'},
            {id:'hole',type:'CIRCLE',center:[10,0,0],radius:1,layer:'0',color:'bylayer'}
        ],attributes:[{tag:'PART',value:'${Variant} / ${Gain}',position:[10,-2,0],height:1}],dynamic:{version:1,
            parameters:[{name:'Count',type:'integer',default:4,min:1,max:20000},
                {name:'Sweep',type:'angle',default:360,min:-360,max:360},
                {name:'Size',type:'length',default:1,min:1e-7,max:1e9},
                {name:'Finish',type:'boolean',default:false},
                {name:'Variant',type:'enum',default:'Small',values:['Small','Large','Long']},
                {name:'Gain',type:'number',default:2,expression:'Size * 2'}],
            lookups:[{parameter:'Variant',rows:[{value:'Small',set:{Size:1,Finish:false}},
                {value:'Large',set:{Size:2,Finish:false}},{value:'Long',set:{Size:2,Finish:true}}]}],
            actions:[{type:'scale',targets:['hole'],factor:'Size',center:[10,0,0]},
                {type:'polar-array',targets:['radial','hole','attribute:PART'],count:'Count',angle:'Sweep',
                 center:[0,0,0],axis:[0,0,1],...options}]
        }};
        doc.production.blocks.push(block);
        const insert=doc.add('INSERT',{block:block.id,matrix:Array.from(K.Math.M.identity()),parameters:{},attributes:{},color:'#55aacc'});
        doc.reindex();return {doc,block,insert};
    };
})(globalThis);
