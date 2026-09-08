/* Optional maintainer tool. Runtime/build.py use the checked-in plain JS bundle. */
const fs=require('fs'), path=require('path');
let ts; try{ts=require('typescript');}catch{const globalRoot=require('child_process').execFileSync(process.platform==='win32'?'npm.cmd':'npm',['root','-g'],{encoding:'utf8'}).trim();ts=require(path.join(globalRoot,'typescript'));}
const root=path.resolve(__dirname,'..'), base=path.join(root,'third_party/bidi-shaper/src');
function files(dir){return fs.readdirSync(dir,{withFileTypes:true}).flatMap(e=>e.isDirectory()?files(path.join(dir,e.name)):e.name.endsWith('.ts')?[path.join(dir,e.name)]:[]);}
let out='/* MIT: bidi-shaper contributors. See third_party/bidi-shaper/LICENSE and manifest.json. */\n(function(root){"use strict";const modules={\n';
for(const f of files(base).sort()){const key=path.relative(base,f).replace(/\\/g,'/').replace(/\.ts$/,'');const js=ts.transpileModule(fs.readFileSync(f,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,removeComments:true}}).outputText;out+=JSON.stringify(key)+':function(exports,require){\n'+js+'},\n';}
out+='};const cache=Object.create(null);function load(id){if(cache[id])return cache[id];if(!Object.prototype.hasOwnProperty.call(modules,id))throw Error("Unknown Unicode module "+id);const e=cache[id]={};modules[id](e,rel=>{const p=id.split("/");p.pop();for(const s of rel.split("/")){if(s==="..")p.pop();else if(s!==".")p.push(s);}return load(p.join("/"));});return e;}root.Kestrel.Unicode={...load("index"),...load("bidi/algorithm"),...load("bidi/reorder"),...load("bidi/levels"),BIDI_CLASS_NAMES:load("data/generated/bidi-classes").BIDI_CLASS_NAMES};})(globalThis);\n';
fs.writeFileSync(path.join(root,'src/unicode-bidi.js'),out);
console.log('Built Unicode bundle:',out.length);
