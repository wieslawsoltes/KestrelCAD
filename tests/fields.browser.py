#!/usr/bin/env python3
"""Real native-field dialogs, history, renderer, clipboard and worker downloads."""
from pathlib import Path
import json, os, traceback
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'tests/results';OUT.mkdir(exist_ok=True)
results=[];errors=[]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1700,'height':1100},accept_downloads=True);page.set_default_timeout(15000)
    page.on('pageerror',lambda error:errors.append(str(error)))
    if os.environ.get('KESTREL_TEST_URL'):page.goto(os.environ['KESTREL_TEST_URL'],wait_until='domcontentloaded')
    else:page.set_content((ROOT/'Kestrel-CAD.html').read_text(),wait_until='domcontentloaded')
    page.wait_for_function('document.documentElement.dataset.ready==="true"')
    def ev(script):return page.evaluate(script)
    def action(command):page.evaluate('(id)=>kestrel.run(id)',command)
    def close():ev('kestrel.closeDialog();kestrel.cancel(false)')
    def test(name,fn):
        before=len(errors)
        try:fn();assert len(errors)==before,errors[before:];results.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
        except Exception as error:traceback.print_exc();results.append({'name':name,'status':'failed','error':str(error)});close()
    def fill(values):
        for key,value in values.items():
            el=page.locator('#modal [name="'+key+'"]')
            if isinstance(value,bool):el.set_checked(value)
            elif el.evaluate('(e)=>e.tagName')=='SELECT':el.select_option(str(value))
            else:el.fill(str(value))
    def submit(values=None):
        fill(values or {});page.locator('#modal-submit').click();page.wait_for_timeout(120)
        assert not page.locator('#modal-error').is_visible(),page.locator('#modal-error').inner_text()
    def setup():
        close();action('new');ev('kestrel.doc.transaction("Fixture",()=>{kestrel.doc.add("LINE",{id:"lineA",points:[[0,0,0],[30,40,0]]});kestrel.doc.add("CIRCLE",{id:"circleA",center:[100,50,0],radius:10});});kestrel.doc.selection=new Set(["lineA"]);kestrel.selectionChanged()')
    def create():
        setup();page.locator('[data-ribbon="Text"]').click();page.locator('#ribbon [data-action="field"]').click()
        fill({'template':'Length {{Value}} mm','position':'0,80,0'});page.wait_for_timeout(250);assert '50.00' in page.locator('#field-preview').inner_text();submit()
        assert ev('kestrel.doc.entities.at(-1).text')=='Length 50.00 mm'
        assert ev('kestrel.doc.entities.at(-1).position')==[0,80,0]
        assert ev('kestrel.doc.entities.at(-1).fieldBindings.length')==1
    test('Text ribbon creates an actual associative MTEXT at exact coordinates',create)
    def modify():
        ev('kestrel.doc.transaction("Change source",()=>{kestrel.doc.byId.get("lineA").points[1]=[60,80,0]})')
        assert ev('kestrel.doc.entities.at(-1).text')=='Length 100.00 mm';action('undo');assert ev('kestrel.doc.entities.at(-1).text')=='Length 50.00 mm';action('redo')
    test('source geometry and displayed annotation update in one undo redo step',modify)
    def render():
        action('fit');page.wait_for_timeout(300)
        assert ev('kestrel.doc.geometry(kestrel.doc.entities.at(-1)).texts[0].composition.runs.map(r=>r.text).join("").includes("100.00")')
        assert ev('kestrel.renderer.texts.some(r=>r.t.composition)')
        page.screenshot(path=str(OUT/'annotation-fields.png'))
    test('production renderer receives freshly composed field output',render)
    def edit():
        ev('kestrel.doc.selection=new Set([kestrel.doc.entities.at(-1).id]);kestrel.selectionChanged()');action('FIELD')
        assert page.locator('[name="template"]').input_value()=='Length {{Value}} mm'
        submit({'units':'cm','precision':3,'template':'Length {{Value}} cm'});assert ev('kestrel.doc.entities.at(-1).text')=='Length 10.000 cm'
    test('FIELD edits the authoritative template and units rather than a display cache',edit)
    def double_editor():
        ev('kestrel.textDialog(kestrel.doc.entities.at(-1))');assert page.locator('#modal-title').inner_text()=='Edit annotation field';close()
    test('normal text-edit entry routes field-controlled MTEXT to the field editor',double_editor)
    def stale():
        action('FIELD');ev('kestrel.doc.transaction("Other edit",()=>kestrel.doc.add("POINT",{position:[2,2,0]}))');page.locator('#modal-submit').click();page.wait_for_timeout(100);assert 'changed' in page.locator('#modal-error').inner_text().lower();close();action('undo')
    test('stale authoring dialog cannot overwrite newer drawing edits',stale)
    def formula():
        action('FIELD');sources=[{'name':'A','kind':'object','entity':'lineA','property':'length'},{'name':'Price','kind':'literal','value':2.5}]
        submit({'kind':'formula','sources':json.dumps(sources),'expression':'A * Price','template':'Cost {{Result}}','precision':2})
        assert ev('kestrel.doc.entities.at(-1).text')=='Cost 250.00'
    test('formula form uses named measurements and numeric constants',formula)
    def malicious():
        action('FIELD');fill({'expression':'globalThis.fieldPwned = 1'});page.locator('#modal-submit').click();page.wait_for_timeout(120);assert page.locator('#modal-error').is_visible();assert ev('globalThis.fieldPwned===undefined');close()
    test('invalid expressions fail without running JavaScript',malicious)
    def script_text():
        action('FIELD');fill({'kind':'literal','literal':json.dumps('<img src=x onerror=alert(1)>'),'template':'{{Value}}'});page.wait_for_timeout(250)
        assert page.locator('#field-preview img').count()==0;assert '<img' in page.locator('#field-preview').inner_text();close()
    test('live preview renders external strings as literal text instead of HTML',script_text)
    def props():
        action('DWGPROPS');submit({'name':'Fabrication sheet','Title':'Pump assembly','Author':'Designer','custom':'[{"name":"Revision","value":3}]'})
        action('FIELD');submit({'kind':'property','key':'Title','template':'{{Value}}'})
        assert ev('kestrel.doc.entities.at(-1).text')=='Pump assembly'
        action('DWGPROPS');submit({'Title':'Revised pump'});assert ev('kestrel.doc.entities.at(-1).text')=='Revised pump'
    test('drawing property dialog drives title-block annotations transactionally',props)
    def native():
        with page.expect_download() as download:action('save')
        data=json.loads(Path(download.value.path()).read_text());assert data['entities'][-1]['fieldBindings'];assert data['production']['drawingProperties']
        data['entities'][-1]['text']='obsolete cache'
        page.evaluate('(d)=>kestrel.addDocument(Kestrel.Drawing.from(d))',data)
        assert ev('kestrel.doc.entities.at(-1).text')=='Revised pump'
    test('actual native save and reopen recompute definitions and retain drawing metadata',native)
    def tables():
        ev('kestrel.doc.selection=new Set(["lineA","circleA"]);kestrel.selectionChanged()');page.locator('[data-ribbon="Productivity"]').click();page.locator('#ribbon [data-action="field-table"]').click()
        submit({'columns':'[{"label":"Object","property":"type"},{"label":"Length","property":"length"}]','position':'0,-20,0'})
        assert ev('kestrel.doc.entities.at(-1).cells[1][1]')=='100'
        ev('kestrel.doc.transaction("Source",()=>{kestrel.doc.byId.get("lineA").points[1]=[0,20,0]})')
        assert ev('kestrel.doc.entities.at(-1).cells[1][1]')=='20'
    test('linked schedule ribbon creates and refreshes stable cells',tables)
    def table_formula():
        ev('kestrel.doc.selection=new Set([kestrel.doc.entities.at(-1).id]);kestrel.selectionChanged()');action('FIELD')
        tid=ev('kestrel.doc.entities.at(-1).id')
        submit({'kind':'formula','sources':json.dumps([{'name':'Length','kind':'field','entity':tid,'target':'cell:1:1'}]),'expression':'Length * 2','target':'cell:0:1','template':'Double {{Result}}','precision':1,'trimZeros':False})
        assert ev('kestrel.doc.entities.at(-1).cells[0][1]')=='Double 40.0', ev('kestrel.doc.entities.at(-1)')
    test('table headers can contain formulas referencing typed cell fields',table_formula)
    def reports():
        ev('kestrel.doc.transaction("Erase source",()=>kestrel.doc.remove(["lineA"]))');action('FIELDINFO')
        assert 'unresolved' in page.locator('#modal-body').inner_text();assert 'missing' in page.locator('#modal-body').inner_text();close();action('undo')
        assert ev('kestrel.doc.entities.at(-1).cells[1][1]')=='20'
    test('missing dependencies produce visible diagnostics and undo restores them',reports)
    def worker():
        result=ev('kestrel.io("write-dxf",kestrel.doc.serialize())')
        assert 'Double 40.0' in result and 'Revised pump' in result
        assert 'fieldBindings' not in result
        (OUT/'fields-browser.dxf').write_text(result)
        report=ev('(async()=>{const d=await kestrel.io("write-dxf",kestrel.doc.serialize());return await kestrel.io("parse-dxf",d,"fields.dxf")})()')
        assert any(e.get('text')=='Double 40.0' for e in report['data']['entities'])
    test('real exchange worker writes and rereads evaluated annotation and table values',worker)
    def copy_full():
        setup();action('FIELD');submit({'template':'L={{Value}}'});ev('kestrel.doc.selection=new Set(["lineA",kestrel.doc.entities.at(-1).id]);kestrel.selectionChanged()');action('copy-clipboard');action('new');action('paste');ev('kestrel.acceptPoint([0,0,0])')
        assert ev('kestrel.doc.entities.length')==2
        assert ev('kestrel.doc.entities[1].fieldBindings[0].sources[0].entity===kestrel.doc.entities[0].id')
        ev('kestrel.doc.transaction("Resize",()=>{kestrel.doc.entities[0].points[1]=Kestrel.Math.V.add(kestrel.doc.entities[0].points[0],[0,10,0])})')
        assert ev('kestrel.doc.entities[1].text')=='L=10.00', ev('kestrel.doc.entities')
    test('actual clipboard remaps complete reference graphs into a new drawing',copy_full)
    def copy_partial():
        ev('kestrel.doc.selection=new Set([kestrel.doc.entities[1].id]);kestrel.selectionChanged()');action('copy-clipboard');action('new');action('paste');ev('kestrel.acceptPoint([0,0,0])')
        assert ev('kestrel.doc.entities[0].text')=='L=10.00';assert ev('!kestrel.doc.entities[0].fieldBindings')
        assert ev('kestrel.doc.operationWarnings.some(w=>w.includes("frozen"))')
    test('partial cross-document clipboard freezes unavailable dependencies with a warning',copy_partial)
    def freeze():
        setup();action('FIELD');submit();action('FIELDREMOVE');submit();assert ev('!kestrel.doc.entities.at(-1).fieldBindings');action('undo');assert ev('kestrel.doc.entities.at(-1).fieldBindings.length')==1
    test('FIELDREMOVE freezes values in one reversible transaction',freeze)
    def choose_binding():
        setup();action('FIELDTABLE');submit({'columns':'[{"label":"Type","property":"type"},{"label":"Length","property":"length"}]'})
        action('FIELD');fill({'binding':'cell:1:1'});assert page.locator('[name="target"]').input_value()=='cell:1:1';assert page.locator('[name="property"]').input_value()=='length'
        submit({'precision':3,'trimZeros':False});assert ev('kestrel.doc.entities.at(-1).cells[1][1]')=='50.000'
        assert ev('kestrel.doc.entities.at(-1).cells[1][0]')=='LINE'
    test('existing-binding selector edits the chosen table field without disturbing adjacent cells',choose_binding)
    def extraction_link():
        setup();action('DATAEXTRACTION');submit({'format':'linked','position':'20,30,0'})
        assert ev('kestrel.doc.entities.at(-1).position')==[20,30,0]
        assert ev('kestrel.doc.entities.at(-1).fieldBindings.length')==4
        ev('kestrel.doc.transaction("Resize",()=>{kestrel.doc.byId.get("lineA").points[1]=[0,70,0]})')
        assert ev('kestrel.doc.entities.at(-1).cells[1][2]')=='70'
    test('DATAEXTRACTION can produce linked measurements instead of snapshot cells',extraction_link)
    def partial_chain():
        setup();action('FIELD');submit();ev('window.firstField=kestrel.doc.entities.at(-1).id;kestrel.doc.selection.clear();kestrel.selectionChanged()');action('FIELD')
        submit({'kind':'formula','sources':json.dumps([{'name':'A','kind':'field','entity':ev('firstField'),'target':'text'}]),'expression':'A * 2','template':'{{Result}}'})
        ev('kestrel.doc.selection=new Set([firstField,kestrel.doc.entities.at(-1).id]);kestrel.selectionChanged()');action('copy-clipboard');action('new');action('paste');ev('kestrel.acceptPoint([0,0,0])')
        assert ev('kestrel.doc.entities.every(e=>!e.fieldBindings)');assert ev('kestrel.doc.entities.map(e=>e.text)')==['50.00','100.00']
    test('partial clipboard transitively freezes numeric links whose source field was frozen',partial_chain)
    def aliases():
        for command in ['FIELD','UPDATEFIELD','FIELDINFO','DWGPROPS','FIELDTABLE']:
            assert page.evaluate('(id)=>{const value=kestrel.run(id);return !!value&&typeof value.then==="function";}',command);close()
    test('direct and aliased commands retain the asynchronous handler contract',aliases)
    browser.close()
failed=sum(r['status']=='failed' for r in results);(OUT/'fields-browser-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'javascript_errors':errors,'tests':results},indent=2)+'\n');print('RESULT',len(results)-failed,'passed;',failed,'failed; JS errors:',errors);raise SystemExit(bool(failed or errors))
