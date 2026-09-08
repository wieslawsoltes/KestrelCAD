#!/usr/bin/env python3
"""Real browser file workflows backed by the actual local OCCT worker."""
from pathlib import Path
import json,os,socket,subprocess,sys,time,traceback,urllib.request
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'tests/results';OUT.mkdir(exist_ok=True);sys.path.insert(0,str(ROOT/'tools'))
import cadquery as cq
import acis_exchange as A
import ezdxf
results=[];errors=[]
sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
server=subprocess.Popen([sys.executable,str(ROOT/'tools/serve.py'),'--port',str(port)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
url=f'http://127.0.0.1:{port}/';box=cq.Solid.makeBox(20,30,10);sat=A.export_geometry([box,box.translate((40,0,0))]);sab=A.export_geometry([box],'sab')
try:
    for _ in range(100):
        try:urllib.request.urlopen(url,timeout=1);break
        except OSError:time.sleep(.05)
    with sync_playwright() as p:
        b=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
        page=b.new_page(viewport={'width':1600,'height':1000},accept_downloads=True);page.set_default_timeout(65000)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(url,wait_until='domcontentloaded');page.wait_for_function('document.documentElement.dataset.ready==="true"')
        def action(id):page.evaluate('(id)=>kestrel.run(id)',id)
        def submit(values=None):
            for key,value in (values or {}).items():
                el=page.locator('#modal [name="'+key+'"]')
                if el.evaluate('(e)=>e.type')=='checkbox':el.set_checked(bool(value))
                elif el.evaluate('(e)=>e.tagName')=='SELECT':el.select_option(str(value))
                else:el.fill(str(value))
            page.locator('#modal-submit').click();page.wait_for_function('!document.querySelector("#modal").open || !document.querySelector("#modal-error").hidden')
            assert not page.locator('#modal-error').is_visible(),page.locator('#modal-error').inner_text()
        def upload(data,name):page.locator('#acis-file').set_input_files({'name':name,'mimeType':'application/octet-stream','buffer':data})
        def test(name,fn):
            before=len(errors)
            try:fn();assert len(errors)==before,errors[before:];results.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
            except Exception as e:traceback.print_exc();results.append({'name':name,'status':'failed','error':str(e)});page.evaluate('kestrel.closeDialog();kestrel.cancel(false)')
        action('new')
        def importing():
            page.locator('[data-ribbon="Exchange"]').click();page.locator('#ribbon [data-action="acis-import"]').click();upload(sat,'bodies.sat');submit({'acknowledge':True})
            assert page.evaluate('kestrel.doc.entities.length')==2
            assert page.evaluate('kestrel.doc.entities.every(e=>e.solid.provider==="OCCT" && e.solid.solidCount===1 && Math.abs(e.solid.volume-6000)<1e-6)')
            action('undo');assert page.evaluate('kestrel.doc.entities.length')==0;action('redo');assert page.evaluate('kestrel.doc.entities.length')==2
        test('Exchange ribbon imports every SAT root as native B-rep with atomic undo',importing)
        def export_sat():
            page.evaluate('kestrel.doc.selection=new Set(kestrel.doc.entities.map(e=>e.id));kestrel.selectionChanged()');action('acis-export')
            with page.expect_download() as dl:submit({'format':'sat','acknowledge':True})
            out,_=A.import_geometry(Path(dl.value.path()).read_bytes(),'sat');assert len(out)==2 and abs(out[0].Volume()-6000)<1e-6
        test('ACISOUT dialog downloads a real multi-body SAT file',export_sat)
        def export_sab():
            action('acis-export')
            with page.expect_download() as dl:submit({'format':'sab','acknowledge':True})
            raw=Path(dl.value.path()).read_bytes();assert raw.startswith(b'ACIS BinaryFile');out,_=A.import_geometry(raw,'sab');assert len(out)==2
        test('SAB export contains typed binary records, not renamed text',export_sab)
        def native_dxf():
            action('acis-dxf')
            with page.expect_download() as dl:submit({'version':'R2018','acknowledge':True})
            doc=ezdxf.readfile(dl.value.path());audit=doc.audit();assert not audit.errors and not audit.fixes
            assert len(doc.modelspace())==2 and all(e.dxftype()=='3DSOLID' and e.sab for e in doc.modelspace())
        test('SOLIDDXF download passes independent payload and zero-repair audit',native_dxf)
        def import_sab():
            action('acis-import');upload(sab,'body.sab');submit({'acknowledge':True});assert page.evaluate('kestrel.doc.entities.length')==3;action('undo')
        test('SAB upload uses the actual binary decoder and retains undo',import_sab)
        def persistence():
            with page.expect_download() as dl:action('save')
            data=json.loads(Path(dl.value.path()).read_text());assert data['entities'][0]['solid']['brep']
            page.evaluate('(d)=>kestrel.addDocument(Kestrel.Drawing.from(d))',data);assert page.evaluate('kestrel.doc.entities.length')==2
        test('Native save and reopening retain imported authoritative bodies',persistence)
        def malformed():
            snap=page.evaluate('kestrel.doc.snapshot()');action('acis-import');upload(b'not acis','bad.sab');page.locator('[name="acknowledge"]').check();page.locator('#modal-submit').click();page.wait_for_function('!document.querySelector("#modal-error").hidden');assert page.evaluate('kestrel.doc.snapshot()')==snap;page.evaluate('kestrel.closeDialog()')
        test('Malformed input leaves the complete drawing unchanged',malformed)
        def curved():
            action('solid-cylinder');submit({'radius':4,'height':10});snapshot=page.evaluate('kestrel.doc.snapshot()');action('acis-export');page.locator('[name="acknowledge"]').check();page.locator('#modal-submit').click();page.wait_for_function('!document.querySelector("#modal-error").hidden');assert 'curved' in page.locator('#modal-error').inner_text().lower();assert page.evaluate('kestrel.doc.snapshot()')==snapshot;page.evaluate('kestrel.closeDialog()');action('undo')
        test('Curved-body export rejects instead of silently tessellating',curved)
        def stale():
            action('acis-import');upload(sat,'bodies.sat');page.evaluate('kestrel.doc.transaction("Other edit",()=>kestrel.doc.add("POINT",{position:[99,99,99]}))');page.locator('[name="acknowledge"]').check();page.locator('#modal-submit').click();page.wait_for_function('!document.querySelector("#modal-error").hidden');assert 'changed' in page.locator('#modal-error').inner_text().lower();assert page.evaluate('kestrel.doc.entities.length')==3;page.evaluate('kestrel.closeDialog()');action('undo')
        test('Stale ACIS dialog cannot overwrite a newer edit',stale)
        def units():
            action('new');action('acis-import');upload(A.export_geometry([box],'sat',25.4),'inch.sat');submit({'acknowledge':True});assert abs(page.evaluate('kestrel.doc.entities[0].solid.volume')-6000*25.4**3)<.001
        test('Import uses declared physical units rather than viewport scale',units)
        page.screenshot(path=str(OUT/'acis-exchange.png'));b.close()
finally:server.terminate();server.wait(timeout=5)
failed=sum(r['status']=='failed' for r in results);(OUT/'acis-browser-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'javascript_errors':errors,'tests':results},indent=2)+'\n');print('RESULT',len(results)-failed,'passed;',failed,'failed; JS errors:',errors);sys.exit(bool(failed or errors))
