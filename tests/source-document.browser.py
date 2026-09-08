#!/usr/bin/env python3
"""Actual file chooser, worker, fidelity UI, native persistence and downloads."""
from pathlib import Path
import json, os, subprocess, sys, traceback
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'tests/results';OUT.mkdir(exist_ok=True)
# Produce only original synthetic drawing geometry and opaque drawing metadata.
script="""
for(const m of ['math','geometry','model','exchange','production','kernel','constraints','dynamic-blocks','fonts','source-document'])require('./src/'+m+'.js');
const K=globalThis.Kestrel,d=new K.Drawing('Source browser');d.add('LINE',{points:[[0,0,0],[100,0,0]],layer:'0'});d.reindex();
const s=K.Exchange.writeDXF(d).replace('AC1015','AC1021').replace('0\\nEOF\\n','0\\nSECTION\\n2\\nOBJECTS\\n0\\nACAD_PROXY_OBJECT\\n5\\nFAFF\\n1\\nOpaque application data\\n310\\nDEADBEEF0001\\n0\\nENDSEC\\n0\\nEOF\\n');
console.log(JSON.stringify({ascii:s,binary:[...K.SourceDocument.toBinary(s)]}));
"""
fixtures=json.loads(subprocess.check_output(['node','-e',script],cwd=ROOT,text=True));raw=fixtures['ascii'].encode();binary=bytes(fixtures['binary']);results=[];errors=[]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1600,'height':1000},accept_downloads=True);page.set_default_timeout(20000);page.on('pageerror',lambda e:errors.append(str(e)))
    if os.environ.get('KESTREL_TEST_URL'):page.goto(os.environ['KESTREL_TEST_URL'],wait_until='domcontentloaded')
    else:page.set_content((ROOT/'Kestrel-CAD.html').read_text(),wait_until='domcontentloaded')
    page.wait_for_function('document.documentElement.dataset.ready==="true"')
    def ev(js,arg=None):return page.evaluate(js,arg)
    def action(id):return ev('(id)=>kestrel.run(id)',id)
    def close():ev('kestrel.closeDialog()')
    def download(id):
        # Keep UI-driven exports distinct rather than flood the browser download queue.
        page.wait_for_timeout(250)
        with page.expect_download() as got:
            alias=ev('(id)=>Kestrel.UI.get(id).alias.split(/[ ·]/)[0]',id)
            page.locator('#command-input').fill(alias);page.locator('#command-input').press('Enter')
        return Path(got.value.path()).read_bytes()
    def open_file(name,data):
        close();action('open');page.locator('#file-input').set_input_files({'name':name,'mimeType':'application/octet-stream','buffer':data})
        page.wait_for_function('(name)=>kestrel.doc.name===name',arg=name.rsplit('.',1)[0])
    def test(name,fn):
        before=len(errors)
        try:fn();assert len(errors)==before,errors[before:];results.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
        except Exception as e:traceback.print_exc();print('HISTORY',page.locator('#command-history').inner_text()[-2500:]);results.append({'name':name,'status':'failed','error':str(e)});close()
    def opening():
        open_file('preserved.dxf',raw);page.wait_for_function('document.querySelector("#modal").open && document.querySelector("#modal-title").textContent==="DXF import report"')
        assert ev('!!kestrel.doc.sourceDocument && kestrel.doc.entities.length===1');assert 'retained' in page.locator('#modal-body').inner_text();close()
    test('file chooser and worker retain original source and display unsupported-record warning',opening)
    def original():
        assert download('source-original')==raw
        assert download('export-dxf')==raw
    test('original and unchanged DXF UI downloads match every input byte',original)
    def move():
        ev('kestrel.doc.selection=new Set([kestrel.doc.entities[0].id]);kestrel.selectionChanged()')
        page.locator('#command-input').fill('MOVE 0,0 20,30');page.locator('#command-input').press('Enter')
        page.wait_for_function('kestrel.doc.entities[0].points[0][0]===20')
        edited=download('export-dxf');assert b'Opaque application data' in edited and edited!=raw
        restored=ev('(text)=>Kestrel.Exchange.parseDXF(text).data.entities[0].points',edited.decode());assert restored==[[20,30,0],[120,30,0]]
        (OUT/'browser-source-preserved.dxf').write_bytes(edited)
        assert download('source-original')==raw
    test('command-line MOVE saves edited geometry while keeping opaque original records',move)
    def undo():
        action('undo');assert download('source-preserved')==raw;action('redo');assert download('source-preserved')!=raw
        assert ev('kestrel.doc.undoStack.every(x=>!x.state.includes("sourceDocument"))')
    test('undo/redo retain provenance without copying archive bytes into history',undo)
    def persistence():
        native=download('save');assert json.loads(native)['sourceDocument']['format']=='dxf'
        # The saved project name is independent of the chosen file name.
        close();action('new');action('open');page.locator('#file-input').set_input_files({'name':'archived.kcad','mimeType':'application/json','buffer':native})
        page.wait_for_function('kestrel.doc.name==="preserved" && !!kestrel.doc.sourceDocument')
        assert download('source-original')==raw;assert b'Opaque application data' in download('source-preserved')
    test('downloaded native project restores both edited geometry and unedited source',persistence)
    def report():
        page.locator('[data-ribbon="Exchange"]').click();page.locator('#ribbon [data-action="source-info"]').click()
        assert 'Edited native drawing' in page.locator('#modal-body').inner_text();assert 'retained' in page.locator('#modal-body').inner_text().lower();close()
    test('Exchange ribbon exposes actual archive and editing-state information',report)
    def refusal():
        ev("kestrel.doc.transaction('Unsupported metadata',()=>kestrel.doc.entities[0].group='native-only')")
        before=ev('kestrel.doc.snapshot()');downloads=[];listener=lambda d:downloads.append(d);page.on('download',listener)
        action('source-preserved');assert 'group' in page.locator('#command-history').inner_text();assert not downloads;page.remove_listener('download',listener)
        assert ev('kestrel.doc.snapshot()')==before;action('undo')
    test('unsafe export produces no file and does not modify the drawing',refusal)
    def compatibility():
        action('source-compatible');assert 'supported content only' in page.locator('#modal-body').inner_text();assert not ev('document.querySelector("#modal-form").checkValidity()')
        page.locator('#modal [name="acknowledge"]').check()
        with page.expect_download() as got:page.locator('#modal-submit').click()
        data=Path(got.value.path()).read_bytes();assert b'Opaque application data' not in data;assert b'LINE' in data
    test('lossy compatibility export requires explicit acknowledgement',compatibility)
    def binary_read():
        open_file('binary.dxf',binary);page.wait_for_function('document.querySelector("#modal").open && document.querySelector("#modal-title").textContent==="DXF import report"');close()
        assert ev('kestrel.doc.sourceDocument.binary');assert download('export-dxf')==binary
    test('binary DXF file chooser imports and reproduces the actual binary file',binary_read)
    def binary_write():
        action('new');page.locator('#command-input').fill('LINE 0,0 50,0 ENTER');page.locator('#command-input').press('Enter');page.wait_for_function('kestrel.doc.entities.length===1')
        data=download('source-binary');assert data.startswith(b'AutoCAD Binary DXF\r\n\x1a\0')
        assert ev('(b)=>Kestrel.Exchange.parseDXF(new Uint8Array(b)).data.entities.length',list(data))==1
    test('binary export creates real typed DXF records, not a renamed text file',binary_write)
    page.screenshot(path=str(OUT/'source-document-ui.png'));browser.close()
failed=sum(r['status']=='failed' for r in results)
(OUT/'source-document-browser-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'javascript_errors':errors,'tests':results},indent=2))
print('Source browser:',len(results)-failed,'passed;',failed,'failed; JS errors:',errors);sys.exit(bool(failed or errors))
