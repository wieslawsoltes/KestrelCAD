#!/usr/bin/env python3
"""Served-browser native editing tests against the actual local OCCT subprocess."""
from pathlib import Path
import json, os, socket, subprocess, sys, time, traceback, urllib.request
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'tests/results';OUT.mkdir(exist_ok=True)
sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
server=subprocess.Popen([sys.executable,str(ROOT/'tools/serve.py'),'--port',str(port)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
url=f'http://127.0.0.1:{port}/';results=[];errors=[]
try:
    for _ in range(100):
        try:urllib.request.urlopen(url,timeout=1);break
        except OSError:time.sleep(.05)
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1600,'height':1000},accept_downloads=True);page.set_default_timeout(65000)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(url,wait_until='domcontentloaded');page.wait_for_function('document.documentElement.dataset.ready==="true"')
        def action(id):page.evaluate('(id)=>kestrel.run(id)',id)
        def submit(fields=None):
            for key,value in (fields or {}).items():
                el=page.locator('#modal [name="'+key+'"]')
                if el.evaluate('(e)=>e.tagName')=='SELECT':el.select_option(str(value))
                else:el.fill(str(value))
            page.locator('#modal-submit').click();page.wait_for_function('!document.querySelector("#modal").open || !document.querySelector("#modal-error").hidden')
            assert not page.locator('#modal-error').is_visible(),page.locator('#modal-error').inner_text()
        def test(name,fn):
            before=len(errors)
            try:fn();assert len(errors)==before,errors[before:];results.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
            except Exception as e:traceback.print_exc();results.append({'name':name,'status':'failed','error':str(e)});page.evaluate('kestrel.closeDialog();kestrel.cancel(false)')
        def select(index=0):page.evaluate('(i)=>{kestrel.doc.selection=new Set([kestrel.doc.entities[i].id]);kestrel.selectionChanged()}',index)
        def setup():
            action('new');action('solid-box');submit({'width':20,'depth':30,'height':10})
            page.evaluate("kestrel.doc.transaction('appearance',()=>{kestrel.doc.entities[0].color='#dd8877';kestrel.doc.entities[0].lineweight=.5;})")
        setup()
        def slicing():
            select();page.locator('[data-ribbon="Solids"]').click();page.locator('#ribbon [data-action="solid-slice"]').click();submit({'origin':'10,0,0','normal':'1,0,0','keep':'both'})
            assert page.evaluate("kestrel.doc.entities.length===2 && kestrel.doc.entities.every(e=>Math.abs(e.solid.volume-3000)<1e-6 && e.color==='#dd8877' && e.lineweight===.5)")
            assert page.evaluate('Kestrel.Drawing.from(kestrel.doc.serialize()).entities.length')==2
            action('undo');assert page.evaluate('kestrel.doc.entities.length')==1
            action('redo');assert page.evaluate('kestrel.doc.entities.length')==2
            action('undo')
        test('Slice ribbon command keeps both halves, properties, persistence and atomic undo',slicing)
        def failure():
            select();action('solid-slice');page.locator('#modal [name="origin"]').fill('1000,0,0');page.locator('#modal [name="normal"]').fill('1,0,0');page.locator('#modal-submit').click()
            page.wait_for_function('!document.querySelector("#modal-error").hidden')
            assert page.evaluate('kestrel.doc.entities.length')==1;assert page.evaluate('kestrel.doc.entities[0].solid.volume')==6000
            page.evaluate('kestrel.closeDialog()')
        test('failed native slice leaves the complete original body intact',failure)
        def massprops():
            select();action('solid-massprops')
            with page.expect_download() as download:submit({'density':2.5})
            data=json.loads(Path(download.value.path()).read_text());assert data['mass']==15000;assert data['centroid']==[10,15,5]
            assert abs(data['inertia'][0][0]-1250000)<1e-6
        test('MASSPROP downloads real centroid and inertia from the transformed native body',massprops)
        def extract():
            select();action('solid-extract-faces');submit({'indices':'5'})
            assert page.evaluate('kestrel.doc.entities.length')==2
            assert page.evaluate("kestrel.doc.entities[1].solid.solidCount===0 && kestrel.doc.entities[1].color==='#dd8877'")
            action('solid-thicken');submit({'thickness':2})
            assert abs(page.evaluate('kestrel.doc.entities[1].solid.volume')-1200)<1e-6
            action('undo');assert page.evaluate('kestrel.doc.entities[1].solid.solidCount')==0
        test('face extraction retains original and THICKEN creates an undoable solid',extract)
        def surface():
            action('new');page.evaluate("const d=kestrel.doc;d.transaction('profile',()=>{let e=d.add('CIRCLE',{center:[0,0,0],radius:10});d.selection=new Set([e.id]);});kestrel.selectionChanged()")
            action('solid-plane-surface');submit();assert page.evaluate('kestrel.doc.entities.length')==2
            assert page.evaluate('kestrel.doc.entities[1].solid.solidCount')==0
            action('solid-thicken');submit({'thickness':3});assert abs(page.evaluate('kestrel.doc.entities[1].solid.volume')-300*3.141592653589793)<1e-5
        test('closed circle to native planar surface to analytic solid workflow',surface)
        def stale():
            select(1);action('solid-slice');page.evaluate("kestrel.doc.transaction('other edit',()=>kestrel.doc.add('POINT',{position:[40,0,0]}))")
            page.locator('#modal-submit').click();page.wait_for_function('!document.querySelector("#modal-error").hidden')
            assert 'changed' in page.locator('#modal-error').inner_text().lower();assert page.evaluate('kestrel.doc.entities.length')==3
            page.evaluate('kestrel.closeDialog()')
        test('native dialog rejects stale topology instead of overwriting a newer edit',stale)
        page.screenshot(path=str(OUT/'native-surface-workflow.png'));browser.close()
finally:server.terminate();server.wait(timeout=5)
failed=sum(r['status']=='failed' for r in results)
(OUT/'native-edit-browser-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'javascript_errors':errors,'tests':results},indent=2))
print('RESULT',len(results)-failed,'passed;',failed,'failed; JS errors:',errors);sys.exit(bool(failed or errors))
