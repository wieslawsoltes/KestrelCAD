#!/usr/bin/env python3
"""Real served editor + real local OCCT subprocess, not synthetic bridge replies."""
from pathlib import Path
import base64,io,json,os,socket,subprocess,sys,time,traceback,urllib.request
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'tests/results';OUT.mkdir(exist_ok=True);sys.path.insert(0,str(ROOT/'tools'))
import kernel as K
import cadquery as cq
results=[];errors=[]
sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
server=subprocess.Popen([sys.executable,str(ROOT/'tools/serve.py'),'--port',str(port)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
url=f'http://127.0.0.1:{port}/'
box=cq.Solid.makeBox(10,10,10)
fixture=[K.pack(box,.1),K.pack(box.translate((5,0,0)),.1),K.pack(box.translate((17,0,0)),.1)]
try:
    for _ in range(100):
        try:urllib.request.urlopen(url,timeout=1);break
        except OSError:time.sleep(.05)
    with sync_playwright() as p:
        b=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
        page=b.new_page(viewport={'width':1600,'height':1050},accept_downloads=True);page.set_default_timeout(65000)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(url,wait_until='domcontentloaded');page.wait_for_function('document.documentElement.dataset.ready==="true"')
        def action(s):page.evaluate('(s)=>kestrel.run(s)',s)
        def setup():
            action('new')
            page.evaluate('(items)=>{const d=kestrel.doc;d.transaction("Native fixture",()=>{for(const item of items)d.add(Kestrel.Kernel.body(item));d.selection=new Set(d.entities.map(e=>e.id));});kestrel.selectionChanged();kestrel.fit(false);kestrel.autosave();}',fixture)
        def analyze():
            page.locator('#analysis-run').click();page.wait_for_function('!document.querySelector("#analysis-run").disabled')
            assert not page.locator('#modal-error').is_visible(),page.locator('#modal-error').inner_text()
        def test(name,fn):
            before=len(errors)
            try:fn();assert len(errors)==before,errors[before:];results.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
            except Exception as e:traceback.print_exc();results.append({'name':name,'status':'failed','error':str(e)});page.evaluate('kestrel.closeDialog();kestrel.cancel(false)')
        def report():
            setup();snapshot=page.evaluate('kestrel.doc.snapshot()');history=page.evaluate('kestrel.doc.undoStack.length')
            page.locator('[data-ribbon="Solids"]').click();page.locator('[data-action="native-interference"]').first.click();page.locator('[name="clearance"]').fill('3');analyze()
            assert '3 pairs' in page.locator('#analysis-results').inner_text()
            assert '1 overlaps' in page.locator('#analysis-results').inner_text()
            assert '1 clearance violations' in page.locator('#analysis-results').inner_text()
            assert page.evaluate('kestrel.doc.snapshot()')==snapshot
            assert page.evaluate('kestrel.doc.undoStack.length')==history
        test('Solids ribbon reports actual overlaps and gaps without document edits',report)
        def download():
            with page.expect_download() as dl:page.locator('#analysis-download').click()
            data=json.loads(Path(dl.value.path()).read_text());assert data['units']=='mm'
            assert data['counts']['interference']==1 and abs(data['pairs'][0]['volume']-500)<1e-5
            assert 'bodies' not in data and len(data['entities'])==3
        test('JSON download labels the exact source IDs and units',download)
        def focus():
            page.locator('[name="analysis-pair"][value="2"]').check();page.locator('#analysis-focus').click()
            assert page.evaluate('kestrel.doc.selection.size')==2
        test('Focus pair selects original bodies without manufacturing geometry',focus)
        def retain():
            original=page.evaluate('JSON.stringify(kestrel.doc.entities)');page.locator('#modal-submit').click();page.wait_for_function('!document.querySelector("#modal").open')
            assert page.evaluate('kestrel.doc.entities.length')==4
            assert abs(page.evaluate('kestrel.doc.entities[3].solid.volume')-500)<1e-5
            assert page.evaluate('JSON.stringify(kestrel.doc.entities.slice(0,3))')==original
            action('undo');assert page.evaluate('kestrel.doc.entities.length')==3
            action('redo');assert page.evaluate('kestrel.doc.entities.length')==4
        test('Retain overlap creates independent native solids with undo redo',retain)
        def native_save():
            with page.expect_download() as dl:action('save')
            data=json.loads(Path(dl.value.path()).read_text());assert data['entities'][-1]['solid']['brep']
            page.evaluate('(d)=>kestrel.addDocument(Kestrel.Drawing.from(d))',data)
            assert abs(page.evaluate('kestrel.doc.entities.at(-1).solid.volume')-500)<1e-5
        test('Saved project reopens retained BREP region',native_save)
        def sets():
            setup();action('CLEARANCE');page.locator('[name="mode"]').select_option('sets')
            page.locator('[name="first1"]').check();page.locator('[name="second1"]').check();analyze()
            assert '2 pairs' in page.locator('#analysis-results').inner_text()
            assert '0 overlaps' in page.locator('#analysis-results').inner_text()
            assert page.locator('#modal-submit').is_disabled()
        test('Two sets suppress duplicate membership and omit within-set overlap',sets)
        def gap():
            page.locator('[name="analysis-pair"][value="1"]').check();page.locator('#analysis-gap').click();page.wait_for_function('!document.querySelector("#modal").open')
            assert page.evaluate('kestrel.doc.entities.at(-1).type')=='LINE'
            assert abs(page.evaluate('Kestrel.Math.V.dist(...kestrel.doc.entities.at(-1).points)')-2)<1e-6
            action('undo');assert page.evaluate('kestrel.doc.entities.length')==3
        test('Retain gap line uses actual closest points and undo',gap)
        def readonly():
            setup();page.evaluate('kestrel.doc.layer(kestrel.doc.entities[0]).locked=true');action('INTERFERE');analyze()
            assert '1 overlaps' in page.locator('#analysis-results').inner_text()
            snapshot=page.evaluate('kestrel.doc.snapshot()');page.locator('#modal-submit').click();page.wait_for_function('!document.querySelector("#modal-error").hidden')
            assert 'unlocked' in page.locator('#modal-error').inner_text();assert page.evaluate('kestrel.doc.snapshot()')==snapshot
            page.evaluate('kestrel.closeDialog()')
        test('Locked sources can be read but locked current layer cannot receive regions',readonly)
        def stale():
            setup();action('INTERFERE');analyze();page.evaluate('kestrel.doc.transaction("Other edit",()=>kestrel.doc.add("POINT",{position:[30,40,50]}))')
            snapshot=page.evaluate('kestrel.doc.snapshot()');page.locator('#modal-submit').click();page.wait_for_function('!document.querySelector("#modal-error").hidden')
            assert 'changed' in page.locator('#modal-error').inner_text();assert page.evaluate('kestrel.doc.snapshot()')==snapshot;page.evaluate('kestrel.closeDialog()')
        test('Stale results cannot be retained over a newer edit',stale)
        def change():
            setup();action('INTERFERE');analyze();page.locator('[name="clearance"]').fill('5')
            assert page.locator('#modal-submit').is_disabled();assert page.locator('#analysis-download').count()==0
            analyze();assert '1 clearance violations' in page.locator('#analysis-results').inner_text()
        test('Changing analysis controls invalidates prior results',change)
        def no_regions():
            page.locator('[name="regions"]').uncheck();analyze();assert page.locator('#modal-submit').is_disabled()
            assert page.locator('#analysis-download').is_visible();page.evaluate('kestrel.closeDialog()')
        test('Report-only analysis does not create native result bodies',no_regions)
        def empty_sets():
            setup();action('INTERFERE');page.locator('[name="mode"]').select_option('sets')
            page.locator('[name="second1"]').uncheck();page.locator('[name="second2"]').uncheck()
            page.locator('#analysis-run').click();page.wait_for_function('!document.querySelector("#modal-error").hidden')
            assert page.evaluate('kestrel.doc.entities.length')==3;page.locator('[name="second1"]').check();analyze()
        test('Invalid groups reject and can be corrected in the same form',empty_sets)
        page.screenshot(path=str(OUT/'native-analysis.png'));b.close()
finally:server.terminate();server.wait(timeout=5)
failed=sum(t['status']=='failed' for t in results)
(OUT/'native-analysis-browser-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'javascript_errors':errors,'tests':results},indent=2)+'\n')
print('RESULT',len(results)-failed,'passed;',failed,'failed;',errors);sys.exit(bool(failed or errors))
