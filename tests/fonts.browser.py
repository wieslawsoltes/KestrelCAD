#!/usr/bin/env python3
"""Font file chooser, stroke layout, styles, text editor, outline loading and export."""
from pathlib import Path
from io import BytesIO
import json,os,subprocess,traceback
from playwright.sync_api import sync_playwright
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'tests/results';OUT.mkdir(exist_ok=True)
# Only original synthetic glyphs in memory; no proprietary font asset is copied.
def outline():
    fb=FontBuilder(1000,isTTF=True);fb.setupGlyphOrder(['.notdef','space','A','H']);glyphs={}
    for name in ['.notdef','space','A','H']:
        pen=TTGlyphPen(None)
        if name!='space':
            pen.moveTo((0,0));pen.lineTo((300,700));pen.lineTo((600,0));pen.closePath()
        glyphs[name]=pen.glyph()
    fb.setupCharacterMap({32:'space',65:'A',72:'H'});fb.setupGlyf(glyphs);fb.setupHorizontalMetrics({g:(600,0) for g in glyphs});fb.setupHorizontalHeader(ascent=800,descent=-200)
    fb.setupNameTable({'familyName':'Kestrel Synthetic Test','styleName':'Regular','uniqueFontIdentifier':'KestrelSyntheticTest-Regular','fullName':'Kestrel Synthetic Test','psName':'KestrelSyntheticTest-Regular'});fb.setupOS2(sTypoAscender=800,sTypoDescender=-200,usWinAscent=800,usWinDescent=200);fb.setupPost();fb.setupMaxp();out=BytesIO();fb.save(out);return out.getvalue()
