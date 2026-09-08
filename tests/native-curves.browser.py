#!/usr/bin/env python3
"""Native edge/section authoring through the served editor and actual OCCT bridge."""
from pathlib import Path
import json,math,os,socket,subprocess,sys,time,traceback,urllib.request
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'tests/results';OUT.mkdir(exist_ok=True);sys.path.insert(0,str(ROOT/'tools'))
import kernel as K,native_curves as C,cadquery as cq,ezdxf
from OCP.Geom import Geom_Circle,Geom_TrimmedCurve
from OCP.GeomConvert import GeomConvert
from OCP.gp import gp_Circ,gp_Ax2,gp_Pnt,gp_Dir
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
box=K.pack(cq.Solid.makeBox(10,20,30),.1);cylinder=K.pack(cq.Solid.makeCylinder(4,12),.1)
carrier=GeomConvert.CurveToBSplineCurve_s(Geom_TrimmedCurve(Geom_Circle(gp_Circ(gp_Ax2(gp_Pnt(),gp_Dir(0,0,1)),4)),0,math.tau))
spline=C.extract_edge(cq.Edge(BRepBuilderAPI_MakeEdge(carrier).Edge()))
results=[];errors=[]
sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
server=subprocess.Popen([sys.executable,str(ROOT/'tools/serve.py'),'--port',str(port)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);url=f'http://127.0.0.1:{port}/'
try:
 for _ in range(100):
  try:urllib.request.urlopen(url,timeout=1);break
  except OSError:time.sleep(.05)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
  page=browser.new_page(viewport={'width':1600,'height':1050},accept_downloads=True);page.set_default_timeout(65000);page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(url,wait_until='domcontentloaded');page.wait_for_function('document.documentElement.dataset.ready==="true"')
  def action(s):page.evaluate('(s)=>kestrel.run(s)',s)
  def setup(items=None):
   page.evaluate('kestrel.closeDialog();kestrel.cancel(false);for(const d of kestrel.docs.slice()){if(d!==kestrel.doc){d.dirty=false;kestrel.closeDocument(d.id);}}');action('new')
   page.evaluate('(items)=>{const d=kestrel.doc;d.transaction("Native fixture",()=>{for(const item of items)d.add(Kestrel.Kernel.body(item));d.selection=new Set(d.entities.map(e=>e.id));});kestrel.selectionChanged();kestrel.fit(false);kestrel.autosave();}',[box] if items is None else items)
  def submit(values=None,error=None):
   for key,value in (values or {}).items():page.locator(f'#modal [name="{key}"]').fill(str(value))
   page.locator('#modal-submit').click();page.wait_for_function('!document.querySelector("#modal").open || !document.querySelector("#modal-error").hidden')
   if error is not None:assert page.locator('#modal-error').is_visible() and error in page.locator('#modal-error').inner_text().lower(),page.locator('#modal-error').inner_text()
   else:assert not page.locator('#modal-error').is_visible(),page.locator('#modal-error').inner_text()
  def test(name,fn):
   before=len(errors)
   try:fn();assert len(errors)==before,errors[before:];results.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
   except Exception as e:traceback.print_exc();results.append({'name':name,'status':'failed','error':str(e)});page.evaluate('kestrel.closeDialog();kestrel.cancel(false)')
  def edges():
   setup();original=page.evaluate('JSON.stringify(kestrel.doc.entities[0])');history=page.evaluate('kestrel.doc.undoStack.length')
   page.locator('[data-ribbon="Solids"]').click();page.locator('#ribbon [data-action="native-edges"]').click();submit()
   assert page.evaluate('kestrel.doc.entities.length')==13 and page.evaluate('kestrel.doc.selection.size')==12
   assert page.evaluate('kestrel.doc.entities.slice(1).every(e=>e.type==="LINE"&&!e.solid)')
   assert page.evaluate('JSON.stringify(kestrel.doc.entities[0])')==original
   assert page.evaluate('kestrel.doc.undoStack.length')==history+1
  test('Solids ribbon extracts twelve editable native box edges without changing source',edges)
  def undo():
   action('undo');assert page.evaluate('kestrel.doc.entities.length')==1;action('redo');assert page.evaluate('kestrel.doc.entities.length')==13
  test('Complete extraction is one undoable and redoable operation',undo)
  def subset():
   setup();action('XEDGES');submit({'indices':'4,1'});assert page.evaluate('kestrel.doc.entities.length')==3
   assert page.evaluate('kestrel.doc.entities.slice(1).every(e=>e.type==="LINE")')
  test('XEDGES accepts selected current native edge indices',subset)
  def invalid():
   setup();action('XEDGES');snapshot=page.evaluate('kestrel.doc.snapshot()');submit({'indices':'999'},'index');assert page.evaluate('kestrel.doc.snapshot()')==snapshot
   submit({'indices':'1,1'},'indices');assert page.evaluate('kestrel.doc.snapshot()')==snapshot
   submit({'indices':'2'});assert page.evaluate('kestrel.doc.entities.length')==2
  test('Invalid edge indices reject atomically and can be corrected',invalid)
  def circular():
   setup([cylinder]);action('SECTIONCURVES');submit({'origin':'0,0,6'});e=page.evaluate('kestrel.doc.entities[1]')
   assert e['type']=='CIRCLE' and abs(e['radius']-4)<1e-10 and abs(e['center'][2]-6)<1e-10
  test('SECTIONCURVES creates a true editable circular section',circular)
  def oblique():
   setup([cylinder]);action('SECTIONCURVES');submit({'origin':'0,0,6','normal':'0,1,2'});e=page.evaluate('kestrel.doc.entities[1]')
   assert e['type']=='ELLIPSE' and abs(e['rx']-4*math.sqrt(1.25))<1e-9 and abs(e['ry']-4)<1e-9
  test('Oblique native cylinder section retains analytic ellipse axes',oblique)
  def ucs():
   setup([cylinder]);page.evaluate('kestrel.doc.transaction("UCS",()=>kestrel.doc.production.ucs={origin:[0,0,6],x:[1,0,0],y:[0,1,0]})');action('SECTIONCURVES');submit();assert abs(page.evaluate('kestrel.doc.entities[1].center[2]')-6)<1e-9
  test('Section plane input follows the active UCS rather than the camera',ucs)
  def no_hit():
   setup();action('SECTIONCURVES');snap=page.evaluate('kestrel.doc.snapshot()');history=page.evaluate('kestrel.doc.undoStack.length');submit({'origin':'0,0,99'})
   assert page.evaluate('kestrel.doc.snapshot()')==snap and page.evaluate('kestrel.doc.undoStack.length')==history
  test('A missed section changes neither drawing nor undo history',no_hit)
  def download():
   setup([cylinder]);action('SECTIONCURVES');submit({'origin':'0,0,6'})
   with page.expect_download() as dl:action('export-dxf')
   doc=ezdxf.readfile(dl.value.path());a=doc.audit();assert not a.errors and not a.fixes
   circles=list(doc.modelspace().query('CIRCLE'));assert len(circles)==1 and abs(circles[0].dxf.radius-4)<1e-10
  test('Actual worker/download DXF contains the extracted native analytic circle',download)
  def reopen():
   with page.expect_download() as dl:action('save')
   data=json.loads(Path(dl.value.path()).read_text());assert data['entities'][0]['solid']['brep'];assert data['entities'][1]['type']=='CIRCLE'
   page.evaluate('(d)=>kestrel.addDocument(Kestrel.Drawing.from(d))',data);assert page.evaluate('kestrel.doc.entities.length')==2
  test('Native project reopens source BREP and independent drafting curves',reopen)
  def extrusion():
   setup([]);page.evaluate('(e)=>{const d=kestrel.doc;d.transaction("Rational profile",()=>{const x=d.add(e);d.selection=new Set([x.id]);});kestrel.selectionChanged();}',spline)
   action('solid-extrude');submit({'vector':'0,0,7'});e=page.evaluate('kestrel.doc.entities.at(-1)');assert e['solid']['brep'];assert abs(e['solid']['volume']-math.pi*16*7)<1e-6
   action('undo');assert page.evaluate('kestrel.doc.entities.length')==1
  test('A clamped rational circular SPLINE drives actual native extrusion and undo',extrusion)
  def sweep():
   setup([]);page.evaluate('()=>{const d=kestrel.doc;d.transaction("Sweep profiles",()=>{const a=d.add("CIRCLE",{center:[0,0,0],radius:2}),b=d.add("SPLINE",{controlPoints:[[0,0,0],[0,0,20]],degree:1,knots:[0,0,1,1]});d.selection=new Set([a.id,b.id]);});kestrel.selectionChanged();}')
   action('solid-sweep');submit();assert abs(page.evaluate('kestrel.doc.entities.at(-1).solid.volume')-math.pi*80)<1e-6
  test('Open clamped SPLINE serves as a real native sweep path',sweep)
  def locks():
   setup();page.evaluate('kestrel.doc.layer(kestrel.doc.entities[0]).locked=true');action('XEDGES');snap=page.evaluate('kestrel.doc.snapshot()');submit(error='unlocked');assert page.evaluate('kestrel.doc.snapshot()')==snap
   page.evaluate('kestrel.closeDialog();kestrel.doc.currentLayer="construction"');action('XEDGES');submit();assert page.evaluate('kestrel.doc.entities.slice(1).every(e=>e.layer==="construction")')
  test('Read-only locked sources can extract to an unlocked current layer',locks)
  def stale():
   setup();action('XEDGES');page.evaluate('kestrel.doc.transaction("New edit",()=>kestrel.doc.add("POINT",{position:[1,2,3]}))');snap=page.evaluate('kestrel.doc.snapshot()');submit(error='changed');assert page.evaluate('kestrel.doc.snapshot()')==snap
  test('An extraction dialog cannot overwrite a newer document edit',stale)
  def cancelled():
   setup();page.evaluate('()=>{const N=Kestrel.Kernel;window.originalCurveRequest=N.request;window.curveGateDone=false;N.request=async(...args)=>{await new Promise(resolve=>window.releaseCurveGate=resolve);try{return await window.originalCurveRequest(...args);}finally{window.curveGateDone=true;}};}')
   try:
    action('XEDGES');page.locator('#modal-submit').click();page.wait_for_function('typeof window.releaseCurveGate==="function"')
    page.evaluate('()=>{kestrel.closeDialog();kestrel.dialog({title:"Replacement",html:"<p>Do not apply old extraction.</p>",closeOnly:true});}');snap=page.evaluate('kestrel.doc.snapshot()')
    page.evaluate('window.releaseCurveGate()');page.wait_for_function('window.curveGateDone && !document.querySelector("#modal-error").hidden');assert page.evaluate('kestrel.doc.snapshot()')==snap
   finally:page.evaluate('Kestrel.Kernel.request=window.originalCurveRequest;kestrel.closeDialog()')
  test('A completed native request cannot apply after its dialog was replaced',cancelled)
  setup([cylinder]);action('SECTIONCURVES');page.locator('[name="origin"]').fill('0,0,6');page.screenshot(path=str(OUT/'native-curves.png'));browser.close()
finally:server.terminate();server.wait(timeout=5)
failed=sum(t['status']=='failed' for t in results);(OUT/'native-curves-browser-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'javascript_errors':errors,'tests':results},indent=2)+'\n');print('RESULT',len(results)-failed,'passed',failed,'failed; JS',errors);sys.exit(bool(failed or errors))
