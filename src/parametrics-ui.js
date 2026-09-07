/* Parametric commands operate on the drawing transaction and undo systems. */
(function(root) {
  'use strict';
  const K=root.Kestrel, P=K.Parametrics;
  if(!P || !K.UI)throw new Error('Parametric modules must load before the application.');
  const esc=v=>String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
  const read=(f,n)=>typeof f.get==='function'?f.get(n):f[n];
  const labels={coincident:'Coincident',horizontal:'Horizontal',vertical:'Vertical',length:'Driving length',distance:'Driving distance',dx:'Horizontal distance',dy:'Vertical distance',parallel:'Parallel',perpendicular:'Perpendicular',angle:'Driving angle',equalLength:'Equal length',radius:'Driving radius',diameter:'Driving diameter',concentric:'Concentric',equalRadius:'Equal radius',tangent:'Tangent',pointOnLine:'Point on line',pointOnCircle:'Point on circle',midpoint:'Midpoint',symmetry:'Symmetric',fix:'Fix geometry'};
  const commands=[{id:'parametric-tools',label:'Parametric sketch tools',alias:['PARAMETRIC'],icon:'settings',description:'Add geometric constraints and driving dimensions to selected sketch geometry.'},{id:'parametric-parameters',label:'Named driving parameters',alias:['PARAMETERS'],icon:'settings',description:'Edit named arithmetic expressions; solve and roll back conflicting changes.'},{id:'parametric-manager',label:'Constraint manager',alias:['CONSTRAINTS'],icon:'settings',description:'Inspect, disable, remove and edit persisted sketch constraints.'},{id:'parametric-status',label:'Sketch degrees of freedom',alias:['CONSTRAINTSTATUS'],icon:'info',description:'Inspect numerical rank, residuals and remaining degrees of freedom.'},...P.types.map(type=>({id:'constrain-'+type,label:labels[type]+' constraint',alias:['GC'+type.toUpperCase()],icon:'dimension',description:'Apply '+labels[type].toLowerCase()+' to selected planar sketch geometry.'}))];
  K.UI.commands.push(...commands);
  const owned=new Set(commands.map(c=>c.id));
  const previousInstall=K.installAdvancedUI;
  K.installAdvancedUI=function(App) {
    previousInstall?.(App);
    const originalRun=App.prototype.run, originalInit=App.prototype.init;
    App.prototype.init=async function(...args) {
      const result=await originalInit.apply(this,args);
      if(!document.getElementById('parametric-tools-button')) {
        const button=document.createElement('button');button.id='parametric-tools-button';button.type='button';button.textContent='Parametric';button.title='Parametric sketch tools — select geometry first';button.addEventListener('click',()=>this.run('parametric-tools'));
        const host=document.querySelector('#ribbon-tabs, .ribbon-tabs, header');
        if(host)host.append(button);else {button.style.cssText='position:fixed;right:8px;bottom:36px;z-index:30;padding:6px 12px';document.body.append(button);}
      }
      return result;
    };
    App.prototype.run=function(id,...args) {
      if(!owned.has(id))return originalRun.call(this,id,...args);
      try {
        const app=this,doc=this.doc,store=P.ensure(doc),selected=[...doc.selection].map(id=>doc.byId.get(id)).filter(e=>e && doc.editable(e));
        const finish=()=>{app.refresh?.();app.selectionChanged?.();};
        const apply=(label,fn)=>{doc.transaction(label,fn);finish();};
        if(id==='parametric-parameters') {
          const text=Object.entries(store.parameters).map(([n,v])=>n+' = '+v).join('\n');
          return app.dialog({title:'Named driving parameters',wide:true,html:'<p>One name = expression per line. Angles in constraint values are degrees; trigonometric functions use radians. No JavaScript is evaluated.</p><textarea name="parameters" rows="12" style="width:100%;font-family:monospace">'+esc(text)+'</textarea><p>Example: width = 100<br>height = width * 0.6</p>',onSubmit(f){const definitions={};for(const line of String(read(f,'parameters')||'').split(/\r?\n/)){if(!line.trim())continue;const m=line.match(/^\s*([A-Za-z_][A-Za-z_0-9]*)\s*=\s*(.+)$/);if(!m)throw new Error('Expected name = expression: '+line);if(Object.hasOwn(definitions,m[1]))throw new Error('Duplicate parameter: '+m[1]);Object.defineProperty(definitions,m[1],{value:m[2],enumerable:true,writable:true,configurable:true});}P.parameters(definitions);apply('Edit driving parameters',()=>{P.ensure(doc).parameters=definitions;});}});
        }
        if(id==='parametric-status') {
          const r=P.solve(doc,{apply:false});
          return app.dialog({title:'Parametric sketch status',closeOnly:true,html:'<p><b>'+esc(r.converged?'Constraints satisfied':'Constraints are inconsistent')+'</b></p><p>Scalar variables: '+r.variables+'<br>Equations: '+r.equations+'<br>Estimated numerical rank: '+r.rank+'<br>Remaining degrees of freedom: '+r.degreesOfFreedom+'<br>Dependent equations: '+(r.redundantEquations||0)+'<br>Normalized residual: '+esc(r.normalizedResidual??0)+'</p><p>The reported rank is a local numerical estimate, not a proof of global solvability.</p>'});
        }
        if(id==='parametric-manager') {
          const rows=store.constraints.map(c=>'<tr><td>'+esc(c.id)+'</td><td>'+esc(labels[c.type])+'</td><td>'+esc(c.value??'—')+'</td><td>'+(c.enabled===false?'Disabled':'Enabled')+'</td></tr>').join('');
          return app.dialog({title:'Constraint manager',wide:true,html:'<table style="width:100%"><thead><tr><th>ID</th><th>Constraint</th><th>Value</th><th>State</th></tr></thead><tbody>'+rows+'</tbody></table><p>Remove or disable IDs separated by commas. Changes are undoable.</p>'+app.field('remove','Remove IDs','','text')+app.field('disable','Disabled IDs',store.constraints.filter(c=>c.enabled===false).map(c=>c.id).join(', '),'text')+'<details><summary>Advanced constraint definitions</summary><p>Point references use the JSON-encoded pair [entity ID, point index]; circle centers use "center". The entities array declares affected drawing objects.</p><textarea name="definitions" rows="14" style="width:100%;font-family:monospace">'+esc(JSON.stringify(store.constraints,null,2))+'</textarea></details>',onSubmit(f){const definitions=JSON.parse(String(read(f,'definitions')||'[]')),remove=new Set(String(read(f,'remove')||'').split(',').map(s=>s.trim()).filter(Boolean)),disabled=new Set(String(read(f,'disable')||'').split(',').map(s=>s.trim()).filter(Boolean));if(!Array.isArray(definitions))throw new Error('Constraint definitions must be an array.');apply('Edit sketch constraints',()=>{P.ensure(doc).constraints=definitions.filter(c=>!remove.has(c.id)).map(c=>({...c,enabled:!disabled.has(c.id)}));});}});
        }
        let type=id.startsWith('constrain-')?id.slice(10):'horizontal';
        const needsValue=t=>['length','distance','dx','dy','radius','diameter','angle'].includes(t);
        const typeField=id==='parametric-tools'?'<label>Constraint<select name="type">'+P.types.map(t=>'<option value="'+t+'">'+esc(labels[t])+'</option>').join('')+'</select></label>':'<input type="hidden" name="type" value="'+esc(type)+'">';
        return app.dialog({title:id==='parametric-tools'?'Parametric sketch tools':labels[type]+' constraint',html:'<p>'+selected.length+' editable object(s) selected. Constraints act in the sketch’s captured UCS plane. Use PARAMETERS for named values and CONSTRAINTS to manage existing constraints.</p>'+typeField+app.field('value','Driving value or expression',type==='angle'?'90':'100','text')+app.field('first','First point index',0,'number','min="0" step="1"')+app.field('second','Second point index',0,'number','min="0" step="1"')+'<label><input type="checkbox" name="internal"> Internal circle-circle tangency</label>',onSubmit(f){type=String(read(f,'type'));const first=Number(read(f,'first')),second=Number(read(f,'second'));if(!Number.isInteger(first)||first<0||!Number.isInteger(second)||second<0)throw new Error('Point indices must be nonnegative integers.');const options={firstPoint:first,secondPoint:second,internal:!!read(f,'internal')};if(needsValue(type))options.value=String(read(f,'value'));apply('Add '+type+' constraint',()=>{
          const output=[],point=(e,i)=>{if(!e)throw new Error('Select enough entities for this constraint.');if(e.type!=='CIRCLE' && !e.points?.[i])throw new Error('Point index is outside the selected entity.');return P.key(e.id,e.type==='CIRCLE'?'center':i);};
          if(type==='fix') {
            for(const e of selected) {
              if(e.type==='CIRCLE') {output.push(P.make(doc,'fix',[e],{}));output.push(P.make(doc,'radius',[e],{value:e.radius}));}
              else if(e.type==='LINE'||e.type==='POLYLINE')e.points.forEach((p,i)=>output.push(P.make(doc,'fix',[e],{firstPoint:i})));
              else throw new Error('Fix geometry supports lines, straight polylines and circles.');
            }
            if(!output.length)throw new Error('Select geometry to fix.');
          } else if(['pointOnLine','pointOnCircle','midpoint','symmetry'].includes(type)) {
            const count=['midpoint','symmetry'].includes(type)?3:2;if(selected.length!==count)throw new Error('Select '+count+' entities in reference order.');
            const c={id:K.uid(),type,enabled:true,entities:selected.map(e=>e.id),a:point(selected[0],first)};
            if(type==='pointOnLine'||type==='pointOnCircle')c.b=selected[1].id;
            else {c.b=point(selected[1],second);if(type==='midpoint')c.c=point(selected[2],0);else c.axis=selected[2].id;}
            output.push(c);
          } else output.push(P.make(doc,type,selected,options));
          P.ensure(doc).constraints.push(...output);
        });}});
      } catch(error) {this.fail(error);}
    };
  };
})(window);
