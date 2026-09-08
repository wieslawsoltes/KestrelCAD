#!/usr/bin/env python3
"""Actual editor forms, worker exchange, clipboard and browser downloads."""
from pathlib import Path
import json, os, traceback
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'tests/results';OUT.mkdir(exist_ok=True)
results=[];errors=[]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1600,'height':1050},accept_downloads=True);page.set_default_timeout(20000)
    page.on('pageerror',lambda e:errors.append(str(e)))
    if os.environ.get('KESTREL_TEST_URL'):page.goto(os.environ['KESTREL_TEST_URL'],wait_until='domcontentloaded')
    else:page.set_content((ROOT/'Kestrel-CAD.html').read_text(),wait_until='domcontentloaded')
    page.wait_for_function('document.documentElement.dataset.ready==="true"')
    page.add_script_tag(content=(ROOT/'tests/polar-block.fixture.js').read_text())
    def action(name):page.evaluate('(name)=>kestrel.run(name)',name)
    def setup():
        page.evaluate('''()=>{kestrel.closeDialog();kestrel.cancel(false);while(kestrel.docs.length>1){const old=kestrel.docs[0];old.dirty=false;kestrel.closeDocument(old.id);}const f=makePolarBlockFixture();kestrel.addDocument(f.doc);kestrel.doc.selection=new Set([f.insert.id]);kestrel.selectionChanged();kestrel.setRibbon('Blocks');kestrel.fit(false);kestrel.autosave();}''')
    def state(expr):return page.evaluate('(()=>{const d=kestrel.doc,e=d.entities[0],b=d.production.blocks.find(b=>b.id===e.block),r=Kestrel.Production.expand(d,e);return '+expr+'})()')
    def submit(values):
        for key,v in values.items():
            el=page.locator('#modal [name="'+key+'"]')
            if isinstance(v,bool):el.set_checked(v)
            elif el.evaluate('(e)=>e.tagName')=='SELECT':el.select_option(str(v))
            else:el.fill(str(v))
        page.locator('#modal-submit').click();page.wait_for_function('!document.querySelector("#modal").open||!document.querySelector("#modal-error").hidden')
        assert not page.locator('#modal-error').is_visible(),page.locator('#modal-error').inner_text()
    def test(name,fn):
        n=len(errors)
        try:setup();fn();assert len(errors)==n,errors[n:];results.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
        except Exception as e:traceback.print_exc();results.append({'name':name,'status':'failed','error':str(e)});page.evaluate('kestrel.closeDialog()')
    def ribbon_labels():
        assert page.locator('#ribbon .ribbon-large .button-label').evaluate_all('(els)=>els.every(e=>e.scrollWidth<=e.clientWidth+1)')
    test('large ribbon labels wrap within their own controls',ribbon_labels)
    def inverse():
        page.locator('#ribbon [data-action="dynamic-lookup"]').click();submit({'lookupOut_Size':2,'lookupOut_Finish':True})
        assert state('e.parameters.Variant')=='Long'
        assert state('r.filter(x=>x.type==="CIRCLE").every(x=>Math.abs(x.radius-2)<1e-7)')
        assert state('r.filter(x=>x.attributeTag).every(x=>x.text==="Long / 4")')
    test('Blocks ribbon matches numeric and boolean outputs and regenerates annotations',inverse)
    def history():
        action('dynamic-lookup');submit({'lookupOut_Size':2,'lookupOut_Finish':False});action('undo');assert state('r.find(x=>x.type==="CIRCLE").radius')==1
        action('redo');assert state('e.parameters.Variant')=='Large'
    test('matched table selection has one reversible history step',history)
    def reject():
        action('dynamic-lookup');before=state('d.snapshot()');page.locator('[name="lookupOut_Size"]').fill('3');page.locator('#modal-submit').click()
        assert 'No lookup' in page.locator('#modal-error').inner_text();assert state('d.snapshot()')==before
        submit({'lookupOut_Size':2,'lookupOut_Finish':True});assert state('e.parameters.Variant')=='Long'
    test('unmatched properties preserve the document and permit correction in the same dialog',reject)
    def ambiguous():
        page.evaluate('kestrel.doc.transaction("Ambiguous table",()=>{const t=kestrel.doc.production.blocks[0].dynamic.lookups[0];t.rows[1].set={Size:1,Finish:false};})')
        action('dynamic-lookup');before=state('d.snapshot()');page.locator('#modal-submit').click();assert 'Ambiguous' in page.locator('#modal-error').inner_text();assert state('d.snapshot()')==before
    test('duplicate output tuples reject instead of selecting by row order',ambiguous)
    def stale():
        action('dynamic-lookup');page.evaluate('kestrel.doc.transaction("Other edit",()=>kestrel.doc.add("POINT",{position:[99,99,0]}))');page.locator('#modal-submit').click()
        assert 'changed' in page.locator('#modal-error').inner_text();assert state('d.entities.length')==2;assert state('e.parameters.Variant||"Small"')=='Small'
    test('stale lookup dialog cannot overwrite an intervening drawing edit',stale)
    def author(rotates=True,axis='0,0,1'):
        page.evaluate('kestrel.doc.transaction("No array",()=>kestrel.doc.production.blocks[0].dynamic.actions.pop())')
        action('dynamic-action');submit({'type':'polar-array','count':'4','fill':'360','normal':axis,'base':'10,0,0','rotateItems':rotates})
        assert state('r.filter(x=>x.type==="LINE").length')==4
        points=state('r.filter(x=>x.type==="LINE")[1].points')
        expected=[[0,10,0],[0,12,0]] if rotates else [[0,10,0],[2,10,0]]
        if axis=='0,1,0':expected=[[0,0,-10],[0,0,-12]]
        assert all(abs(v-e)<1e-6 for point,target in zip(points,expected) for v,e in zip(point,target)),points
    test('action authoring creates a real polar array and rotates each item',author)
    test('unrotated action preserves group orientation using the shared base',lambda:author(False))
    test('custom polar axis generates free-space rather than flattened geometry',lambda:author(True,'0,1,0'))
    def properties():
        action('dynamic-properties');submit({'db_Count':6,'db_Sweep':-180});assert state('r.filter(x=>x.type==="LINE").length')==6
        p=state('r.filter(x=>x.type==="LINE").at(-1).points[1]');assert abs(p[0]+12)<1e-7 and abs(p[1])<1e-7
    test('typed count and negative sweep edits update actual partial-array endpoints',properties)
    def clipboard():
        action('dynamic-lookup');submit({'lookupOut_Size':2,'lookupOut_Finish':True})
        page.evaluate('kestrel.copyClipboard()');action('new');action('paste');page.locator('#command-input').fill('0,0');page.locator('#command-input').press('Enter')
        assert state('b.dynamic.actions[1].type')=='polar-array';assert state('e.parameters.Variant')=='Long'
        page.evaluate('kestrel.doc.selection=new Set([kestrel.doc.entities[0].id]);kestrel.selectionChanged()');action('dynamic-lookup');submit({'lookupOut_Size':1,'lookupOut_Finish':False})
        assert state('r.find(x=>x.type==="CIRCLE").radius')==1
    test('clipboard transfers definitions, inverse lookup and editable polar behavior',clipboard)
    def native():
        action('dynamic-lookup');submit({'lookupOut_Size':2,'lookupOut_Finish':True})
        with page.expect_download() as dl:action('save')
        data=json.loads(Path(dl.value.path()).read_text());assert data['production']['blocks'][0]['dynamic']['actions'][1]['type']=='polar-array'
        page.evaluate('(d)=>kestrel.addDocument(Kestrel.Drawing.from(d))',data);assert state('e.parameters.Variant')=='Long'
    test('native browser download reopens all polar and lookup settings',native)
    def worker():
        action('dynamic-lookup');submit({'lookupOut_Size':2,'lookupOut_Finish':True})
        data=page.evaluate('async()=>{const s=await kestrel.io("write-dxf",kestrel.doc.serialize());return (await kestrel.io("parse-dxf",s,"polar")).data;}')
        report=page.evaluate('(data)=>{const d=Kestrel.Drawing.from(data),r=Kestrel.Production.expand(d,d.entities[0]);return {count:r.filter(e=>e.type==="CIRCLE").length,radii:r.filter(e=>e.type==="CIRCLE").map(e=>e.radius)}}',data)
        assert report['count']==4 and all(abs(r-2)<1e-7 for r in report['radii'])
    test('actual worker DXF exchange retains the evaluated polar variant',worker)
    def alias():
        el=page.locator('#command-input');el.fill('BLOOKUPMATCH');el.press('Enter');page.wait_for_function('document.querySelector("#modal").open')
        assert page.locator('[name="lookupOut_Size"]').is_visible()
    test('command-line BLOOKUPMATCH opens the installed tool',alias)
    def switch():
        page.evaluate('''kestrel.doc.transaction('Second table',()=>{const d=kestrel.doc.production.blocks[0].dynamic;d.parameters.push({name:'Fastener',type:'enum',default:'M6',values:['M6','M8']},{name:'Diameter',type:'length',default:6});d.lookups.push({parameter:'Fastener',rows:[{value:'M6',set:{Diameter:6}},{value:'M8',set:{Diameter:8}}]});})''')
        action('dynamic-lookup');page.locator('[name="lookup"]').select_option('Fastener');assert page.locator('[name="lookupOut_Size"]').count()==0
        submit({'lookupOut_Diameter':8});assert state('e.parameters.Fastener')=='M8';assert state('e.parameters.Variant||"Small"')=='Small'
    test('switching lookup tables replaces typed fields without writing the wrong selector',switch)
    setup();page.screenshot(path=str(OUT/'polar-blocks.png'));browser.close()
failed=sum(r['status']=='failed' for r in results);(OUT/'polar-block-browser-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'javascript_errors':errors,'tests':results},indent=2)+'\n');print('RESULT',len(results)-failed,'passed;',failed,'failed; JS errors:',errors);raise SystemExit(bool(failed or errors))
