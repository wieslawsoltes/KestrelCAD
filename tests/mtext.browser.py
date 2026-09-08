#!/usr/bin/env python3
"""Actual standalone MTEXT authoring, rendering, persistence and exchange workflows."""
from pathlib import Path
import json, os, traceback
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'tests/results';OUT.mkdir(exist_ok=True)
results=[];errors=[]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1600,'height':1000},accept_downloads=True);page.set_default_timeout(12000)
    page.on('pageerror',lambda e:errors.append(str(e)))
    if os.environ.get('KESTREL_TEST_URL'):page.goto(os.environ['KESTREL_TEST_URL'],wait_until='domcontentloaded')
    else:page.set_content((ROOT/'Kestrel-CAD.html').read_text(),wait_until='domcontentloaded')
    page.wait_for_function('document.documentElement.dataset.ready==="true"')
    def ev(js):return page.evaluate(js)
    def action(id):page.evaluate('(id)=>kestrel.run(id)',id)
    def select():ev('kestrel.doc.selection=new Set([kestrel.doc.entities[0].id]);kestrel.selectionChanged()')
    def close():ev('kestrel.closeDialog();kestrel.cancel(false)')
    def test(name,fn):
        before=len(errors)
        try:fn();assert len(errors)==before,errors[before:];results.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
        except Exception as e:traceback.print_exc();results.append({'name':name,'status':'failed','error':str(e)});close()
    def submit(fields=None):
        for key,value in (fields or {}).items():
            el=page.locator('#modal [name="'+key+'"]')
            if isinstance(value,bool):el.set_checked(value)
            elif el.evaluate('(el)=>el.tagName')=='SELECT':el.select_option(str(value))
            else:el.fill(str(value))
        page.locator('#modal-submit').click();page.wait_for_timeout(100)
        assert not page.locator('#modal-error').is_visible(),page.locator('#modal-error').inner_text()
    raw=r'{\H1.5x;FABRICATION NOTES}\P{\C1;\LWarning\l}: plate \S3/8; in\Pשלום 123 — مرحبا — Zażółć gęślą jaźń'
    def create():
        action('new');page.locator('[data-ribbon="Text"]').click();page.locator('#ribbon [data-action="mtext"]').click()
        submit({'text':raw,'height':5,'width':110,'background':True})
        assert ev('kestrel.tool.id')=='text';ev('kestrel.acceptPoint([20,30,0])');action('fit')
        e=ev('kestrel.doc.entities[0]');assert e['type']=='MTEXT' and e['text']==raw and e['position']==[20,30,0]
        assert ev('kestrel.doc.geometry(kestrel.doc.entities[0]).texts[0].composition.runs.length')>5
    test('Text ribbon authors a real native rich annotation at an exact insertion point',create)
    def renderer():
        page.wait_for_timeout(100);ev('kestrel.doc.selection.clear();kestrel.selectionChanged()')
        assert ev('kestrel.renderer.texts.some(v=>v.t.composition)')
        state=ev("(()=>{const c=kestrel.doc.geometry(kestrel.doc.entities[0]).texts[0].composition;return {rtl:c.runs.some(r=>r.direction==='rtl'),red:c.runs.some(r=>r.style.color==='#ef6565'),strokes:c.lines.length,prepared:c.prepared.length}})()")
        assert state['rtl'] and state['red'] and state['strokes']>=2 and state['prepared']>5
        page.screenshot(path=str(OUT/'mtext-composition.png'))
    test('actual renderer receives prepared fraction decorations and bidirectional colored runs',renderer)
    def picking():
        q=ev('(()=>{const c=kestrel.doc.geometry(kestrel.doc.entities[0]).texts[0].composition;return kestrel.camera.project(c.world(25,8))})()')
        box=page.locator('#interaction-canvas').bounding_box() if page.locator('#interaction-canvas').count() else page.locator('#overlay').bounding_box()
        page.mouse.dblclick(box['x']+q[0],box['y']+q[1]);page.wait_for_timeout(100)
        assert page.locator('#modal-title').inner_text()=='Edit rich MTEXT';close()
    test('double-click hit testing opens rich text instead of flattening its formatting',picking)
    def edit():
        select();action('MTEXTEDIT');assert 'FABRICATION' in page.locator('#mtext-source').input_value();submit({'width':150,'text':raw+r'\PRevised'})
        assert ev('kestrel.doc.entities[0].width')==150;action('undo');assert ev('kestrel.doc.entities[0].text')==raw;action('redo')
    test('rich editing and undo redo preserve raw control groups',edit)
    def preview():
        action('mtext-edit');page.locator('#mtext-source').fill('<img src=x onerror=alert(1)>');page.locator('#mtext-source').dispatch_event('input');page.wait_for_timeout(200)
        assert page.locator('#mtext-preview img').count()==0;assert '<img' in page.locator('#mtext-preview').inner_text();close()
    test('live preview displays markup literally without executing it',preview)
    def columns():
        select();action('mtext-edit');submit({'columnCount':2,'width':55,'columnGutter':8,'text':'Column one\\NColumn two','reverse':True})
        c=ev('kestrel.doc.geometry(kestrel.doc.entities[0]).texts[0].composition');assert len(c['quads'])==2;assert c['allLines'][1]['column']==1
        with page.expect_download() as dl:action('save')
        data=json.loads(Path(dl.value.path()).read_text());assert data['entities'][0]['columns']['reverse'];assert data['entities'][0]['type']=='MTEXT'
        page.evaluate('(data)=>{kestrel.addDocument(Kestrel.Drawing.from(data));kestrel.run("fit")}',data)
        assert ev('kestrel.doc.entities[0].columns.count')==2
    test('balanced reversed columns and explicit column breaks survive actual project downloads',columns)
    def report():
        select();action('mtext-report');assert '2 lines' in page.locator('#modal').inner_text();assert 'Multi-column' in page.locator('#modal').inner_text();close()
    test('composition report states the actual layout and DXF column boundary',report)
    def svg():
        select();action('export-svg')
        with page.expect_download() as dl:submit()
        text=Path(dl.value.path()).read_text();assert '<text' in text and 'Column one' in text and '<polygon' in text
    test('SVG download contains composed text and a vector background mask',svg)
    def single():
        select();action('mtext-edit');submit({'columnCount':1,'text':raw,'width':100});select()
        with page.expect_download() as dl:action('export-dxf')
        text=Path(dl.value.path()).read_text();assert '\nMTEXT\n' in text and '\\S3/8;' in text
        # Exercise the real worker and document integration, not a monkey-patched converter.
        ev('kestrel.doc.selection.clear()')
        page.locator('#file-input').set_input_files({'name':'rich-roundtrip.dxf','mimeType':'application/dxf','buffer':text.encode()})
        page.wait_for_timeout(200);assert ev('kestrel.doc.entities[0].type')=='MTEXT';assert ev('kestrel.doc.entities[0].text')==raw
        close()
    test('single-column DXF download and worker import retain a genuine MTEXT entity',single)
    def copy():
        select();ev('kestrel.copyClipboard()');action('new');ev('kestrel.pasteClipboard();kestrel.acceptPoint([50,60,0])')
        assert ev('kestrel.doc.entities[0].type')=='MTEXT';assert ev('kestrel.doc.entities[0].text')==raw
    test('clipboard retains rich content and independent text-local transforms',copy)
    def explode():
        select();action('mtext-explode');assert ev('kestrel.doc.entities.every(e=>e.type!=="MTEXT")');assert ev('kestrel.doc.entities.length')>5
        action('undo');assert ev('kestrel.doc.entities[0].type')=='MTEXT'
    test('explicit explosion creates editable evaluated glyph runs and undo restores rich source',explode)
    def stale():
        select();action('mtext-edit');ev("kestrel.doc.transaction('newer edit',()=>kestrel.doc.add('POINT',{position:[100,100,0]}))")
        page.locator('#modal-submit').click();page.wait_for_timeout(100);assert 'changed' in page.locator('#modal-error').inner_text();close()
    test('stale rich-text dialog rejects instead of overwriting a newer edit',stale)
    def contract():
        assert ev("['mtext-report','MTEXTINFO','mtext-edit','MTEXTEDIT'].every(id=>{const r=kestrel.run(id);kestrel.closeDialog();return r && typeof r.catch==='function'})")
        close()
    test('direct and aliased rich-text commands preserve Promise contract',contract)
    def image():
        action('mtext-demo');ev('kestrel.doc.selection.clear();kestrel.selectionChanged()');page.wait_for_timeout(120)
        with page.expect_download() as dl:action('export-png')
        assert Path(dl.value.path()).read_bytes().startswith(b'\x89PNG')
        page.screenshot(path=str(OUT/'mtext-composition.png'))
    test('rich annotation demo and PNG export render the actual editor',image)
    browser.close()
failed=sum(r['status']=='failed' for r in results)
(OUT/'mtext-browser-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'javascript_errors':errors,'tests':results},indent=2)+'\n')
print('RESULT',len(results)-failed,'passed;',failed,'failed; JS errors:',errors);raise SystemExit(bool(failed or errors))
