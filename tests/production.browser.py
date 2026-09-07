#!/usr/bin/env python3
"""New production UI interactions; fixture setup is explicit, no mocked editor methods."""
from pathlib import Path
import os,json,traceback
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'tests/results';OUT.mkdir(exist_ok=True)
results=[];errors=[]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1600,'height':1000},accept_downloads=True)
    page.on('pageerror',lambda e:errors.append(str(e)));page.set_default_timeout(10000)
    url=os.environ.get('KESTREL_TEST_URL')
    if url:page.goto(url,wait_until='domcontentloaded')
    else:page.set_content((ROOT/'Kestrel-CAD.html').read_text(),wait_until='domcontentloaded')
    page.wait_for_function('document.documentElement.dataset.ready==="true"',timeout=30000)
    def test(name,fn):
        before=len(errors)
        try:
            fn();assert len(errors)==before,errors[before:];results.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
        except Exception as e:
            traceback.print_exc();results.append({'name':name,'status':'failed','error':str(e)});page.screenshot(path=str(OUT/'production-failure.png'));page.evaluate('kestrel.closeDialog();kestrel.cancel(false)')
    def fresh():page.evaluate("async()=>{kestrel.closeDialog();kestrel.docs=[kestrel.doc];await kestrel.run('new');kestrel.settings.osnap=false;kestrel.settings.snap=false;kestrel.settings.ortho=false;kestrel.settings.polar=false;}")
    def action(x):page.evaluate('(id)=>kestrel.run(id)',x)
    def command(x):page.locator('#command-input').fill(x);page.locator('#command-input').press('Enter');page.wait_for_timeout(70)
    def select(ids):page.evaluate('(ids)=>{kestrel.doc.selection=new Set(ids.map(i=>kestrel.doc.entities[i].id));kestrel.selectionChanged();}',ids)
    def submit(fields):
        for k,v in fields.items():
            el=page.locator('#modal [name="'+k+'"]')
            if el.evaluate('(e)=>e.tagName')=='SELECT':el.select_option(str(v))
            else:el.fill(str(v))
        page.locator('#modal-submit').click();page.wait_for_timeout(70)
        assert not page.locator('#modal-error').is_visible(),page.locator('#modal-error').inner_text()
    def eq(expr,value):assert page.evaluate(expr)==value,(expr,page.evaluate(expr),value)
    def blocks():
        fresh();command('LINE 0,0 100,0 ENTER');select([0]);action('block-create');submit({'name':'Beam','base':'0,0,0'});eq('kestrel.doc.entities[0].type','INSERT')
        action('block-insert');submit({'position':'200,0,0','scale':2,'rotation':0});eq('kestrel.doc.entities.length',2)
        eq('Kestrel.Production.expand(kestrel.doc,kestrel.doc.entities[1])[0].points[1][0]',400)
    test('block creation and insertion through dialogs',blocks)
    def shared():
        select([0]);action('block-edit');select([0]);command('MOVE 0,0 0,30');action('block-save');eq('Kestrel.Production.expand(kestrel.doc,kestrel.doc.entities[0])[0].points[0][1]',30);eq('Kestrel.Production.expand(kestrel.doc,kestrel.doc.entities[1])[0].points[0][1]',60)
    test('BEDIT and BCLOSE update shared definition instances',shared)
    def attrs():
        select([0]);action('attributes');submit({'definitions':json.dumps([{'tag':'ID','value':'B','height':2,'position':[0,5,0]}]),'values':json.dumps({'ID':'B-20'})});eq('kestrel.doc.geometry(kestrel.doc.entities[0]).texts[0].text','B-20')
    test('attribute authoring and instance value editing',attrs)
    def clipboard():
        select([0]);page.evaluate('kestrel.copyClipboard()');action('new');action('paste');command('0,0');eq('kestrel.doc.entities[0].type','INSERT');eq('kestrel.doc.production.blocks.length',1);assert page.evaluate('kestrel.doc.geometry(kestrel.doc.entities[0]).segments.length')>0
    test('clipboard copies referenced definitions across drawings',clipboard)
    def explode():select([0]);action('explode');eq('kestrel.doc.entities[0].type','LINE');action('undo');eq('kestrel.doc.entities[0].type','INSERT')
    test('block explode and undo restore reference identity',explode)
    def linear():
        fresh();command('LINE 0,0 30,40 ENTER');select([0]);command('DIMLINEAR');submit({});eq('kestrel.doc.entities[1].kind','linear');eq('kestrel.doc.geometry(kestrel.doc.entities[1]).texts[0].text','30.00')
        page.evaluate("kestrel.doc.transaction('edit fixture endpoint',()=>{kestrel.doc.entities[0].points[1][0]=60;})");eq('kestrel.doc.geometry(kestrel.doc.entities[1]).texts[0].text','60.00')
    test('DIMLINEAR and associative updates do not use aligned distance',linear)
    def dimmodes():
        fresh();action('dim-radius');submit({'a':'0,0,0','b':'3,4,0'});eq('kestrel.doc.geometry(kestrel.doc.entities[0]).texts[0].text','R5.00');action('dim-angular');submit({'a':'0,0,0','b':'20,0,0','c':'0,20,0'});eq('kestrel.doc.geometry(kestrel.doc.entities[1]).texts[0].text','90.00°')
    test('radial and angular dimensions through dialogs',dimmodes)
    def table():
        fresh();action('table');submit({'cells':'[["Part","Qty"],["Plate","2"]]'});eq('kestrel.doc.entities[0].cells[1][1]','2');select([0]);action('table');submit({'cells':'[["Part","Qty"],["Plate","7"]]'});eq('kestrel.doc.entities[0].cells[1][1]','7');action('undo');eq('kestrel.doc.entities[0].cells[1][1]','2')
    test('editable table creation, cell editing and undo',table)
    def hatch():
        fresh();command('RECTANGLE 0,0 100,100');command('RECTANGLE 30,30 70,70');select([0,1]);action('associative-hatch');submit({'pattern':'solid'});eq('kestrel.doc.entities[2].loops.length',2)
        assert page.evaluate('kestrel.doc.geometry(kestrel.doc.entities[2]).triangles.length')>0
    test('island hatch authoring and filled geometry',hatch)
    def stretch():
        fresh();command('LINE 0,0 100,0 ENTER');select([0]);action('stretch');submit({'min':'90,-10','max':'110,10','delta':'25,0'});eq('kestrel.doc.entities[0].points[1][0]',125)
    test('stretch dialog edits crossing vertices',stretch)
    def brk():select([0]);action('break');submit({'a':'25,0','b':'75,0'});eq('kestrel.doc.entities.length',2)
    test('break dialog produces editable remainders',brk)
    def align():
        fresh();command('LINE 0,0 100,0 ENTER');select([0]);action('align2');submit({'a':'0,0,0','b':'100,0,0','c':'5,5,5','d':'5,5,105'});assert abs(page.evaluate('kestrel.doc.entities[0].points[1][2]')-105)<1e-5
    test('alignment rotates actual geometry into 3D',align)
    def ucs():
        fresh();action('ucs-manager');submit({'origin':'10,20,30','x':'0,1,0','y':'0,0,1'});command('LINE 0,0 100,0 ENTER');eq('kestrel.doc.entities[0].points',[[10,20,30],[10,120,30]]);command('CIRCLE 0,0 0,10');assert abs(page.evaluate('kestrel.doc.entities[1].radius')-10)<1e-5
    test('UCS line and circle coordinate input uses the actual plane',ucs)
    def layout():
        fresh();command('LINE 0,0 100,0 ENTER');action('layout-manager');submit({'layouts':json.dumps([{'name':'Fabrication','width':420,'height':297,'viewports':[{'x':10,'y':10,'width':400,'height':265,'center':[0,0,0],'scale':2,'locked':True}]}])})
        action('plot-layout')
        with page.expect_download() as dl:submit({})
        text=Path(dl.value.path()).read_text();assert 'width="420mm"' in text;assert 'M210,142.5L260,142.5' in text
        page.screenshot(path=str(OUT/'production-layout.png'))
    test('layout dialog and scaled SVG download',layout)
    def native():
        action('save')
        # Save is a direct download; model snapshot is checked independently too.
        eq('Kestrel.Drawing.from(kestrel.doc.serialize()).production.layouts[0].name','Fabrication')
    test('layout native persistence',native)
    def worker():
        fresh();command('LINE 0,0 100,0 ENTER');select([0]);action('block-create');submit({'name':'DXFBlock'});out=page.evaluate("async()=>{const text=await kestrel.io('write-dxf',kestrel.doc.serialize());return (await kestrel.io('parse-dxf',text,'test')).data;}")
        assert out['entities'][0]['type']=='INSERT';assert any(b['name']=='DXFBlock' for b in out['production']['blocks'])
    test('worker round trip preserves actual BLOCK and INSERT',worker)
    page.evaluate("kestrel.setRibbon('Drafting');kestrel.fit(false)");page.screenshot(path=str(OUT/'production-ui.png'));browser.close()
failed=sum(t['status']=='failed' for t in results)
(OUT/'production-browser-results.json').write_text(json.dumps({'suite':'production browser interactions','passed':len(results)-failed,'failed':failed,'javascript_errors':errors,'tests':results},indent=2)+'\n')
print(f'{len(results)-failed}/{len(results)} passed; JS errors: {errors}')
raise SystemExit(1 if failed or errors else 0)
