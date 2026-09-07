#!/usr/bin/env python3
"""Idempotent, checked integration of the parametric feature modules."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent.parent
INDEX=ROOT/'index.html'
text=INDEX.read_text()
core=['parametrics.js','parametrics-integration.js']
for name in core:
    if 'src/'+name in text:
        continue
    text,count=re.subn(r'(?=<script\s+src=[\"\']src/(?:kernel|renderer)\.js)',lambda _:f'<script src="src/{name}"></script>\n',text,count=1)
    if count!=1:
        raise RuntimeError('Could not identify the browser core-module anchor')
if 'src/parametrics-ui.js' not in text:
    text,count=re.subn(r'(?=<script\s+src=[\"\']src/app\.js)', '<script src="src/parametrics-ui.js"></script>\n',text,count=1)
    if count!=1:
        raise RuntimeError('Could not identify the browser application anchor')
INDEX.write_text(text)

# The existing extension hook lets this feature compose with native-solid UI.
app=(ROOT/'src/app.js').read_text()
if 'installAdvancedUI' not in app:
    raise RuntimeError('The application extension hook is missing')

for name in ['src/io-worker.js','tools/build.py']:
    path=ROOT/name
    text=path.read_text()
    if 'parametrics' in text:
        continue
    for suffix in ['.js','']:
        pattern=r'([\"\'])production'+re.escape(suffix)+r'\1'
        text,count=re.subn(pattern,lambda m:m[0]+', '+repr('parametrics'+suffix)+', '+repr('parametrics-integration'+suffix),text,count=1)
        if count:
            break
    else:
        raise RuntimeError('Could not identify the worker module anchor in '+name)
    path.write_text(text)

integration=ROOT/'src/parametrics-integration.js'
text=integration.read_text()
anchor='''      edit();
      K.Parametrics.enforce(this);'''
replacement='''      // A solver must not move protected geometry indirectly through parameters.
      const active = this.production?.parametrics?.constraints?.filter(c => c.enabled !== false) || [];
      const affected = new Set(active.flatMap(c => c.entities || []));
      const coordinates = entity => entity.center ? [...entity.center, entity.radius] : (entity.points || []).flat();
      const protectedGeometry = this.entities.filter(e => affected.has(e.id) && !this.editable(e)).map(e => ({id:e.id, values:coordinates(e)}));
      edit();
      K.Parametrics.enforce(this);
      for (const prior of protectedGeometry) {
        const entity = this.entities.find(e => e.id === prior.id);
        const values = entity ? coordinates(entity) : [];
        if (values.length !== prior.values.length || values.some((v,i) => Math.abs(v-prior.values[i]) > Math.max(1e-7,Math.abs(prior.values[i])*Number.EPSILON*16))) {
          throw new Error('Constraints would modify locked or hidden geometry; edit rolled back.');
        }
      }'''
if 'protectedGeometry' not in text:
    if anchor not in text:
        raise RuntimeError('Unexpected transaction integration source')
    text=text.replace(anchor,replacement,1)
    integration.write_text(text)

ui=ROOT/'src/parametrics-ui.js'
text=ui.read_text()
anchor='const result=await originalInit.apply(this,args);'
if 'K.Parametrics.application=this;' not in text:
    if anchor not in text:
        raise RuntimeError('Unexpected parametric UI initialization source')
    ui.write_text(text.replace(anchor,anchor+'\n      K.Parametrics.application=this;',1))

verify=ROOT/'tools/verify.py'
text=verify.read_text()
# The core runner already discovers constraints.test.js. Add real browser coverage.
if 'constraints.browser.py' not in text:
    for quote in ["'",'"']:
        anchor=quote+'advanced.browser.py'+quote
        if anchor in text:
            text=text.replace(anchor,anchor+', '+quote+'constraints.browser.py'+quote,1)
            break
    else:
        raise RuntimeError('Could not identify optional browser-suite inventory')
    verify.write_text(text)
print('Parametric browser/worker modules, transaction guards and CI coverage integrated.')
