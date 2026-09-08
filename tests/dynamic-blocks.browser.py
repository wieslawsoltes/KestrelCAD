#!/usr/bin/env python3
"""Actual DOM controls, geometry, workers, clipboard and native/DXF downloads."""
from pathlib import Path
import json, os, traceback
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'tests/results';OUT.mkdir(exist_ok=True)
results=[];errors=[]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1600,'height':1000},accept_downloads=True)
    page.on('pageerror',lambda e:errors.append(str(e)));page.set_default_timeout(15000)
    if os.environ.get('KESTREL_TEST_URL'):page.goto(os.environ['KESTREL_TEST_URL'],wait_until='domcontentloaded')
    else:page.set_content((ROOT/'Kestrel-CAD.html').read_text(),wait_until='domcontentloaded')
    page.wait_for_function('document.documentElement.dataset.ready==="true"')
    def test(name,fn):
        before=len(errors)
        try:fn();assert len(errors)==before,errors[before:];results.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
        except Exception as e:traceback.print_exc();results.append({'name':name,'status':'failed','error':str(e)});page.evaluate('kestrel.closeDialog()')
    def action(id):page.evaluate('(id)=>kestrel.run(id)',id)
    def select(i=0):page.evaluate('(i)=>{kestrel.doc.selection=new Set([kestrel.doc.entities[i].id]);kestrel.selectionChanged();}',i)
    def submit(fields={}):
        for key,value in fields.items():
            el=page.locator('#modal [name="'+key+'"]')
            if isinstance(value,bool):el.set_checked(value)
            elif el.evaluate('(e)=>e.tagName')=='SELECT':el.select_option(str(value))
            else:el.fill(str(value))
        page.locator('#modal-submit').click();page.wait_for_timeout(80)
        assert not page.locator('#modal-error').is_visible(),page.locator('#modal-error').inner_text()
    def value(expr):return page.evaluate(expr)
    def expanded(expr=''):
        return value('(()=>{const e=Kestrel.Production.expand(kestrel.doc,kestrel.doc.entities[0]);return '+expr+'})()')
    def demo():
        page.locator('[data-ribbon="Blocks"]').click();page.locator('#ribbon [data-action="dynamic-demo"]').click()
        assert value('kestrel.doc.entities.length')==2
        select();assert page.locator('#dynamic-block-inspector').is_visible()
        assert expanded('e[0].points[1][0]')==100
    test('Blocks ribbon opens two genuinely configurable plate instances',demo)
    def parameters():
        action('dynamic-properties');submit({'db_Width':160,'db_Height':90,'db_Fastener':'M10','db_Count':5})
        assert expanded('e[0].points[2]')==[160,90,0]
        assert abs(expanded('e.find(x=>x.id==="hole").radius')-5)<1e-6
        assert expanded('e.filter(x=>x.type==="LINE").length')==5
        assert '160' in expanded('e.find(x=>x.attributeTag).text')
    test('typed properties drive stretch, lookup, arrays and attributes',parameters)
    def undo():
        action('undo');assert expanded('e[0].points[1][0]')==100
        action('redo');assert expanded('e[0].points[1][0]')==160
        assert value('kestrel.doc.entities[1].parameters.Width')==160
    test('dynamic parameter changes are undoable and other instances stay independent',undo)
    def inspector():
        select();el=page.locator('#dynamic-block-inspector [name="db_Width"]');el.fill('200');el.dispatch_event('change')
        assert expanded('e[0].points[1][0]')==200
        assert page.locator('#dynamic-block-inspector [name="db_Area"]').is_disabled()
        assert page.locator('#dynamic-block-inspector [name="db_HoleRadius"]').is_disabled()
    test('property inspector edits geometry and protects driven values',inspector)
    def visibility():
        action('dynamic-properties');submit({'db_Detail':'Outline','db_Flipped':True})
        assert expanded('e.length')==2
        assert expanded('e[0].points[1][0]')==-200
    test('visibility and flip controls change real expanded geometry',visibility)
    def reset():
        action('dynamic-reset');submit();assert expanded('e[0].points[1][0]')==100
        assert expanded('e.length')==6
        action('undo');assert expanded('e[0].points[1][0]')==-200
    test('reset preserves insert position and is reversible',reset)
    def invalid():
        select();action('dynamic-properties');before=value('kestrel.doc.snapshot()')
        page.locator('#modal [name="db_Width"]').fill('105');page.locator('#modal-submit').click()
        assert page.locator('#modal-error').is_visible();assert value('kestrel.doc.snapshot()')==before
        page.locator('#modal [name="db_Width"]').fill('210');page.locator('#modal-submit').click()
        assert not page.locator('#modal-error').is_visible();assert expanded('e[0].points[1][0]')==-210
    test('invalid increments roll back and the same dialog accepts corrected values',invalid)
    def clipboard():
        select();page.evaluate('kestrel.copyClipboard()');action('new');action('paste');page.locator('#command-input').fill('0,0');page.locator('#command-input').press('Enter')
        assert value('!!kestrel.doc.production.blocks[0].dynamic')
        assert value('kestrel.doc.entities[0].parameters.Width')==210
        select();action('dynamic-properties');submit({'db_Width':220});assert abs(expanded('e[0].points[1][0]-e[0].points[0][0]')+220)<1e-6
    test('normal clipboard transfers editable definitions and instance parameters',clipboard)
    def native():
        with page.expect_download() as dl:action('save')
        data=json.loads(Path(dl.value.path()).read_text());assert data['production']['blocks'][0]['dynamic']['version']==1
        assert data['entities'][0]['parameters']['Width']==220
        assert value('Kestrel.Drawing.from(kestrel.doc.serialize()).entities[0].parameters.Width')==220
    test('native download preserves parameters, actions, lookups and geometry',native)
    def worker():
        data=page.evaluate("async()=>{const text=await kestrel.io('write-dxf',kestrel.doc.serialize());return (await kestrel.io('parse-dxf',text,'dynamic')).data;}")
        assert data['entities'][0]['type']=='INSERT';assert not any(b.get('dynamic') for b in data['production']['blocks'])
        width=page.evaluate('(data)=>{const d=Kestrel.Drawing.from(data);const p=Kestrel.Production.expand(d,d.entities[0])[0].points;return p[1][0]-p[0][0]}',data)
        assert width==-220
    test('real worker DXF exchange carries evaluated variant rather than default geometry',worker)
    def action_form():
        select();before=expanded('e[0].points[0][0]');action('dynamic-action');submit({'type':'move','x':'10'})
        # All selected targets, including the label, move after the existing flip.
        assert expanded('e[0].points[0][0]')==before+10
        action('undo');assert expanded('e[0].points[0][0]')==before
    test('action authoring adds real shared definition behavior with undo',action_form)
    def definition():
        select();action('dynamic-definition');definition=json.loads(page.locator('[name="definition"]').input_value())
        definition['parameters'][0]['max']=500
        submit({'definition':json.dumps(definition)})
        assert value('kestrel.doc.production.blocks[0].dynamic.parameters[0].max')==500
    test('definition editor persists schema edits',definition)
    def explode():
        select();before=expanded('e[0].points');action('explode');assert value('kestrel.doc.entities[0].points')==before
        action('undo');assert value('kestrel.doc.entities[0].type')=='INSERT'
    test('explode and undo preserve the evaluated instance shape',explode)
    action('dynamic-demo');select(1);page.evaluate('kestrel.fit(false)');page.screenshot(path=str(OUT/'dynamic-blocks.png'));browser.close()
failed=sum(r['status']=='failed' for r in results)
(OUT/'dynamic-blocks-browser-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'javascript_errors':errors,'tests':results},indent=2)+'\n')
print('RESULT',len(results)-failed,'passed;',failed,'failed; JS errors:',errors);raise SystemExit(bool(failed or errors))