stroke=bytes(json.loads(subprocess.check_output(['node','-e',"console.log(JSON.stringify([...require('./tests/font-fixture').fixture()]))"],cwd=ROOT,text=True)))
results=[];errors=[]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1600,'height':1000},accept_downloads=True);page.on('pageerror',lambda e:errors.append(str(e)));page.set_default_timeout(15000)
    if os.environ.get('KESTREL_TEST_URL'):page.goto(os.environ['KESTREL_TEST_URL'],wait_until='domcontentloaded')
    else:page.set_content((ROOT/'Kestrel-CAD.html').read_text(),wait_until='domcontentloaded')
    page.wait_for_function('document.documentElement.dataset.ready==="true"')
    def test(name,fn):
        before=len(errors)
        try:fn();assert len(errors)==before,errors[before:];results.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
        except Exception as e:traceback.print_exc();results.append({'name':name,'status':'failed','error':str(e)});page.evaluate('kestrel.closeDialog()')
    def ev(js):return page.evaluate(js)
    def action(id):page.evaluate('(id)=>kestrel.run(id)',id)
    def close():ev('kestrel.closeDialog()')
    def select():ev('kestrel.doc.selection=new Set([kestrel.doc.entities[0].id]);kestrel.selectionChanged()')
    def submit(fields={}):
        for k,v in fields.items():
            el=page.locator('#modal [name="'+k+'"]')
            if isinstance(v,bool):el.set_checked(v)
            elif el.evaluate('(e)=>e.tagName')=='SELECT':el.select_option(str(v))
            else:el.fill(str(v))
        page.locator('#modal-submit').click();page.wait_for_timeout(60);assert not page.locator('#modal-error').is_visible(),page.locator('#modal-error').inner_text()
    def setup():
        ev("(()=>{const d=new Kestrel.Drawing('Text fidelity');d.currentLayer='0';kestrel.addDocument(d);})()")
        page.locator('[data-ribbon="Text"]').click();page.locator('#ribbon [data-action="text-styles"]').click();submit({'name':'Engineering','font':'synthetic.shx','width':1,'height':0})
        assert ev('kestrel.doc.production.currentTextStyle')=='Engineering'
        ev("kestrel.doc.transaction('text fixture',()=>kestrel.doc.add('TEXT',{position:[0,0,0],height:30,text:'AA',textStyle:'Engineering'}));kestrel.run('fit')");select()
    test('Text ribbon creates persisted current text style',setup)
    def missing():
        action('font-report');assert 'Missing font' in page.locator('#modal').inner_text();close()
        assert ev('kestrel.doc.geometry(kestrel.doc.entities[0]).segments.length')==10
    test('missing SHX font is explicit and produces placeholders',missing)
    def load(name,buffer):
        with page.expect_file_chooser() as chooser:action('font-load')
        chooser.value.set_files({'name':name,'mimeType':'application/octet-stream','buffer':buffer})
        page.wait_for_function("document.querySelector('#modal-title')?.textContent==='Font dependencies'");close()
    def shx():
        load('synthetic.shx',stroke)
        assert ev('kestrel.doc.geometry(kestrel.doc.entities[0]).segments.length')==4
        assert ev('Kestrel.Fonts.report(kestrel.doc).length')==0
    test('real file chooser loads SHX and invalidates existing cached text geometry',shx)
    def edit():
        ev('kestrel.textDialog(kestrel.doc.entities[0])');submit({'widthFactor':2,'oblique':30,'text':'AAA','backwards':True})
        e=ev('kestrel.doc.entities[0]');assert e['widthFactor']==2 and e['oblique']==30 and e['backwards']
        assert ev('kestrel.doc.geometry(kestrel.doc.entities[0]).segments.length')==6
        action('undo');assert ev('kestrel.doc.entities[0].text')=='AA';action('redo');assert ev('kestrel.doc.entities[0].text')=='AAA'
    test('text dialog edits real typography with atomic undo redo',edit)
    def apply():
        select();action('text-style-apply');submit({'style':'Engineering'});assert ev('kestrel.doc.entities[0].widthFactor===undefined')
        assert ev('kestrel.doc.geometry(kestrel.doc.entities[0]).segments.length')==6
    test('Apply style clears explicit overrides without flattening text',apply)
    def svg():
        action('export-svg')
        with page.expect_download() as dl:page.locator('#modal-submit').click()
        text=Path(dl.value.path()).read_text();assert '<path' in text and '>AAA<' not in text
    test('actual SVG download contains self-contained stroke geometry',svg)
    def native():
        with page.expect_download() as dl:action('save')
        data=json.loads(Path(dl.value.path()).read_text());assert data['production']['textstyles'][1]['font']=='synthetic.shx';assert 'glyphs' not in json.dumps(data)
    test('native download preserves style references without embedding font bytes',native)
    def copy():
        select();ev('kestrel.copyClipboard()');ev("kestrel.addDocument(new Kestrel.Drawing('Copy destination'));kestrel.pasteClipboard();kestrel.acceptPoint([100,0,0]);")
        e=ev('kestrel.doc.entities[0]');assert ev('Kestrel.Fonts.style(kestrel.doc,kestrel.doc.entities[0].textStyle).font')=='synthetic.shx'
        assert ev('kestrel.doc.geometry(kestrel.doc.entities[0]).segments.length')==6
    test('clipboard transfers font styles with independent geometry',copy)
    def ttf():
        load('synthetic.ttf',outline());font=ev("(()=>{const f=Kestrel.Fonts.registry.get('synthetic.ttf');return {kind:f.kind,family:f.exportFamily}})()")
        assert font=={'kind':'outline','family':'Kestrel Synthetic Test'}
        action('text-styles');submit({'name':'Outline','font':'synthetic.ttf','width':1,'height':0});select();action('text-style-apply');submit({'style':'Outline'})
        t=ev('kestrel.doc.geometry(kestrel.doc.entities[0]).texts[0]');assert t['fontFamily'].startswith('KestrelUserFont') and abs(t['fontEm']-1/.7)<.01
        assert 'Kestrel Synthetic Test' in ev('Kestrel.Exchange.writeSVG(kestrel.doc)')
    test('real outline FontFace loading measures cap height and preserves actual family name',ttf)
    def validation():
        action('text-styles');page.locator('#modal summary').click();page.locator('#modal [name="advanced"]').check();bad=ev('JSON.stringify([{name:"STANDARD",font:"",height:0,width:0}])');page.locator('#modal [name="definitions"]').fill(bad);before=ev('kestrel.doc.snapshot()');page.locator('#modal-submit').click();assert page.locator('#modal-error').is_visible();assert ev('kestrel.doc.snapshot()')==before;close()
    test('invalid style edits reject and preserve drawing/history',validation)
    def frame():
        action('fit');page.wait_for_timeout(150);page.screenshot(path=str(OUT/'font-styles.png'));assert ev('kestrel.renderer.texts.length')>0
    test('font-backed annotations render in the running editor',frame)
    browser.close()
failed=sum(r['status']=='failed' for r in results)
(OUT/'fonts-browser-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'tests':results,'javascript_errors':errors},indent=2)+'\n')
print('RESULT',len(results)-failed,'passed;',failed,'failed; JS errors:',errors);raise SystemExit(bool(failed or errors))
