#!/usr/bin/env python3
"""Real local native-bridge browser integration. No simulated kernel responses."""
from pathlib import Path
import json,os,socket,subprocess,sys,time,traceback,urllib.request
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'tests/results';OUT.mkdir(exist_ok=True)
results=[];errors=[]
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
url=f'http://127.0.0.1:{port}/'
server=subprocess.Popen([sys.executable,str(ROOT/'tools/serve.py'),'--port',str(port)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
    for _ in range(100):
        try:urllib.request.urlopen(url+'api/capabilities',timeout=1);break
        except OSError:time.sleep(.05)
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1600,'height':1000},accept_downloads=True)
        page.on('pageerror',lambda e:errors.append(str(e)));page.set_default_timeout(65000)
        page.goto(url,wait_until='domcontentloaded');page.wait_for_function('document.documentElement.dataset.ready==="true"')
        def test(name,fn):
            before=len(errors)
            try:fn();assert len(errors)==before,errors[before:];results.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
            except Exception as e:traceback.print_exc();results.append({'name':name,'status':'failed','error':str(e)});page.evaluate('kestrel.closeDialog();kestrel.cancel(false)')
        def action(x):page.evaluate('(id)=>kestrel.run(id)',x)
        # Undo intentionally clears selection; each independent operation reselects its body.
        def select_body():page.evaluate('kestrel.doc.selection = new Set([kestrel.doc.entities[0].id]); kestrel.selectionChanged()')
        def submit(fields={}):
            for key,value in fields.items():
                el=page.locator('#modal [name="'+key+'"]')
                if el.evaluate('(e)=>e.tagName')=='SELECT':el.select_option(str(value))
                else:el.fill(str(value))
            page.locator('#modal-submit').click();page.wait_for_function('!document.querySelector("#modal").open || document.querySelector("#modal-error").textContent.length>0')
            assert not page.locator('#modal-error').is_visible(),page.locator('#modal-error').inner_text()
        def box():
            action('new');page.locator('[data-ribbon="Solids"]').click();page.locator('#ribbon [data-action="solid-box"]').click();submit({'width':20,'depth':30,'height':10})
            assert abs(page.evaluate('kestrel.doc.entities[0].solid.volume')-6000)<1e-6
            assert page.evaluate('kestrel.doc.entities[0].solid.provider')=='OCCT'
        test('Solids ribbon creates a real B-rep box through localhost',box)
        def fillet():
            select_body();action('solid-fillet');submit({'indices':'0','size':2});assert page.evaluate('kestrel.doc.entities[0].solid.faces.length')==7
            action('undo');assert page.evaluate('kestrel.doc.entities[0].solid.faces.length')==6
        test('native fillet dialog edits topology with atomic undo',fillet)
        def chamfer():select_body();action('solid-chamfer');submit({'indices':'0','size':2});assert abs(page.evaluate('kestrel.doc.entities[0].solid.volume')-5980)<1e-5;action('undo')
        test('native chamfer runs the actual kernel',chamfer)
        def shell():select_body();action('solid-shell');submit({'indices':'5','size':-1});assert abs(page.evaluate('kestrel.doc.entities[0].solid.volume')-1464)<1e-5;action('undo')
        test('native shell removes selected face and hollows body',shell)
        def step():
            select_body();action('solid-export')
            with page.expect_download() as download:submit({'format':'step'})
            data=Path(download.value.path()).read_bytes();assert b'ISO-10303-21' in data;assert len(data)>1000
        test('STEP export downloads actual solid exchange data',step)
        def persist():assert page.evaluate('Kestrel.Drawing.from(kestrel.doc.serialize()).entities[0].solid.brep===kestrel.doc.entities[0].solid.brep')
        test('native solid project persistence',persist)
        def detach():select_body();action('solid-detach');submit();assert page.evaluate('!kestrel.doc.entities[0].solid');action('undo');assert page.evaluate('!!kestrel.doc.entities[0].solid')
        test('explicit mesh conversion and undo',detach)
        def security():
            assert page.request.post(url+'api/kernel',data={'op':'box'}).status==403
            assert page.request.post(url+'api/kernel',headers={'X-Kestrel-Client':'1','Origin':'https://untrusted.example'},data={'op':'box'}).status==403
            assert page.request.post(url+'api/kernel',headers={'X-Kestrel-Client':'1'},data={'op':'unknown'}).status==422
        test('native API rejects untrusted origins, missing headers and unknown operations',security)
        page.evaluate('kestrel.setRibbon("Solids");kestrel.fit(false)');page.screenshot(path=str(OUT/'native-solids.png'));browser.close()
finally:
    server.terminate();server.wait(timeout=5)
failed=sum(r['status']=='failed' for r in results)
(OUT/'advanced-browser-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'javascript_errors':errors,'tests':results},indent=2)+'\n')
print(f'Native browser: {len(results)-failed} passed; {failed} failed; JS errors: {errors}')
raise SystemExit(bool(failed or errors))
