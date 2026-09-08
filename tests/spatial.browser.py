#!/usr/bin/env python3
"""Actual standalone browser interactions for 3D assembly and point constraints."""
from pathlib import Path
import json, os, traceback
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'tests/results';OUT.mkdir(exist_ok=True)
results=[];errors=[]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
    page=b.new_page(viewport={'width':1640,'height':1040},accept_downloads=True);page.set_default_timeout(12000)
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content((ROOT/'Kestrel-CAD.html').read_text(),wait_until='domcontentloaded');page.wait_for_function('document.documentElement.dataset.ready==="true"')
    def action(s):page.evaluate('(s)=>kestrel.run(s)',s)
    def submit(values=None):
        for k,v in (values or {}).items():
            e=page.locator('#modal [name="'+k+'"]')
            if e.evaluate('(x)=>x.type')=='checkbox':e.set_checked(bool(v))
            elif e.evaluate('(x)=>x.tagName')=='SELECT':e.select_option(str(v))
            else:e.fill(str(v))
        page.locator('#modal-submit').click();page.wait_for_function('!document.querySelector("#modal").open||!document.querySelector("#modal-error").hidden')
        assert not page.locator('#modal-error').is_visible(),page.locator('#modal-error').inner_text()
    def test(name,fn):
        before=len(errors)
        try:fn();assert len(errors)==before,errors[before:];results.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
        except Exception as e:traceback.print_exc();results.append({'name':name,'status':'failed','error':str(e)});page.evaluate('kestrel.closeDialog();kestrel.cancel(false)')
    def demo():
        page.locator('[data-ribbon="Assembly"]').click();page.locator('#ribbon [data-action="spatial-example"]').click()
        assert page.evaluate('kestrel.doc.entities.length')==2
        assert page.evaluate('kestrel.doc.spatialReport.degreesOfFreedom')==0
        assert abs(page.evaluate('kestrel.doc.entities[1].constraintFrame[14]')-35)<1e-6
        assert 'Spatial constraints' in page.locator('#inspector').inner_text()
    test('Assembly ribbon builds a genuinely constrained six-DOF slider design',demo)
    def parameters():
        action('spatial-parameters');submit({'parameters':json.dumps([{'name':'Lift','expression':'40'}])})
        assert abs(page.evaluate('kestrel.doc.entities[1].constraintFrame[14]')-50)<1e-6
        action('undo');assert abs(page.evaluate('kestrel.doc.entities[1].constraintFrame[14]')-35)<1e-6
        action('redo');assert abs(page.evaluate('kestrel.doc.entities[1].constraintFrame[14]')-50)<1e-6
    test('3D parameter dialog moves a rigid body and undo redo restores both graph and geometry',parameters)
    def report():
        action('spatial-report');assert '0 remaining DOF' in page.locator('#modal').inner_text();assert 'global satisfiability' in page.locator('#modal').inner_text();page.evaluate('kestrel.closeDialog()')
    test('3DDOF reports actual local rank rather than a fixed success message',report)
    def suppress():
        action('spatial-manage');submit({'suppress2':True});action('spatial-report');assert '1 remaining DOF' in page.locator('#modal').inner_text();page.evaluate('kestrel.closeDialog()');action('undo')
    test('Suppressing the axial dimension releases exactly one slider freedom',suppress)
    def cycle():
        snap=page.evaluate('kestrel.doc.snapshot()');action('spatial-parameters');page.locator('[name="parameters"]').fill('[{"name":"Lift","expression":"Other"},{"name":"Other","expression":"Lift"}]');page.locator('#modal-submit').click();page.wait_for_function('!document.querySelector("#modal-error").hidden');assert 'cycle' in page.locator('#modal-error').inner_text().lower();assert page.evaluate('kestrel.doc.snapshot()')==snap;page.evaluate('kestrel.closeDialog()')
    test('Unsafe cyclic parameter edit rolls back without changing body geometry',cycle)
    def save():
        with page.expect_download() as dl:action('save')
        data=json.loads(Path(dl.value.path()).read_text());assert len(data['production']['spatial']['constraints'])==3;assert data['entities'][1]['constraintFrame'][14]>49.999
        page.evaluate('(d)=>kestrel.addDocument(Kestrel.Drawing.from(d))',data)
        assert page.evaluate('Kestrel.SpatialConstraints.solve(kestrel.doc,{apply:false}).degreesOfFreedom')==0
    test('Native browser download and reopening retain the assembly frames and equations',save)
    def units():
        action('units');submit({'units':'in','convert':True});assert abs(page.evaluate('kestrel.doc.entities[1].constraintFrame[14]')-50/25.4)<1e-6;assert page.evaluate('kestrel.doc.spatialReport.degreesOfFreedom')==0;action('undo')
    test('Normal units dialog converts all rigid datums and dimensional units coherently',units)
    def clipboard():
        page.evaluate('kestrel.doc.selection=new Set(kestrel.doc.entities.map(e=>e.id));kestrel.selectionChanged()');action('copy-clipboard');action('new');action('paste')
        page.wait_for_function('kestrel.tool?.id==="paste"');page.evaluate('kestrel.acceptPoint([100,0,0])')
        assert page.evaluate('kestrel.doc.entities.length')==2
        assert page.evaluate('kestrel.doc.production.spatial.constraints.length')==3
        assert page.evaluate('kestrel.doc.spatialReport.degreesOfFreedom')==0
    test('Normal clipboard retains a complete 3D assembly and its driving dimensions',clipboard)
    def freepoint():
        action('new');page.evaluate("const d=kestrel.doc;d.transaction('Point',()=>{let e=d.add('POINT',{position:[1,2,3]});d.selection=new Set([e.id]);});kestrel.selectionChanged()")
        entity=page.evaluate('kestrel.doc.entities[0].id');action('spatial-add');submit({'kind':'coincident','aEntity':entity,'bEntity':'world','bLocal':'10,20,30'})
        actual=page.evaluate('kestrel.doc.entities[0].position');assert all(abs(a-b)<1e-6 for a,b in zip(actual,[10,20,30]));assert page.evaluate('kestrel.doc.spatialReport.degreesOfFreedom')==0
    test('3DCONSTRAINT form solves actual XYZ coordinates through UI',freepoint)
    def conflict():
        snapshot=page.evaluate('kestrel.doc.snapshot()');action('spatial-distance');page.locator('#modal [name="value"]').fill('100');page.locator('#modal [name="bLocal"]').fill('10,20,30');page.locator('#modal-submit').click();page.wait_for_function('!document.querySelector("#modal-error").hidden');assert 'rolled back' in page.locator('#modal-error').inner_text();assert page.evaluate('kestrel.doc.snapshot()')==snapshot
        page.locator('#modal [name="value"]').fill('0');page.locator('#modal-submit').click();page.wait_for_function('!document.querySelector("#modal").open')
    test('Conflicting relation is rejected and can be corrected without discarding the dialog',conflict)
    def stale():
        action('spatial-add');page.evaluate("kestrel.doc.transaction('Other edit',()=>kestrel.doc.add('POINT',{position:[99,99,99]}))");page.locator('#modal-submit').click();page.wait_for_function('!document.querySelector("#modal-error").hidden');assert 'changed' in page.locator('#modal-error').inner_text();page.evaluate('kestrel.closeDialog()')
    test('Stale 3D dialog cannot overwrite a newer drawing edit',stale)
    def delete():
        count=page.evaluate('kestrel.doc.production.spatial.constraints.length');action('spatial-manage');submit({'delete0':True});assert page.evaluate('kestrel.doc.production.spatial.constraints.length')==count-1;action('undo');assert page.evaluate('kestrel.doc.production.spatial.constraints.length')==count
    test('Constraint manager deletion participates in normal undo history',delete)
    def disabling():
        action('spatial-manage');submit({'enabled':False});assert not page.evaluate('kestrel.doc.production.spatial.enabled');action('spatial-manage');submit({'enabled':True});assert page.evaluate('kestrel.doc.production.spatial.enabled')
    test('System-wide enable switch preserves stored relationships',disabling)
    def fix():
        action('new');page.evaluate("const d=kestrel.doc;d.transaction('Body',()=>{const e=d.add(Kestrel.Geo.box([0,0,0],10,10,10));d.selection=new Set([e.id]);});kestrel.selectionChanged()")
        action('spatial-fix');assert page.evaluate('kestrel.doc.production.spatial.constraints[0].type')=='fixed-entity'
        page.evaluate("kestrel.doc.transaction('Move',()=>kestrel.doc.transform([...kestrel.doc.selection],Kestrel.Math.M.translation(30,40,50)))")
        assert page.evaluate('kestrel.doc.entities[0].vertices[0]')==[0,0,0]
    test('3DFIX prevents an ordinary transformation from moving a constrained body',fix)
    action('spatial-example');page.locator('[data-ribbon="Assembly"]').click();page.screenshot(path=str(OUT/'spatial-assembly.png'));b.close()
failed=sum(t['status']=='failed' for t in results)
(OUT/'spatial-browser-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'javascript_errors':errors,'tests':results},indent=2))
print('RESULT',len(results)-failed,'passed;',failed,'failed;',errors);raise SystemExit(bool(failed or errors))
