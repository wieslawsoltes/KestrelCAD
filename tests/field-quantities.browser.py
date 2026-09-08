#!/usr/bin/env python3
"""Native geometry fixture with actual field and schedule UI, history and downloads."""
from pathlib import Path
import json, os, sys, traceback
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'tests/results';OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'tools'));import kernel
body=kernel.execute({'op':'box','params':{'width':20,'depth':30,'height':10}})
tests=[];errors=[]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH',p.chromium.executable_path),headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1700,'height':1100},accept_downloads=True);page.set_default_timeout(20000)
    page.on('pageerror',lambda e:errors.append(str(e)))
    url=os.environ.get('KESTREL_TEST_URL');mode=os.environ.get('KESTREL_TEST_MODE','file')
    if url:page.goto(url,wait_until='domcontentloaded');loading='served URL'
    elif mode=='dom':page.set_content((ROOT/'Kestrel-CAD.html').read_text(),wait_until='domcontentloaded');loading='standalone DOM diagnostic; no file or HTTP navigation'
    elif mode=='file':page.goto((ROOT/'Kestrel-CAD.html').as_uri(),wait_until='domcontentloaded');loading='standalone file navigation'
    else:raise ValueError('Unknown KESTREL_TEST_MODE')
    page.wait_for_function('document.documentElement.dataset.ready==="true"')
    def ev(s,arg=None):return page.evaluate(s,arg)
    def action(name):ev('(name)=>kestrel.run(name)',name)
    def reset():
        ev('kestrel.closeDialog();kestrel.cancel(false);kestrel.docs=[kestrel.doc]');action('new')
        ev('result=>{kestrel.doc.transaction("Native fixture",()=>{kestrel.doc.units="mm";kestrel.doc.add({...Kestrel.Kernel.body(result),id:"body"});});kestrel.doc.selection=new Set(["body"]);kestrel.selectionChanged();}',body)
    def submit():
        page.locator('#modal-submit').click();page.wait_for_function('!document.querySelector("#modal").open || !document.querySelector("#modal-error").hidden')
        assert not page.locator('#modal-error').is_visible(),page.locator('#modal-error').inner_text()
    def test(name,fn):
        n=len(errors)
        try:reset();fn();assert len(errors)==n,errors[n:];tests.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
        except Exception as e:traceback.print_exc();tests.append({'name':name,'status':'failed','error':str(e)})
    def field():
        action('FIELD');page.locator('[name="property"]').select_option('volume');page.locator('[name="units"]').select_option('cm');page.locator('[name="template"]').fill('Volume {{Value}} cm3');submit()
        assert ev('kestrel.doc.entities.find(e=>e.type==="MTEXT").text')=='Volume 6.00 cm3'
    test('FIELD exposes native volume and cubic physical output units',field)
    def area():
        action('FIELD');page.locator('[name="property"]').select_option('surfaceArea');page.locator('[name="units"]').select_option('cm');submit()
        assert ev('kestrel.doc.entities.find(e=>e.type==="MTEXT").text')=='22.00'
    test('FIELD authors native surface area with squared units',area)
    def schedule():
        action('FIELDTABLE');cols=json.loads(page.locator('[name="columns"]').input_value());assert [c['property'] for c in cols][-2:]==['volume','surfaceArea'];submit()
        assert ev('kestrel.doc.entities.find(e=>e.type==="TABLE").cells[1].slice(-2)')==['6000','2200']
    test('native-solid selection gets quantity columns by default',schedule)
    def history():
        field();ev('kestrel.doc.transaction("Scale source",()=>kestrel.doc.transform(["body"],Kestrel.Math.M.scale(2)))');assert ev('kestrel.doc.entities.find(e=>e.type==="MTEXT").text')=='Volume 48.00 cm3';action('undo');assert ev('kestrel.doc.entities.find(e=>e.type==="MTEXT").text')=='Volume 6.00 cm3';action('redo');assert ev('kestrel.doc.entities.find(e=>e.type==="MTEXT").text')=='Volume 48.00 cm3'
    test('placed native quantity updates with source undo and redo',history)
    def unresolved():
        area();ev('kestrel.doc.transaction("Nonuniform source",()=>kestrel.doc.transform(["body"],Kestrel.Math.M.scale(2,3,4)))');action('FIELDINFO');assert 'native recomputation' in page.locator('#modal-body').inner_text();assert ev('kestrel.doc.entities.find(e=>e.type==="MTEXT").text')=='####'
    test('unsupported area placement shows explicit diagnostic',unresolved)
    def save():
        field()
        with page.expect_download() as dl:action('save')
        data=json.loads(Path(dl.value.path()).read_text());ev('(data)=>kestrel.addDocument(Kestrel.Drawing.from(data))',data)
        assert ev('kestrel.doc.entities.find(e=>e.type==="MTEXT").text')=='Volume 6.00 cm3';assert ev('kestrel.doc.byId.get("body").solid.brep')==body['brep']
    test('native project download preserves quantity links and authoritative geometry',save)
    browser.close()
failed=sum(t['status']=='failed' for t in tests);(OUT/'field-quantities-browser-results.json').write_text(json.dumps({'passed':len(tests)-failed,'failed':failed,'javascript_errors':errors,'loading':loading,'tests':tests},indent=2)+'\n');sys.exit(bool(failed or errors))
