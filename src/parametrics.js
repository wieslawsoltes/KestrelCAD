/* Kestrel CAD — bounded 2D parametric sketch solver. No eval or external solver. */
(function(root) {
  'use strict';
  const K = root.Kestrel = root.Kestrel || {};
  const LIMIT = 128;
  const finite = (v, label = 'Value') => {
    if (typeof v !== 'number' || !Number.isFinite(v) || Math.abs(v) > 1e15) throw new Error(label + ' must be finite and within ±1e15.');
    return v;
  };
  const functions = Object.freeze({abs:Math.abs,sqrt:Math.sqrt,sin:Math.sin,cos:Math.cos,tan:Math.tan,asin:Math.asin,acos:Math.acos,atan:Math.atan,atan2:Math.atan2,min:Math.min,max:Math.max,floor:Math.floor,ceil:Math.ceil,round:Math.round,deg:x=>x*180/Math.PI,rad:x=>x*Math.PI/180});
  function expression(source, resolve = () => { throw new Error('Unknown parameter.'); }) {
    if (typeof source === 'number') return finite(source);
    if (typeof source !== 'string' || source.length > 4096) throw new Error('Invalid parameter expression.');
    const tokens = []; let i=0;
    while(i<source.length) {
      if (/\s/.test(source[i])) { i++; continue; }
      const rest=source.slice(i), number=rest.match(/^(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?/), name=rest.match(/^[A-Za-z_][A-Za-z_0-9]*/);
      if(number) {tokens.push({number:Number(number[0])}); i+=number[0].length;}
      else if(name) {tokens.push({name:name[0]});i+=name[0].length;}
      else if('+-*/^(),'.includes(source[i])) tokens.push(source[i++]);
      else throw new Error('Unexpected character in expression at '+(i+1)+'.');
      if(tokens.length>512) throw new Error('Expression is too complex.');
    }
    let at=0,depth=0;
    const take=()=>tokens[at++];
    function parse(minimum=0) {
      if(++depth>64) throw new Error('Expression nesting limit exceeded.');
      let token=take(), value;
      if(token==='+' || token==='-') { value=parse(25); if(token==='-') value=-value; }
      else if(token==='(') {value=parse(); if(take()!==')') throw new Error('Missing closing parenthesis.');}
      else if(token && typeof token==='object' && 'number' in token) value=finite(token.number);
      else if(token && token.name) {
        const name=token.name;
        if(tokens[at]==='(') {
          if(!Object.hasOwn(functions,name)) throw new Error('Unknown function: '+name);
          take(); const args=[];
          if(tokens[at]!==')') {do {args.push(parse()); if(tokens[at]!==',') break; take();} while(args.length<32);}
          if(take()!==')' || args.length===0 || args.length>31) throw new Error('Invalid function arguments.');
          if(!['min','max','atan2'].includes(name) && args.length!==1 || name==='atan2' && args.length!==2) throw new Error('Wrong number of function arguments.');
          value=finite(functions[name](...args),'Function result');
        } else value=name==='pi'?Math.PI:name==='e'?Math.E:finite(resolve(name),'Parameter '+name);
      } else throw new Error('Expected a number, parameter or parenthesis.');
      for(;;) {
        const op=tokens[at], precedence=op==='+'||op==='-'?10:op==='*'||op==='/'?20:op==='^'?30:-1;
        if(precedence<minimum) break;
        take(); const right=parse(precedence+(op==='^'?0:1));
        if(op==='+') value+=right;
        if(op==='-') value-=right;
        if(op==='*') value*=right;
        if(op==='/') {if(right===0) throw new Error('Division by zero.');value/=right;}
        if(op==='^') value=Math.pow(value,right);
        finite(value,'Expression result');
      }
      depth--;return finite(value);
    }
    const value=parse(); if(at!==tokens.length) throw new Error('Unexpected trailing expression input.'); return value;
  }
  function parameters(definitions={}) {
    if(!definitions || typeof definitions!=='object' || Array.isArray(definitions) || Object.keys(definitions).length>128) throw new Error('Invalid named parameters.');
    const result=Object.create(null), visiting=new Set();
    for(const name of Object.keys(definitions)) if(!/^[A-Za-z_][A-Za-z_0-9]{0,63}$/.test(name) || ['pi','e','__proto__','constructor','prototype'].includes(name) || Object.hasOwn(functions,name)) throw new Error('Invalid or reserved parameter name: '+name);
    function resolve(name) {
      if(Object.hasOwn(result,name)) return result[name];
      if(!Object.hasOwn(definitions,name)) throw new Error('Unknown parameter: '+name);
      if(visiting.has(name)) throw new Error('Circular parameter dependency: '+name);
      visiting.add(name);result[name]=expression(definitions[name],resolve);visiting.delete(name);return result[name];
    }
    for(const name of Object.keys(definitions)) resolve(name);
    return result;
  }
  const types=Object.freeze(['coincident','horizontal','vertical','length','distance','dx','dy','parallel','perpendicular','angle','equalLength','radius','diameter','concentric','equalRadius','tangent','pointOnLine','pointOnCircle','midpoint','symmetry','fix']);
  const sub=(a,b)=>[a[0]-b[0],a[1]-b[1]], dot=(a,b)=>a[0]*b[0]+a[1]*b[1], cross=(a,b)=>a[0]*b[1]-a[1]*b[0], length=a=>Math.hypot(...a);
  function linearSolve(matrix,rhs) {
    const n=rhs.length, a=matrix.map((row,i)=>[...row,rhs[i]]);
    for(let col=0;col<n;col++) {
      let pivot=col;for(let row=col+1;row<n;row++) if(Math.abs(a[row][col])>Math.abs(a[pivot][col])) pivot=row;
      if(Math.abs(a[pivot][col])<1e-18) return null;
      [a[col],a[pivot]]=[a[pivot],a[col]];
      for(let row=col+1;row<n;row++) {
        const f=a[row][col]/a[col][col];if(f===0) continue;
        for(let k=col;k<=n;k++) a[row][k]-=f*a[col][k];
      }
    }
    const x=new Array(n).fill(0);
    for(let i=n-1;i>=0;i--) {let v=a[i][n];for(let j=i+1;j<n;j++) v-=a[i][j]*x[j];x[i]=v/a[i][i];}
    return x.every(Number.isFinite)?x:null;
  }
  function rank(matrix) {
    if(!matrix.length) return 0;
    const a=matrix.map(r=>[...r]);let row=0;const n=a[0].length;
    let maximum=0;for(const r of a) for(const v of r) maximum=Math.max(maximum,Math.abs(v));
    const threshold=Math.max(1e-10,maximum*1e-7);
    for(let col=0;col<n && row<a.length;col++) {
      let pivot=row;for(let i=row+1;i<a.length;i++) if(Math.abs(a[i][col])>Math.abs(a[pivot][col])) pivot=i;
      if(Math.abs(a[pivot][col])<threshold) continue;
      [a[row],a[pivot]]=[a[pivot],a[row]];
      for(let i=row+1;i<a.length;i++) {const f=a[i][col]/a[row][col];for(let j=col;j<n;j++) a[i][j]-=f*a[row][j];}
      row++;
    }
    return row;
  }
  function solveSketch(sketch,options={}) {
    const names=Object.keys(sketch.points||{}), circleNames=Object.keys(sketch.circles||{}), variables=2*names.length+circleNames.length;
    if(!variables || variables>LIMIT) throw new Error('A constraint sketch supports 1–128 scalar variables.');
    const constraints=(sketch.constraints||[]).filter(c=>c.enabled!==false);
    if(constraints.length>128) throw new Error('At most 128 active constraints are supported per sketch.');
    const resolved=parameters(sketch.parameters||{}), indexes=new Map(names.map((name,i)=>[name,i*2]));
    const p0=names.map(name=>{const p=sketch.points[name];if(!Array.isArray(p)||p.length!==2)throw new Error('Invalid sketch point.');return p.map(v=>finite(v));});
    const origin=[0,0];for(const p of p0) {origin[0]+=p[0]/p0.length;origin[1]+=p[1]/p0.length;}
    let scale=1;for(const p of p0) scale=Math.max(scale,length(sub(p,origin)));
    for(const name of circleNames) scale=Math.max(scale,finite(sketch.circles[name].radius));
    let x=p0.flatMap(p=>[(p[0]-origin[0])/scale,(p[1]-origin[1])/scale]);
    const radii=new Map();
    for(const name of circleNames) {const c=sketch.circles[name];if(!(c.radius>1e-9)||!indexes.has(c.center))throw new Error('Invalid sketch circle.');radii.set(name,x.length);x.push(Math.log(c.radius/scale));}
    const compiled=constraints.map((c,i)=>{
      if(!c || !types.includes(c.type)) throw new Error('Unknown constraint type: '+c?.type);
      return {...c,id:c.id||'constraint-'+i,number:'value' in c?expression(c.value,n=>{if(!Object.hasOwn(resolved,n))throw new Error('Unknown parameter: '+n);return resolved[n];}):undefined};
    });
    const rows=[];
    function residual(v,record=false) {
      if(record) rows.length=0;
      const result=[];
      const point=id=>{const i=indexes.get(id);if(i===undefined)throw new Error('Constraint references an unknown point.');return [v[i],v[i+1]];};
      const line=id=>{const ends=sketch.lines?.[id];if(!Array.isArray(ends)||ends.length!==2)throw new Error('Constraint requires a line.');return ends.map(point);};
      const direction=id=>{const [a,b]=line(id),d=sub(b,a);if(length(d)<1e-12)throw new Error('A constrained line is degenerate.');return d;};
      const circle=id=>{const c=sketch.circles?.[id],i=radii.get(id);if(!c||i===undefined)throw new Error('Constraint requires a circle.');const r=Math.exp(v[i]);if(!Number.isFinite(r)||r<1e-14||r>1e14)throw new Error('Circle radius left the numerical range.');return {center:point(c.center),radius:r};};
      const normalized=d=>{const n=length(d);if(n<1e-12)throw new Error('Degenerate constraint direction.');return d.map(x=>x/n);};
      for(const c of compiled) {
        let r=[];const target=()=>{if(c.number===undefined)throw new Error('A driving value is required.');return c.number/scale;};
        switch(c.type) {
          case 'coincident': r=sub(point(c.a),point(c.b));break;
          case 'horizontal': r=[direction(c.a)[1]];break;
          case 'vertical': r=[direction(c.a)[0]];break;
          case 'length': {const t=target();if(t<=0)throw new Error('Length must be positive.');r=[length(direction(c.a))-t];break;}
          case 'distance': {const t=target();if(t<0)throw new Error('Distance cannot be negative.');r=[length(sub(point(c.a),point(c.b)))-t];break;}
          case 'dx': r=[point(c.b)[0]-point(c.a)[0]-target()];break;
          case 'dy': r=[point(c.b)[1]-point(c.a)[1]-target()];break;
          case 'parallel': r=[cross(normalized(direction(c.a)),normalized(direction(c.b)))];break;
          case 'perpendicular': r=[dot(normalized(direction(c.a)),normalized(direction(c.b)))];break;
          case 'angle': {if(c.number===undefined)throw new Error('Angle requires a driving value in degrees.');const a=direction(c.a),b=direction(c.b),t=c.number*Math.PI/180,d=Math.atan2(cross(a,b),dot(a,b))-t;r=[Math.atan2(Math.sin(d),Math.cos(d))];break;}
          case 'equalLength': r=[length(direction(c.a))-length(direction(c.b))];break;
          case 'radius': case 'diameter': {const t=target();if(t<=0)throw new Error('Radius/diameter must be positive.');r=[circle(c.a).radius*(c.type==='diameter'?2:1)-t];break;}
          case 'concentric': r=sub(circle(c.a).center,circle(c.b).center);break;
          case 'equalRadius': r=[circle(c.a).radius-circle(c.b).radius];break;
          case 'tangent': {
            if(sketch.lines?.[c.a] || sketch.lines?.[c.b]) {const lid=sketch.lines?.[c.a]?c.a:c.b,cid=lid===c.a?c.b:c.a,ends=line(lid),d=normalized(sub(ends[1],ends[0])),q=circle(cid),signed=cross(sub(q.center,ends[0]),d);r=[Math.abs(signed)-q.radius];}
            else {const a=circle(c.a),b=circle(c.b);r=[length(sub(a.center,b.center))-(c.internal?Math.abs(a.radius-b.radius):a.radius+b.radius)];}break;
          }
          case 'pointOnLine': {const [a,b]=line(c.b);r=[cross(sub(point(c.a),a),normalized(sub(b,a)))];break;}
          case 'pointOnCircle': {const q=circle(c.b);r=[length(sub(point(c.a),q.center))-q.radius];break;}
          case 'midpoint': {const a=point(c.b),b=point(c.c),p=point(c.a);r=[p[0]-(a[0]+b[0])/2,p[1]-(a[1]+b[1])/2];break;}
          case 'symmetry': {const a=point(c.a),b=point(c.b),[s,t]=line(c.axis),d=normalized(sub(t,s));r=[cross(sub([(a[0]+b[0])/2,(a[1]+b[1])/2],s),d),dot(sub(b,a),d)];break;}
          case 'fix': {if(!Array.isArray(c.target)||c.target.length!==2)throw new Error('Fixed point requires two local coordinates.');const p=point(c.a);r=[p[0]-(finite(c.target[0])-origin[0])/scale,p[1]-(finite(c.target[1])-origin[1])/scale];break;}
        }
        for(const value of r) {if(!Number.isFinite(value))throw new Error('Non-finite constraint residual.');result.push(value);if(record)rows.push(c.id);}
      }
      return result;
    }
    function jacobian(v,r) {
      const j=r.map(()=>new Array(v.length).fill(0));
      for(let k=0;k<v.length;k++) {
        const h=1e-6*Math.max(1,Math.abs(v[k])),plus=[...v],minus=[...v];plus[k]+=h;minus[k]-=h;
        const a=residual(plus),b=residual(minus);
        for(let row=0;row<r.length;row++)j[row][k]=(a[row]-b[row])/(2*h);
      }
      return j;
    }
    const norm=r=>r.reduce((sum,v)=>sum+v*v,0), max=r=>r.reduce((a,v)=>Math.max(a,Math.abs(v)),0);
    const tolerance=Math.max(1e-10,Math.min(1e-7,(options.tolerance||1e-7)/scale));
    let r=residual(x),lambda=1e-3,iterations=0;
    for(;iterations<80 && max(r)>tolerance;iterations++) {
      const j=jacobian(x,r),a=x.map(()=>new Array(x.length).fill(0)),b=new Array(x.length).fill(0);
      for(let row=0;row<j.length;row++) for(let i=0;i<x.length;i++) {b[i]-=j[row][i]*r[row];for(let k=0;k<x.length;k++)a[i][k]+=j[row][i]*j[row][k];}
      for(let i=0;i<x.length;i++)a[i][i]+=lambda*Math.max(1,a[i][i]);
      const step=linearSolve(a,b);if(!step) {lambda*=10;continue;}
      const next=x.map((v,i)=>v+step[i]);let nextR;
      try {nextR=residual(next);} catch {lambda=Math.min(1e14,lambda*10);continue;}
      if(norm(nextR)<norm(r)) {x=next;r=nextR;lambda=Math.max(1e-12,lambda/3);} else lambda=Math.min(1e14,lambda*10);
      if(lambda===1e14)break;
    }
    r=residual(x,true);
    const numericalRank=rank(jacobian(x,r)),converged=max(r)<=tolerance,conflict=new Map();
    for(let i=0;i<r.length;i++) if(Math.abs(r[i])>tolerance) conflict.set(rows[i],Math.max(conflict.get(rows[i])||0,Math.abs(r[i])));
    const points=Object.fromEntries(names.map((name,i)=>[name,[x[2*i]*scale+origin[0],x[2*i+1]*scale+origin[1]]]));
    const circles=Object.fromEntries(circleNames.map(name=>[name,{...sketch.circles[name],radius:Math.exp(x[radii.get(name)])*scale}]));
    return {converged,iterations,variables,equations:r.length,rank:numericalRank,degreesOfFreedom:variables-numericalRank,redundantEquations:Math.max(0,r.length-numericalRank),normalizedResidual:max(r),conflicts:[...conflict].sort((a,b)=>b[1]-a[1]).map(([id,residual])=>({id,residual})),points,circles,parameters:{...resolved}};
  }
  const key=(entity,index)=>JSON.stringify([entity,index]);
  function plane(doc) {
    const value=doc.production?.parametrics?.plane || doc.production?.ucs || {origin:[0,0,0],x:[1,0,0],y:[0,1,0]};
    const v3=(v,label)=>{if(!Array.isArray(v)||v.length!==3)throw new Error('Invalid '+label);return v.map(x=>finite(x,label));};
    const origin=v3(value.origin,'plane origin'),unit=v=>{const n=Math.hypot(...v);if(n<1e-12)throw new Error('Zero plane axis');return v.map(x=>x/n);},x=unit(v3(value.x,'plane X')),y=unit(v3(value.y,'plane Y'));
    if(Math.abs(x.reduce((s,v,i)=>s+v*y[i],0))>1e-8)throw new Error('Constraint plane axes must be orthogonal.');
    const z=[x[1]*y[2]-x[2]*y[1],x[2]*y[0]-x[0]*y[2],x[0]*y[1]-x[1]*y[0]];
    return {origin,x,y,z};
  }
  const local=(p,f)=>{const d=p.map((v,i)=>finite(v)-f.origin[i]);if(Math.abs(d.reduce((s,v,i)=>s+v*f.z[i],0))>1e-6)throw new Error('Constrained geometry must be coplanar with the sketch UCS.');return [d.reduce((s,v,i)=>s+v*f.x[i],0),d.reduce((s,v,i)=>s+v*f.y[i],0)];};
  const world=(p,f)=>f.origin.map((v,i)=>v+p[0]*f.x[i]+p[1]*f.y[i]);
  function ensure(doc) {
    if(!doc.production) {if(K.Production)K.Production.ensure(doc);else doc.production={};}
    if(!doc.production.parametrics) {const f=plane(doc);doc.production.parametrics={version:1,parameters:{},constraints:[],plane:{origin:f.origin,x:f.x,y:f.y}};}
    return doc.production.parametrics;
  }
  function state(doc) {
    const store=ensure(doc),f=plane(doc),ids=new Set(store.constraints.filter(c=>c.enabled!==false).flatMap(c=>c.entities||[]));
    const sketch={points:{},lines:{},circles:{},constraints:store.constraints,parameters:store.parameters},entities=[];
    for(const id of ids) {
      const e=doc.entities.find(e=>e.id===id);if(!e)throw new Error('A constrained entity is missing: '+id);
      if(e.solid)throw new Error('Native solids cannot be edited by the 2D sketch solver.');
      if(e.type==='LINE' || e.type==='POLYLINE') {
        if(e.type==='POLYLINE' && (e.bulges||[]).some(v=>Math.abs(v)>1e-12))throw new Error('Constrain straight-vertex polylines; bulged segments are not supported.');
        e.points.forEach((p,i)=>sketch.points[key(id,i)]=local(p,f));
        if(e.points.length===2)sketch.lines[id]=[key(id,0),key(id,1)];
        else e.points.forEach((p,i)=>{if(i<e.points.length-1 || e.closed)sketch.lines[key(id,i)]=[key(id,i),key(id,(i+1)%e.points.length)];});
      } else if(e.type==='CIRCLE') {
        if(K.Geo?.conicAxes) {const axes=K.Geo.conicAxes(e);if(axes?.u && axes?.v) {const n=[axes.u[1]*axes.v[2]-axes.u[2]*axes.v[1],axes.u[2]*axes.v[0]-axes.u[0]*axes.v[2],axes.u[0]*axes.v[1]-axes.u[1]*axes.v[0]],l=Math.hypot(...n);if(l && Math.abs(Math.abs(n.reduce((s,v,i)=>s+v*f.z[i],0)/l)-1)>1e-6)throw new Error('Circle and sketch planes differ.');}}
        sketch.points[key(id,'center')]=local(e.center,f);sketch.circles[id]={center:key(id,'center'),radius:e.radius};
      } else throw new Error('Sketch constraints support lines, straight polylines and circles, not '+e.type+'.');
      entities.push(e);
    }
    return {store,f,sketch,entities};
  }
  function solve(doc,options={}) {
    const data=state(doc);
    if(!Object.keys(data.sketch.points).length) return {converged:true,variables:0,equations:0,rank:0,degreesOfFreedom:0,conflicts:[],parameters:{...parameters(data.store.parameters)}};
    const result=solveSketch(data.sketch,options);
    if(result.converged && options.apply!==false) for(const e of data.entities) {
      if(e.type==='CIRCLE') {e.center=world(result.points[key(e.id,'center')],data.f);e.radius=result.circles[e.id].radius;}
      else e.points=e.points.map((p,i)=>world(result.points[key(e.id,i)],data.f));
    }
    doc.parametricReport={...result,points:undefined,circles:undefined};return result;
  }
  function enforce(doc) {
    if(!doc.production?.parametrics || doc._suspendParametrics)return;
    const store=ensure(doc),existing=new Set(doc.entities.map(e=>e.id));
    store.constraints=store.constraints.filter(c=>(c.entities||[]).every(id=>existing.has(id)));
    const result=solve(doc);
    if(!result.converged)throw new Error('Constraint conflict; edit rolled back. Conflicting constraints: '+result.conflicts.slice(0,6).map(c=>c.id).join(', '));
  }
  function make(doc,type,entities,options={}) {
    if(!types.includes(type))throw new Error('Unsupported constraint type.');
    const ids=entities.map(e=>typeof e==='string'?e:e.id),items=ids.map(id=>doc.entities.find(e=>e.id===id));
    if(items.some(e=>!e) || !items.length)throw new Error('Select sketch entities first.');
    const c={id:K.uid?K.uid():'constraint-'+Math.random().toString(36).slice(2),type,enabled:true,entities:ids};
    const point=(e,index=0)=>key(e.id,e.type==='CIRCLE'?'center':index);
    if(['horizontal','vertical','length','radius','diameter'].includes(type)) {if(ids.length!==1)throw new Error('Select one entity.');c.a=ids[0];}
    else if(type==='fix') {if(ids.length!==1)throw new Error('Fix one point at a time.');const e=items[0],i=options.firstPoint||0;c.a=point(e,i);c.target=local(e.type==='CIRCLE'?e.center:e.points[i],plane(doc));}
    else if(['coincident','distance','dx','dy'].includes(type)) {if(ids.length!==2)throw new Error('Select two entities.');c.a=point(items[0],options.firstPoint||0);c.b=point(items[1],options.secondPoint||0);}
    else {if(ids.length!==2)throw new Error('Select two entities.');c.a=ids[0];c.b=ids[1];}
    if('value' in options)c.value=options.value;
    if(options.internal)c.internal=true;
    return c;
  }
  function validate(data) {
    const p=data.production?.parametrics;if(!p)return;
    if(p.version!==1 || !Array.isArray(p.constraints) || p.constraints.length>256)throw new Error('Invalid parametric sketch data.');
    parameters(p.parameters);plane({production:{parametrics:p}});
    const entities=new Set(data.entities.map(e=>e.id)),seen=new Set();
    for(const c of p.constraints) {
      if(!c || typeof c.id!=='string' || seen.has(c.id) || !types.includes(c.type) || !Array.isArray(c.entities) || !c.entities.length || c.entities.some(id=>!entities.has(id)))throw new Error('Invalid constraint or missing geometry reference.');
      seen.add(c.id);
      if(c.enabled!==undefined && typeof c.enabled!=='boolean')throw new Error('Invalid constraint enabled state.');
      if('value' in c) expression(c.value,n=>parameters(p.parameters)[n]);
    }
  }
  if(K.Production) {const previous=K.Production.validate;K.Production.validate=function(data){previous(data);validate(data);};}
  K.Parametrics={expression,parameters,types,solveSketch,solve,enforce,ensure,make,key,plane,local,world,validate};
  if(typeof module!=='undefined' && module.exports)module.exports=K.Parametrics;
})(typeof window!=='undefined'?window:globalThis);
