#!/usr/bin/env python3
"""Browser integration tests with real mouse/keyboard interaction.
Requires Python Playwright and Chromium. Set KESTREL_TEST_URL to test a server;
otherwise this loads the standalone document via set_content (Canvas fallback).
No browser security settings or administrator policies are changed.
"""
from pathlib import Path
import json, os, sys, time, traceback
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'tests/results'
OUT.mkdir(exist_ok=True)
results=[]

with sync_playwright() as p:
    executable=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium')
    browser=p.chromium.launch(executable_path=executable,headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1600,'height':1000},device_scale_factor=1,accept_downloads=True)
    page.set_default_timeout(6000)
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    url=os.environ.get('KESTREL_TEST_URL')
    if url:page.goto(url,wait_until='domcontentloaded')
    else:page.set_content((ROOT/'Kestrel-CAD.html').read_text(),wait_until='domcontentloaded')
    page.wait_for_function('document.documentElement.dataset.ready === "true"',timeout=30000)

    def test(name,fn):
        before=len(errors)
        try:
            detail=fn()
            assert len(errors)==before,errors[before:]
            results.append({'name':name,'status':'passed','detail':detail})
            print('PASS',name,flush=True)
        except Exception as exc:
            results.append({'name':name,'status':'failed','error':str(exc)})
            print('FAIL',name,repr(exc),flush=True)
            page.screenshot(path=str(OUT/f'failure-{len(results)}.png'))
            traceback.print_exc(limit=2)
            page.evaluate("kestrel.closeDialog();document.getElementById('command-palette').close();kestrel.cancel(false)")

    def state(expression):return page.evaluate(expression)
    def eq(actual,expected):assert actual==expected,(actual,expected)
    def near(actual,expected,eps=1e-5):assert abs(actual-expected)<eps,(actual,expected)
    def command(text):
        page.locator('#command-input').fill(text)
        page.locator('#command-input').press('Enter')
        page.wait_for_timeout(90)
    def action(name):
        page.evaluate('(id)=>kestrel.run(id)',name)
        page.wait_for_timeout(80)
    def fresh():
        page.evaluate("kestrel.closeDialog();kestrel.cancel(false);kestrel.docs=[kestrel.doc];kestrel.run('new');kestrel.settings.osnap=false;kestrel.settings.snap=false;kestrel.settings.ortho=false;kestrel.settings.polar=false;kestrel.defaults.textHeight=5;kestrel.defaults.dimensionHeight=5;kestrel.refresh();")
        page.wait_for_timeout(80)
    def select(indices):
        page.evaluate('(ids)=>{kestrel.doc.selection=new Set(ids.map(i=>kestrel.doc.entities[i].id));kestrel.selectionChanged();}',indices)
    def close_modal():
        if page.locator('#modal').evaluate('(e)=>e.open'):page.locator('#modal-close').click()
    def submit(fields=None,checks=None):
        for name,value in (fields or {}).items():
            el=page.locator(f'#modal [name="{name}"]')
            if el.evaluate('(e)=>e.tagName')=='SELECT':el.select_option(str(value))
            else:el.fill(str(value))
        for name,value in (checks or {}).items():page.locator(f'#modal [name="{name}"]').set_checked(value)
        page.locator('#modal-submit').click()
        page.wait_for_timeout(120)
        if page.locator('#modal-error').is_visible():raise AssertionError(page.locator('#modal-error').inner_text())
    def screen(point):
        q=page.evaluate('(p)=>kestrel.camera.project(p)',point)
        r=page.locator('#viewport').bounding_box()
        return (r['x']+q[0],r['y']+q[1])
    def click_world(point):page.mouse.click(*screen(point));page.wait_for_timeout(70)
    def fit():action('fit')
    def count():return state('kestrel.doc.entities.length')

    test('standalone startup and editable 2D example',lambda:(eq(count(),265),eq(errors,[])))
    def ribbon_tabs():
        for tab in ['Home','Insert','Annotate','Model','View','Manage']:
            page.locator(f'[data-ribbon="{tab}"]').click()
            assert page.locator('#ribbon button').count()>2
    test('all ribbon tabs are populated',ribbon_tabs)
    def light_dark():
        action('theme');eq(state('kestrel.theme'),'light');eq(state('document.documentElement.dataset.theme'),'light');action('theme');eq(state('kestrel.theme'),'dark')
    test('light/dark theme toggle updates the document',light_dark)
    def draw_commands():
        fresh();command('LINE 0,0 100,0 @0,80 ENTER');eq(count(),2)
        eq(state('kestrel.doc.entities[1].points'),[[100,0,0],[100,80,0]])
        command('REC 150,0 250,80');command('CIRCLE 200,40 20');eq(count(),4)
        eq(state('kestrel.doc.entities[2].closed'),True);near(state('kestrel.doc.entities[3].radius'),20)
        command('PLINE 0,150 60,150 @0,60 C');eq(state('kestrel.doc.entities.at(-1).closed'),True)
        fit()
    test('command line creates exact lines, rectangle, circle and closed polyline',draw_commands)
    def polar_line():
        fresh();command('L 0,0 @100<30 ENTER');near(state('kestrel.doc.entities[0].points[1][0]'),86.6025403784);near(state('kestrel.doc.entities[0].points[1][1]'),50)
    test('relative polar coordinate input',polar_line)
    def arc_spline():
        fresh();command('ARC 10,0 0,10 -10,0');command('ELLIPSE 40,0 50,0 5');command('SPLINE 0,20 10,40 20,10 30,20 ENTER');eq(state('kestrel.doc.entities.map(e=>e.type)'),['ARC','ELLIPSE','SPLINE'])
    test('arc, ellipse and spline drawing commands',arc_spline)
    def moves():
        fresh();command('L 0,0 100,0 ENTER');select([0]);command('MOVE 0,0 @25,30');eq(state('kestrel.doc.entities[0].points[0]'),[25,30,0]);select([0]);command('COPY 0,0 @0,50');eq(count(),2)
        command('UNDO');eq(count(),1);command('REDO');eq(count(),2)
    test('move, copy, undo and redo edit real geometry',moves)
    def rotate_scale():
        fresh();command('L 0,0 100,0 ENTER');select([0]);command('ROTATE 0,0 90');near(state('kestrel.doc.entities[0].points[1][1]'),100);select([0]);command('SCALE 0,0 2');near(state('kestrel.doc.entities[0].points[1][1]'),200)
    test('numeric rotation and scale',rotate_scale)
    def mouse_line():
        fresh();page.locator('#viewport-tools [data-action="line"]').click();click_world([0,0,0]);click_world([300,100,0]);page.keyboard.press('Escape');eq(count(),1);near(state('kestrel.doc.entities[0].points[1][0]'),300,2.5);near(state('kestrel.doc.entities[0].points[1][1]'),100,2.5)
    test('mouse drawing through toolbar',mouse_line)
    def snap_line():
        fresh();command('L 0,0 100,0 ENTER');fit();page.evaluate('kestrel.settings.osnap=true');page.locator('#viewport-tools [data-action="line"]').click();x,y=screen([100,0,0]);page.mouse.click(x+4,y+3);eq(state('kestrel.tool.points[0]'),[100,0,0]);click_world([60,20,0]);page.keyboard.press('Escape');eq(count(),2)
    test('endpoint object snap resolves imprecise mouse clicks',snap_line)
    def select_and_grip():
        fresh();command('L 0,0 100,0 ENTER');fit();click_world([30,0,0]);eq(state('kestrel.doc.selection.size'),1)
        start=screen([100,0,0]);end=screen([80,10,0]);page.mouse.move(*start);page.mouse.down();page.mouse.move(*end,steps=8);page.mouse.up();near(state('kestrel.doc.entities[0].points[1][0]'),80,.3);near(state('kestrel.doc.entities[0].points[1][1]'),10,.3)
        action('undo');eq(state('kestrel.doc.entities[0].points[1]'),[100,0,0])
    test('click selection, endpoint grip editing and undo',select_and_grip)
    def selection_window():
        fresh();command('REC 0,0 100,80');command('L 150,0 220,80 ENTER');fit();a=screen([-10,90,0]);b=screen([110,-10,0]);page.mouse.move(*a);page.mouse.down();page.mouse.move(*b,steps=8);page.mouse.up();eq(state('kestrel.doc.selection.size'),1);eq(state('kestrel.doc.selected()[0].type'),'POLYLINE')
    test('left-to-right selection window contains only enclosed objects',selection_window)
    def crossing_window():
        page.keyboard.press('Escape');a=screen([185,45,0]);b=screen([170,20,0]);page.mouse.move(*a);page.mouse.down();page.mouse.move(*b,steps=8);page.mouse.up();eq(state('kestrel.doc.selection.size'),1);eq(state('kestrel.doc.selected()[0].type'),'LINE')
    test('right-to-left crossing window selects intersecting objects',crossing_window)
    def zoom_pan():
        fresh();command('REC 0,0 100,100');fit();zoom=state('kestrel.camera.zoom');page.mouse.move(*screen([50,50,0]));page.mouse.wheel(0,-200);page.wait_for_timeout(100);assert state('kestrel.camera.zoom')>zoom
        before=state('kestrel.camera.target');x,y=screen([50,50,0]);page.mouse.move(x,y);page.mouse.down(button='middle');page.mouse.move(x+40,y+30,steps=5);page.mouse.up(button='middle');assert state('kestrel.camera.target')!=before
    test('wheel zoom and middle-button pan',zoom_pan)
    def properties():
        fresh();command('C 0,0 20');select([0]);el=page.locator('#inspector [data-prop="radius"]');el.fill('35');el.press('Tab');near(state('kestrel.doc.entities[0].radius'),35);action('undo');near(state('kestrel.doc.entities[0].radius'),20)
    test('property inspector radius change is undoable',properties)
    def layers():
        fresh();command('L 0,0 100,0 ENTER');layer=state('kestrel.doc.entities[0].layer');row=page.locator(f'[data-layer="{layer}"]');row.locator('[data-layer-toggle="visible"]').click();eq(state('kestrel.doc.visible(kestrel.doc.entities[0])'),False);row.locator('[data-layer-toggle="visible"]').click();row.locator('[data-layer-toggle="locked"]').click();action('selectall');eq(state('kestrel.doc.selection.size'),0);row.locator('[data-layer-toggle="locked"]').click();action('selectall');eq(state('kestrel.doc.selection.size'),1)
    test('layer visibility and lock controls affect selection and editing',layers)
    def newlayer():
        action('new-layer');submit({'name':'TEST LAYER'});assert state("kestrel.doc.layers.some(l=>l.name==='TEST LAYER')")
    test('new layer dialog creates a real layer',newlayer)
    def hatch():
        fresh();command('REC 0,0 100,100');select([0]);action('hatch');submit({'pattern':'cross','spacing':8});eq(count(),2);eq(state('kestrel.doc.entities[1].type'),'HATCH');assert state('kestrel.doc.geometry(kestrel.doc.entities[1]).segments.length')>10
    test('hatching selected boundaries creates clipped geometry',hatch)
    def dimensions_text():
        fresh();command('DIM 0,0 100,0 -15');eq(state('kestrel.doc.entities[0].type'),'DIMENSION');near(state('kestrel.doc.entities[0].offset'),-15)
        action('text');submit({'text':'Editable annotation','height':8,'rotation':15});command('20,30');eq(state('kestrel.doc.entities[1].text'),'Editable annotation')
    test('dimension and text dialogs create editable annotations',dimensions_text)
    def arrays():
        fresh();command('C 0,0 10');select([0]);action('array');submit({'columns':3,'rows':2,'dx':30,'dy':40});eq(count(),6);eq(len(set(state('kestrel.doc.entities.map(e=>e.id)'))),6);action('undo');eq(count(),1)
    test('rectangular array uses unique editable objects and one undo',arrays)
    def polar_array():
        fresh();command('C 20,0 4');select([0]);action('array');submit({'kind':'polar','count':4,'angle':360,'cx':0,'cy':0});eq(count(),4);near(state('kestrel.doc.entities[1].center[1]'),20)
    test('polar array rotates geometry about the specified center',polar_array)
    def trim():
        fresh();command('L 0,0 100,0 ENTER');command('L 25,-30 25,30 ENTER');command('L 75,-30 75,30 ENTER');fit();action('trim');click_world([50,0,0]);page.keyboard.press('Escape');eq(count(),4);lengths=state("kestrel.doc.entities.filter(e=>Math.abs(e.points[0][1])<1e-8&&Math.abs(e.points[1][1])<1e-8).map(e=>Kestrel.Math.V.dist(...e.points))");eq(len(lengths),2);near(sum(lengths),50)
    test('trim removes a bounded interval and preserves both line remainders',trim)
    def extend():
        fresh();command('L 0,0 50,0 ENTER');command('L 100,-20 100,20 ENTER');fit();action('extend');click_world([48,0,0]);page.keyboard.press('Escape');near(state('kestrel.doc.entities[0].points[1][0]'),100)
    test('extend reaches an intersecting line boundary',extend)
    def join_explode():
        fresh();command('L 0,0 100,0 100,50 ENTER');select([0,1]);action('join');eq(count(),1);eq(state('kestrel.doc.entities[0].type'),'POLYLINE');select([0]);action('explode');eq(count(),2)
    test('join and explode preserve connected geometry',join_explode)
    def solid():
        fresh();action('box');submit({'x':0,'y':0,'z':0,'width':10,'depth':20,'height':30});eq(count(),1);near(state('Kestrel.Geo.volume(kestrel.doc.entities[0])'),6000);eq(state('kestrel.workspace'),'3d');eq(state('kestrel.renderer.style'),'shaded-edges')
    test('box dialog creates a measurable 3D mesh',solid)
    def styles_views():
        for style in ['wireframe','shaded','shaded-edges','xray']:
            page.locator('#style-select').select_option(style);eq(state('kestrel.renderer.style'),style)
        for view in ['top','front','right','iso']:
            page.locator('#view-select').select_option(view)
            assert state('kestrel.camera.matrix.every(Number.isFinite)')
        action('perspective');eq(state('kestrel.camera.perspective'),True);action('perspective')
    test('3D view and visual-style controls change the renderer',styles_views)
    def extrusion():
        fresh();command('REC 0,0 40,30');select([0]);action('extrude');submit({'height':20},{'keep':False});eq(count(),1);near(state('Kestrel.Geo.volume(kestrel.doc.entities[0])'),24000)
    test('extrude creates a closed mesh and optionally removes its source',extrusion)
    def boolean_subtract():
        fresh();page.evaluate("kestrel.doc.transaction('test fixtures',()=>{kestrel.doc.add(Kestrel.Geo.box([0,0,0],10,10,10));kestrel.doc.add(Kestrel.Geo.box([5,0,0],10,10,10));});");select([0,1]);action('subtract');eq(count(),1);near(state('Kestrel.Geo.volume(kestrel.doc.entities[0])'),500);action('undo');eq(count(),2)
    test('Boolean subtract and undo operate on actual mesh geometry',boolean_subtract)
    def section():
        select([0]);action('section');submit({'z':5});assert state("kestrel.doc.entities.some(e=>e.type==='LINE'&&Math.abs(e.points[0][2]-5)<1e-8)")
    test('section creates line geometry on a specified Z plane',section)
    def transform3d():
        select([0]);old=state('kestrel.doc.entities[0].vertices[0]');action('transform3d');submit({'x':10,'y':20,'z':30,'rx':0,'ry':0,'rz':0,'scale':1});new=state('kestrel.doc.entities[0].vertices[0]');eq(new,[old[0]+10,old[1]+20,old[2]+30])
    test('3D transform dialog translates mesh vertices',transform3d)
    def palette():
        page.locator('#viewport').focus();page.keyboard.press('Control+k');eq(page.locator('#command-palette').evaluate('(e)=>e.open'),True);page.locator('#palette-search').fill('diagnostics');assert page.locator('.palette-item').count()>=1;page.locator('#palette-search').press('Enter');eq(page.locator('#modal-title').inner_text(),'Renderer diagnostics');close_modal()
    test('command palette search and keyboard execution',palette)
    def mirror():
        fresh();command('L 20,10 40,30 ENTER');select([0]);command('MIRROR 0,0 0,100');near(state('kestrel.doc.entities[0].points[0][0]'),-20);near(state('kestrel.doc.entities[0].points[0][1]'),10)
    test('mirror reflects actual geometry across the specified axis',mirror)
    def offset():
        fresh();command('C 0,0 20');select([0]);fit();action('offset');submit({'distance':5});click_world([30,0,0]);page.keyboard.press('Escape');eq(count(),2);near(state('kestrel.doc.entities[1].radius'),25)
    test('offset circle through modal and mouse-side selection',offset)
    def fillet():
        fresh();command('L 0,0 100,0 ENTER');command('L 0,0 0,100 ENTER');select([0,1]);action('fillet');submit({'distance':10});eq(count(),3);near(state('kestrel.doc.entities[2].radius'),10);eq(state('kestrel.doc.entities[2].type'),'ARC');action('undo');eq(count(),2)
    test('fillet trims two lines and creates a real tangent arc',fillet)
    def chamfer():
        select([0,1]);action('chamfer');submit({'distance':12});eq(count(),3);near(state('Kestrel.Math.V.dist(...kestrel.doc.entities[2].points)'),12*2**.5)
    test('chamfer creates the expected diagonal setback',chamfer)
    def revolve():
        fresh();command('REC 10,0 20,30');select([0]);action('revolve');submit({'axis':'y','angle':360,'segments':32},{'keep':False});eq(count(),1);eq(state('kestrel.doc.entities[0].type'),'MESH');near(state('Kestrel.Geo.volume(kestrel.doc.entities[0])'),32/2*__import__('math').sin(2*__import__('math').pi/32)*(400-100)*30,.01)
    test('revolve produces the expected tessellated ring volume',revolve)
    def text_rotation():
        fresh();action('text');submit({'text':'Rotated text','height':10});command('0,0');select([0]);command('ROTATE 0,0 30');select([0]);assert state('!!kestrel.doc.entities[0].direction');el=page.locator('#inspector [data-prop="rotationDeg"]');el.fill('90');el.press('Tab');near(state('Kestrel.Geo.textAxes(kestrel.doc.entities[0]).x[1]'),1);assert not state('!!kestrel.doc.entities[0].direction')
        page.evaluate('kestrel.textDialog(kestrel.doc.entities[0])');submit({'rotation':180});near(state('Kestrel.Geo.textAxes(kestrel.doc.entities[0]).x[0]'),-1)
    test('inspector and text dialog override transformed text direction correctly',text_rotation)
    def grouping():
        fresh();command('L 0,0 100,0 ENTER');command('L 0,40 100,40 ENTER');select([0,1]);action('group');submit({'name':'Paired lines'});groups=state('kestrel.doc.entities.map(e=>e.group)');assert groups[0] and groups[0]==groups[1];action('ungroup');assert state('kestrel.doc.entities.every(e=>!e.group)')
    test('group and ungroup update entity organization',grouping)
    def clipboard():
        fresh();command('REC 0,0 100,50');select([0]);page.locator('#viewport').focus();page.keyboard.press('Control+c');eq(state('kestrel.clipboard.length'),1);page.keyboard.press('Control+v');command('200,0');eq(count(),2);near(state('kestrel.doc.entities[1].points[0][0]'),200);eq(len(set(state('kestrel.doc.entities.map(e=>e.id)'))),2)
    test('keyboard in-app copy and paste creates independent geometry',clipboard)
    def units():
        fresh();command('L 0,0 254,0 ENTER');action('units');submit({'units':'in'},{'convert':True});eq(state('kestrel.doc.units'),'in');near(state('kestrel.doc.entities[0].points[1][0]'),10);action('undo');eq(state('kestrel.doc.units'),'mm');near(state('kestrel.doc.entities[0].points[1][0]'),254)
    test('units conversion rescales actual geometry and is undoable',units)
    def toggles():
        fresh();page.locator('#viewport').focus()
        for key,setting in [('F3','osnap'),('F7','grid'),('F8','ortho'),('F9','snap'),('F10','polar')]:
            old=state('kestrel.settings.'+setting);page.keyboard.press(key);eq(state('kestrel.settings.'+setting),not old)
        page.evaluate('kestrel.settings.grid=true;kestrel.settings.ortho=false;kestrel.settings.snap=false;kestrel.settings.polar=false;kestrel.refresh()')
    test('function-key drafting toggles change real editor settings',toggles)
    def pick_front_face():
        fresh();page.evaluate("kestrel.doc.transaction('test occlusion',()=>{kestrel.doc.add(Kestrel.Geo.box([-50,-50,0],100,100,10));kestrel.doc.add(Kestrel.Geo.box([-50,-50,30],100,100,10));});kestrel.setStyle('shaded');kestrel.setView('top');kestrel.fit();")
        click_world([5,3,40]);eq(state('kestrel.doc.selected()[0].id'),state('kestrel.doc.entities[1].id'))
    test('shaded face picking selects the nearest overlapping mesh',pick_front_face)
    def dxf_worker():
        page.locator('#file-input').set_input_files(str(ROOT/'tests/fixtures/external.dxf'));page.wait_for_function("kestrel.doc.name==='external'",timeout=20000);assert count()>25;assert state("kestrel.doc.entities.some(e=>e.text==='±BOLT · Żółć Ω 😀')");assert state('!!kestrel.worker');eq(state('kestrel.lastImportReport.skipped'),{});close_modal()
    test('file input imports independent DXF through the worker',dxf_worker)
    def native_file():
        page.locator('#file-input').set_input_files(str(ROOT/'examples/courtyard.kcad'));page.wait_for_function("kestrel.doc.name.includes('Courtyard')",timeout=10000);eq(count(),265)
    test('native project file input restores the complete drawing',native_file)
    def dxf_export():
        with page.expect_download(timeout=15000) as d:
            page.evaluate("kestrel.run('export-dxf')")
        download=d.value;assert download.suggested_filename.endswith('.dxf');download.save_as(OUT/'browser-export.dxf');assert (OUT/'browser-export.dxf').stat().st_size>10000
    test('DXF export produces an actual browser download',dxf_export)
    def native_export():
        with page.expect_download(timeout=15000) as d:page.locator('#quick-access [data-action="save"]').click()
        d.value.save_as(OUT/'browser-export.kcad');data=json.loads((OUT/'browser-export.kcad').read_text());eq(data['format'],'kestrel-cad');eq(len(data['entities']),265)
    test('Save project produces a valid native browser download',native_export)
    def png_export():
        with page.expect_download(timeout=15000) as d:page.evaluate("kestrel.run('export-png')")
        d.value.save_as(OUT/'browser-export.png');eq((OUT/'browser-export.png').read_bytes()[:8],b'\x89PNG\r\n\x1a\n');assert (OUT/'browser-export.png').stat().st_size>30000
    test('PNG export captures the actual viewport',png_export)
    def svg_export():
        action('export-svg')
        with page.expect_download(timeout=15000) as d:submit()
        d.value.save_as(OUT/'browser-export.svg');text=(OUT/'browser-export.svg').read_text();assert text.startswith('<svg');assert '<path' in text
    test('SVG export produces vector geometry',svg_export)
    def dwg_unavailable():
        action('dwg-setup');assert page.locator('#modal').evaluate('(e)=>e.open');assert 'DWG' in page.locator('#modal-title').inner_text();assert 'codec' in page.locator('#modal-body').inner_text().lower();close_modal()
    test('DWG dialog reports the optional codec requirement',dwg_unavailable)
    def primitive_inventory():
        for kind in ['cylinder','sphere','cone','torus']:
            fresh();action(kind);submit({'radius':10,**({'minor':2} if kind=='torus' else {}),**({'height':20} if kind in ['cylinder','cone'] else {})});eq(count(),1);assert state('Kestrel.Geo.volume(kestrel.doc.entities[0])')>0
    test('cylinder, sphere, cone and torus tools create positive-volume meshes',primitive_inventory)
    def help_and_screens():
        action('help');assert 'DWG' in page.locator('#modal-body').inner_text();close_modal();action('demo-2d');page.wait_for_timeout(300);page.mouse.move(10,10);page.screenshot(path=str(OUT/'kestrel-2d-dark.png'),full_page=True);action('theme');page.screenshot(path=str(OUT/'kestrel-2d-light.png'),full_page=True);action('theme');action('demo-3d');page.wait_for_timeout(350);page.mouse.move(10,10);page.screenshot(path=str(OUT/'kestrel-3d-dark.png'),full_page=True)
    test('help and both complete editable demonstration drawings',help_and_screens)
    diagnostics=state('kestrel.diagnosticData()')
    report={'suite':'Chromium browser integration','loading':'localhost/server' if url else 'offline set_content; insecure context; Canvas compatibility renderer','passed':sum(r['status']=='passed' for r in results),'failed':sum(r['status']=='failed' for r in results),'javascript_errors':errors,'diagnostics':diagnostics,'tests':results}
    (OUT/'browser-results.json').write_text(json.dumps(report,indent=2))
    print('\nRESULT',report['passed'],'passed;',report['failed'],'failed; JavaScript errors:',errors,flush=True)
    browser.close()
    sys.exit(report['failed']>0 or bool(errors))
