#!/usr/bin/env python3
"""Actual standalone editor workflows for bounded joints and position drivers."""
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
    def setup(kind='slider'):
        action('new')
        page.evaluate("""kind=>{const K=Kestrel,C=K.SpatialConstraints,d=kestrel.doc;d.transaction('Fixture',()=>{const e=d.add(K.Geo.box([0,0,0],10,20,30));d.selection=new Set([e.id]);});kestrel.selectionChanged();}""",kind)
        action('spatial-mate');submit({'kind':kind})
    def limits():
        setup();page.locator('[data-ribbon="Assembly"]').click();page.locator('#ribbon [data-action="spatial-joints"]').click()
        submit({'limit0':True,'min0':'5','max0':'30'})
        assert abs(page.evaluate('Kestrel.SpatialConstraints.solve(kestrel.doc,{apply:false}).joints[0].coordinate')-5)<1e-6
        assert page.evaluate('kestrel.doc.production.spatial.constraints[0].limits.min')=='5'
    test('Assembly ribbon authors limits and moves a below-minimum slider into range',limits)
    def drive():
        action('DRIVEJOINT');submit({'drive0':True,'position0':'20'})
        assert abs(page.evaluate('kestrel.doc.entities[0].constraintFrame[14]')-20)<1e-6
        assert page.evaluate('kestrel.doc.spatialReport.degreesOfFreedom')==0
        action('undo');assert abs(page.evaluate('kestrel.doc.entities[0].constraintFrame[14]')-5)<1e-6
        action('redo');assert abs(page.evaluate('kestrel.doc.entities[0].constraintFrame[14]')-20)<1e-6
    test('DRIVEJOINT changes actual rigid geometry with atomic undo redo',drive)
    def conflict():
        page.evaluate('kestrel.autosave()');snap=page.evaluate('kestrel.doc.snapshot()');history=page.evaluate('kestrel.doc.undoStack.length')
        action('JOINTLIMITS');page.locator('[name="position0"]').fill('100');page.locator('#modal-submit').click();page.wait_for_function('!document.querySelector("#modal-error").hidden')
        assert 'outside' in page.locator('#modal-error').inner_text();assert page.evaluate('kestrel.doc.snapshot()')==snap;assert page.evaluate('kestrel.doc.undoStack.length')==history
        page.locator('[name="position0"]').fill('25');page.locator('#modal-submit').click();page.wait_for_function('!document.querySelector("#modal").open')
    test('Out-of-range drive rejects and can be corrected in the same dialog',conflict)
    def disabled():
        action('JOINTS');submit({'drive0':False});assert page.evaluate('kestrel.doc.spatialReport.degreesOfFreedom')==1
        page.evaluate('kestrel.doc.transaction("Move",()=>kestrel.doc.transform([kestrel.doc.entities[0].id],Kestrel.Math.M.translation(0,0,100)))')
        assert abs(page.evaluate('kestrel.doc.entities[0].constraintFrame[14]')-30)<1e-6
        action('spatial-report');text=page.locator('#modal').inner_text();assert '1 remaining DOF' in text and 'unilateral' in text and 'atMaximum' in text;page.evaluate('kestrel.closeDialog()')
    test('Disabling the driver restores travel while enabled stops still enforce the bound',disabled)
    def native():
        with page.expect_download() as dl:action('save')
        data=json.loads(Path(dl.value.path()).read_text());assert data['production']['spatial']['constraints'][0]['limits']['max']=='30'
        page.evaluate('(d)=>kestrel.addDocument(Kestrel.Drawing.from(d))',data);action('JOINTLIMITS');assert page.locator('[name="max0"]').input_value()=='30';page.evaluate('kestrel.closeDialog()')
    test('Native download and reopen retain editable joint travel settings',native)
    def stale():
        action('JOINTLIMITS');page.evaluate('kestrel.doc.transaction("Other edit",()=>kestrel.doc.add("POINT",{position:[2,3,4]}))');page.locator('#modal-submit').click();page.wait_for_function('!document.querySelector("#modal-error").hidden');assert 'changed' in page.locator('#modal-error').inner_text();page.evaluate('kestrel.closeDialog()')
    test('Stale joint form cannot overwrite newer drawing edits',stale)
    def hinge():
        setup('hinge');action('JOINTLIMITS');submit({'limit0':True,'min0':'-70','max0':'70','drive0':True,'position0':'-45'})
        assert abs(page.evaluate('Kestrel.SpatialConstraints.solve(kestrel.doc,{apply:false}).joints[0].coordinate')+45)<1e-6
        action('spatial-parameters');submit({'parameters':'[{"name":"Angle","expression":"35"}]'});action('JOINTLIMITS');submit({'position0':'Angle'})
        assert abs(page.evaluate('Kestrel.SpatialConstraints.solve(kestrel.doc,{apply:false}).joints[0].coordinate')-35)<1e-6
    test('Hinge UI supports signed angles and named expressions',hinge)
    def units():
        action('units');submit({'units':'in','convert':True});assert abs(page.evaluate('Kestrel.SpatialConstraints.solve(kestrel.doc,{apply:false}).joints[0].coordinate')-35)<1e-6
    test('Unit conversion does not rescale angular driver values',units)
    def single_bound():
        setup();action('JOINTLIMITS');submit({'limit0':True,'min0':'','max0':'10'})
        assert page.evaluate('kestrel.doc.spatialReport.inequalities')==1
        action('JOINTLIMITS');submit({'limit0':False});assert page.evaluate('kestrel.doc.production.spatial.constraints[0].limits.max')=='10'
    test('Single-sided and disabled limits preserve their authored expressions',single_bound)
    page.locator('[data-ribbon="Assembly"]').click();action('JOINTLIMITS');page.screenshot(path=str(OUT/'joint-limits.png'));b.close()
failed=sum(t['status']=='failed' for t in results)
(OUT/'joint-limits-browser-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'javascript_errors':errors,'tests':results},indent=2))
print('RESULT',len(results)-failed,'passed;',failed,'failed;',errors);raise SystemExit(bool(failed or errors))
