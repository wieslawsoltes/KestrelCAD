#!/usr/bin/env python3
"""Real chooser, source fidelity dialogs, browser downloads and history integration."""
from pathlib import Path
import json,os,subprocess,traceback
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'tests/results';OUT.mkdir(exist_ok=True)
node="for(const f of ['math','geometry','model','exchange','production','kernel','constraints','dynamic-blocks','fonts','source-archive'])require('./src/'+f+'.js');const d=new Kestrel.Drawing('Source');d.currentLayer='0';d.add('LINE',{points:[[0,0,0],[10,0,0]]});d.add('CIRCLE',{center:[30,0,0],radius:5});process.stdout.write(Kestrel.Exchange.writeDXF(d));"
raw=subprocess.check_output(['node','-e',node],cwd=ROOT)
results=[];errors=[]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1600,'height':1000},accept_downloads=True);page.on('pageerror',lambda e:errors.append(str(e)));page.set_default_timeout(15000)
    page.set_content((ROOT/'Kestrel-CAD.html').read_text(),wait_until='domcontentloaded');page.wait_for_function('document.documentElement.dataset.ready==="true"')
    def ev(js):return page.evaluate(js)
    def action(id):page.evaluate('(id)=>kestrel.run(id)',id)
    def close():ev('kestrel.closeDialog()')
    def open_source(data,name='source.dxf'):
        page.locator('#file-input').set_input_files({'name':name,'mimeType':'application/octet-stream','buffer':data})
        page.wait_for_function('Kestrel.SourceArchive.has(kestrel.doc)');page.wait_for_function('document.querySelector("#modal").open');close()
    def test(name,fn):
        before=len(errors)
        try:fn();assert len(errors)==before,errors[before:];results.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
        except Exception as error:traceback.print_exc();results.append({'name':name,'status':'failed','error':str(error)});close()
    def download(action_id,submit=False):
        with page.expect_download() as info:
            action(action_id)
            if submit:page.locator('#modal-submit').click()
        return Path(info.value.path()).read_bytes()
    def imported():
        open_source(raw);assert ev('kestrel.doc.entities.length')==2;assert ev('Kestrel.SourceArchive.evaluate(kestrel.doc).unchanged')
        page.locator('[data-ribbon="Exchange"]').click();page.locator('#ribbon [data-action="source-report"]').click();assert 'Available' in page.locator('#modal').inner_text();close()
    test('real DXF chooser imports geometry plus immutable source and report',imported)
    def original():assert download('source-original')==raw
    test('original browser download matches every imported byte',original)
    def preserved():assert download('source-save',True)==raw
    test('source-preserving export is an actual byte-identical DXF download',preserved)
    def edit():
        ev("kestrel.doc.transaction('move',()=>kestrel.doc.transform([kestrel.doc.entities[0].id],Kestrel.Math.M.translation(12,0,0)))")
        output=download('source-save',True);assert output!=raw;assert b'12\n' in output
        assert ev('kestrel.doc.undoStack[0].state.includes("sourceArchiveRef")');assert not ev('kestrel.doc.undoStack[0].state.includes("baseline")')
        assert download('source-original')==raw;action('undo');assert download('source-save',True)==raw;action('redo')
    test('source edits patch records while undo and original recovery remain independent',edit)
    def native():
        data=json.loads(download('save'));assert data['sourceArchive']['format']=='dxf-ascii';assert 'sourceArchiveRef' not in data
        page.evaluate('(data)=>{window.archived=Kestrel.Drawing.from(data);}',data);assert ev('Kestrel.SourceArchive.has(archived)')
    test('native save carries the complete source rather than ephemeral history IDs',native)
    def blocked():
        ev("kestrel.doc.transaction('ellipse',()=>kestrel.doc.transform([kestrel.doc.entities[1].id],Kestrel.Math.M.scale(2,1,1)))")
        action('source-save');assert page.locator('[name="mode"][value="source"]').is_disabled();assert 'Entity-type conversion' in page.locator('#modal').inner_text()
        with page.expect_download() as info:page.locator('#modal-submit').click()
        assert b'ELLIPSE' in Path(info.value.path()).read_bytes();action('undo')
    test('unsafe source edit blocks preserve mode and offers an explicit converted export',blocked)
    def binary():
        encoded=download('dxf-binary',True);assert encoded.startswith(b'AutoCAD Binary DXF\r\n\x1a\x00');action('new');open_source(encoded,'binary.dxf')
        assert ev('Kestrel.SourceArchive.evaluate(kestrel.doc).format')=='dxf-binary';assert download('source-save',True)==encoded
    test('binary DXF export and file chooser round trip preserve original binary bytes',binary)
    def detached():
        action('new');assert not ev('Kestrel.SourceArchive.has(kestrel.doc)');action('source-report');assert 'no source archive' in ev('document.body.innerText').lower()
    test('new drawings never inherit another document original source',detached)
    page.screenshot(path=str(OUT/'source-archive.png'));browser.close()
failed=sum(t['status']=='failed' for t in results);(OUT/'source-archive-browser-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'javascript_errors':errors,'tests':results},indent=2));print('RESULT',len(results)-failed,'passed;',failed,'failed; JS errors:',errors);raise SystemExit(bool(failed or errors))
