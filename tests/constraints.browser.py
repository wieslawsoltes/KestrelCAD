#!/usr/bin/env python3
"""Parametric sketch controls exercised with real browser actions and native geometry."""
from pathlib import Path
import json,os,traceback
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'tests/results';OUT.mkdir(exist_ok=True)
results=[];errors=[]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1600,'height':1000},accept_downloads=True);page.on('pageerror',lambda e:errors.append(str(e)));page.set_default_timeout(10000)
    if os.environ.get('KESTREL_TEST_URL'):page.goto(os.environ['KESTREL_TEST_URL'],wait_until='domcontentloaded')
    else:page.set_content((ROOT/'Kestrel-CAD.html').read_text(),wait_until='domcontentloaded')
    page.wait_for_function('document.documentElement.dataset.ready==="true"')
    def test(name,fn):
        before=len(errors)
        try:fn();assert len(errors)==before,errors[before:];results.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
        except Exception as e:traceback.print_exc();results.append({'name':name,'status':'failed','error':str(e)});page.evaluate('kestrel.closeDialog();kestrel.cancel(false)')
    def action(x):page.evaluate('(id)=>kestrel.run(id)',x)
    def fill(fields):
        for key,value in fields.items():
            el=page.locator('#modal [name="'+key+'"]')
            if isinstance(value,bool):el.set_checked(value)
            elif el.evaluate('(e)=>e.tagName')=='SELECT':el.select_option(str(value))
            else:el.fill(str(value))
    def submit(fields={}):
        fill(fields);page.locator('#modal-submit').click();page.wait_for_timeout(60);assert not page.locator('#modal-error').is_visible(),page.locator('#modal-error').inner_text()
    def near(expr,x):v=page.evaluate(expr);assert abs(v-x)<1e-4,(expr,v,x)
    def demo():
        page.locator('[data-ribbon="Parametric"]').click();page.locator('#ribbon [data-action="constraint-demo"]').click();near('kestrel.doc.entities[0].points[1][0]',100);assert page.evaluate('kestrel.doc.constraintReport.degreesOfFreedom')==0
    test('Parametric ribbon creates a genuinely constrained example',demo)
    def resize():
        page.locator('#ribbon [data-action="parameter-edit"]').click();submit({'expression0':'160'});near('kestrel.doc.entities[0].points[1][0]',160);near('kestrel.doc.entities[0].points[2][1]',96)
    test('parameter dialog resizes geometry and evaluates dependent expressions',resize)
    def undo():action('undo');near('kestrel.doc.entities[0].points[1][0]',100);action('redo');near('kestrel.doc.entities[0].points[1][0]',160)
    test('undo and redo retain equations and matching geometry',undo)
    def conflict():
        action('constraint-manage');fill({'value5':'20'});page.locator('#modal-submit').click();page.wait_for_timeout(60)
        # Width is replaced by 20; dependent Height still follows Width parameter 160.
        assert not page.locator('#modal-error').is_visible();near('kestrel.doc.entities[0].points[1][0]',20);action('undo')
        action('parameter-edit');fill({'expression0':'Height'});page.locator('#modal-submit').click();assert 'cycle' in page.locator('#modal-error').inner_text();near('kestrel.doc.entities[0].points[1][0]',160);page.evaluate('kestrel.closeDialog()')
    test('constraint expression editing works and cyclic parameters roll back',conflict)
    def suppress():
        action('constraint-manage');submit({'suppress5':True});assert page.evaluate('kestrel.doc.constraintReport.degreesOfFreedom')==1;action('undo')
    test('constraint manager suppresses a dimension and restores it with undo',suppress)
    def toggle():action('constraint-toggle');assert not page.evaluate('kestrel.doc.production.parametric.enabled');action('constraint-toggle');assert page.evaluate('kestrel.doc.production.parametric.enabled')
    test('constraint enable switch retains and reenables the sketch equations',toggle)
    def report():action('constraint-solve');assert 'fully-constrained' in page.locator('#modal').inner_text();submit()
    test('solver report displays actual local degrees of freedom',report)
    def persist():
        with page.expect_download() as dl:action('save')
        data=json.loads(Path(dl.value.path()).read_text());assert data['production']['parametric']['parameters'][0]['expression']=='160';assert len(data['production']['parametric']['constraints'])==7
    test('project download contains solved geometry, parameters and constraints',persist)
    def units():action('units');submit({'units':'cm','convert':True});near('kestrel.doc.entities[0].points[1][0]',16);assert page.evaluate('kestrel.doc.production.parametric.units')=='mm';action('undo')
    test('unit dialog physically converts a constrained drawing without changing its design',units)
    def add():
        action('constraint-clear');submit();page.evaluate('kestrel.doc.selection=new Set([kestrel.doc.entities[0].id]);kestrel.selectionChanged()');action('gc-horizontal');submit({'aSegment':'0'});assert len(page.evaluate('kestrel.doc.production.parametric.constraints'))==1
    test('geometric constraint form creates a horizontal segment constraint',add)
    def delete():
        action('constraint-manage');submit({'delete0':True});assert len(page.evaluate('kestrel.doc.production.parametric.constraints'))==0;action('undo');assert len(page.evaluate('kestrel.doc.production.parametric.constraints'))==1
    test('constraint manager deletion is atomic and undoable',delete)
    def retry():
        # Add a conflicting dimension to the fully constrained example.
        page.evaluate('kestrel.closeDialog()');action('constraint-demo');page.evaluate('kestrel.doc.selection=new Set([kestrel.doc.entities[0].id]);kestrel.selectionChanged()')
        action('constraint-add');fill({'type':'distance-x','aPoint':'0','bPoint':'1','value':'200'});page.locator('#modal-submit').click();assert 'rolled back' in page.locator('#modal-error').inner_text()
        # Correct the same open form: rollback replaced the underlying drawing snapshot.
        submit({'value':'100'});assert len(page.evaluate('kestrel.doc.production.parametric.constraints'))==8
    test('failed constraint creation can be corrected and resubmitted without losing the edit',retry)
    def clipboard():
        page.evaluate('kestrel.doc.selection=new Set([kestrel.doc.entities[0].id]);kestrel.selectionChanged();kestrel.copyClipboard()');action('new');action('paste')
        page.locator('#command-input').fill('0,0');page.locator('#command-input').press('Enter');page.wait_for_timeout(80)
        assert len(page.evaluate('kestrel.doc.production.parametric.constraints'))==8;near('kestrel.doc.entities[0].points[1][0]-kestrel.doc.entities[0].points[0][0]',100)
    test('normal clipboard UI transfers matching equations and parameters into a new drawing',clipboard)
    action('constraint-demo');page.evaluate('kestrel.setRibbon("Parametric");kestrel.fit(false)');page.screenshot(path=str(OUT/'parametric-sketch.png'));browser.close()
failed=sum(t['status']=='failed' for t in results);(OUT/'constraints-browser-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'javascript_errors':errors,'tests':results},indent=2)+'\n');print(f'Constraint browser: {len(results)-failed}/{len(results)} passed; JS errors: {errors}');raise SystemExit(bool(failed or errors))
