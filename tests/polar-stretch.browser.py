#!/usr/bin/env python3
"""Real polar-stretch authoring, property, persistence and exchange workflows."""
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
    page.add_script_tag(content=(ROOT/'tests/polar-stretch.fixture.js').read_text())
    def action(name):page.evaluate('(name)=>kestrel.run(name)',name)
    def setup():
        page.evaluate('''()=>{kestrel.closeDialog();kestrel.cancel(false);while(kestrel.docs.length>1){const old=kestrel.docs[0];old.dirty=false;kestrel.closeDocument(old.id);}const f=makePolarStretchFixture();kestrel.addDocument(f.doc);kestrel.doc.selection=new Set([f.insert.id]);kestrel.selectionChanged();kestrel.setRibbon('Blocks');kestrel.fit(false);kestrel.autosave();}''')
    def state(expr):return page.evaluate('(()=>{const d=kestrel.doc,e=d.entities[0],b=d.production.blocks.find(b=>b.id===e.block),r=Kestrel.Production.expand(d,e);return '+expr+'})()')
    def near(actual,expected):
        assert len(actual)==len(expected)
        assert all(abs(a-b)<1e-6 for a,b in zip(actual,expected)),actual
    def submit(values):
        for key,v in values.items():
            el=page.locator('#modal [name="'+key+'"]')
            # Member-mode selects live inside a collapsed explanation panel.
            el.evaluate('(e)=>{const d=e.closest("details");if(d)d.open=true;}')
            if isinstance(v,bool):el.set_checked(v)
            elif el.evaluate('(e)=>e.tagName')=='SELECT':el.select_option(str(v))
            else:el.fill(str(v))
        page.locator('#modal-submit').click();page.wait_for_function('!document.querySelector("#modal").open||!document.querySelector("#modal-error").hidden')
        assert not page.locator('#modal-error').is_visible(),page.locator('#modal-error').inner_text()
    def test(name,fn):
        n=len(errors)
        try:setup();fn();assert len(errors)==n,errors[n:];results.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
        except Exception as e:traceback.print_exc();results.append({'name':name,'status':'failed','error':str(e)});page.evaluate('kestrel.closeDialog()')
    def properties():
        page.locator('#ribbon [data-action="dynamic-properties"]').click();submit({'db_Reach':20,'db_Angle':90})
        near(state('r[0].points[1]'),[0,20,0]);near(state('r[2].points[1]'),[0,5,0]);assert state('r.find(x=>x.attributeTag).text')=='Reach 20'
    test('actual block properties regenerate reach, rotation and rotate-only members',properties)
    def author(mode='frame',axis='0,0,1'):
        page.evaluate('kestrel.doc.transaction("Remove old action",()=>kestrel.doc.production.blocks[0].dynamic.actions=[])')
        page.locator('#ribbon [data-action="dynamic-action"]').click()
        submit({'type':'polar-stretch','length':'Reach','baseLength':10,'angle':'Angle','direction':'1,0,0','normal':axis,'min':'8,-2,-2','max':'12,2,2','mode0':mode,'mode2':'rotate','target3':False})
        assert state('b.dynamic.actions[0].type')=='polar-stretch'
        action('dynamic-properties');submit({'db_Reach':20,'db_Angle':90})
        near(state('r[0].points[1]'),[0,20,0] if axis=='0,0,1' else [0,0,-20])
        near(state('r[0].points[0]'),([0,10,0] if mode=='move' else [0,0,0]))
    test('BACTION form authors frame stretching and explicit member modes',author)
    test('BACTION Move whole keeps the target rigid',lambda:author('move'))
    test('BACTION accepts a free-space rotation axis',lambda:author('frame','0,1,0'))
    def undo():
        action('dynamic-properties');submit({'db_Reach':20,'db_Angle':90});action('undo');near(state('r[0].points[1]'),[10,0,0]);action('redo');near(state('r[0].points[1]'),[0,20,0])
    test('undo and redo preserve one complete polar parameter change',undo)
    def invalid():
        action('dynamic-action');before=state('d.snapshot()');page.locator('[name="type"]').select_option('polar-stretch');page.locator('[name="direction"]').fill('0,0,1');page.locator('#modal-submit').click()
        assert 'perpendicular' in page.locator('#modal-error').inner_text();assert state('d.snapshot()')==before
    test('invalid polar frame rejects without changing shared definitions',invalid)
    def stale():
        action('dynamic-action');page.evaluate('kestrel.doc.transaction("Other edit",()=>kestrel.doc.add("POINT",{position:[99,99,0]}))');page.locator('#modal-submit').click()
        assert 'changed' in page.locator('#modal-error').inner_text();assert state('d.entities.length')==2
    test('stale action authoring cannot overwrite a newer edit',stale)
    def partial():
        page.evaluate('kestrel.doc.transaction("Crossing circle",()=>kestrel.doc.production.blocks[0].entities[1].center=[12,0,0])')
        action('dynamic-properties');before=state('d.snapshot()');page.locator('#modal [name="db_Reach"]').fill('20');page.locator('#modal-submit').click()
        assert 'partially' in page.locator('#modal-error').inner_text();assert state('d.snapshot()')==before
    test('partial conic deformation reports an error with exact drawing rollback',partial)
    def native():
        properties()
        with page.expect_download() as dl:action('save')
        data=json.loads(Path(dl.value.path()).read_text());assert data['production']['blocks'][0]['dynamic']['actions'][0]['type']=='polar-stretch'
        page.evaluate('(d)=>kestrel.addDocument(Kestrel.Drawing.from(d))',data);near(state('r[0].points[1]'),[0,20,0])
    test('downloaded native project reopens editable polar stretching',native)
    def clipboard():
        properties();page.evaluate('kestrel.copyClipboard()');action('new');action('paste');page.locator('#command-input').fill('0,0');page.locator('#command-input').press('Enter')
        assert state('b.dynamic.actions[0].type')=='polar-stretch'
        page.evaluate('kestrel.doc.selection=new Set([kestrel.doc.entities[0].id]);kestrel.selectionChanged()');action('dynamic-properties');submit({'db_Reach':15,'db_Angle':0})
        p=state('r[0].points');near([p[1][i]-p[0][i] for i in range(3)],[15,0,0])
    test('clipboard preserves editable behavior and independent subsequent values',clipboard)
    def worker():
        properties();data=page.evaluate('async()=>{const s=await kestrel.io("write-dxf",kestrel.doc.serialize());return (await kestrel.io("parse-dxf",s,"arm")).data;}')
        tip=page.evaluate('(data)=>{const d=Kestrel.Drawing.from(data);return Kestrel.Production.expand(d,d.entities[0])[0].points[1];}',data);near(tip,[0,20,0])
    test('real exchange worker emits the evaluated geometry, not its baseline',worker)
    def independent():
        page.evaluate('()=>{const id=kestrel.doc.entities[0].id;Kestrel.Production.insertBlock(kestrel.doc,kestrel.doc.entities[0].block,[50,0,0]);kestrel.doc.selection=new Set([id]);kestrel.selectionChanged();}');properties()
        near(state('Kestrel.Production.expand(d,d.entities[1])[0].points[1]'),[60,0,0])
    test('property edits leave a second shared-definition instance unchanged',independent)
    setup();properties();page.screenshot(path=str(OUT/'polar-stretch.png'));browser.close()
failed=sum(r['status']=='failed' for r in results);(OUT/'polar-stretch-browser-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'javascript_errors':errors,'tests':results},indent=2)+'\n');print('RESULT',len(results)-failed,'passed;',failed,'failed; JS errors:',errors);raise SystemExit(bool(failed or errors))
