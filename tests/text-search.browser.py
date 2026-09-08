#!/usr/bin/env python3
"""Actual Find UI, rich replacements, selected scopes, field protection and native downloads."""
from pathlib import Path
import json,os,sys,traceback
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'tests/results';OUT.mkdir(exist_ok=True);tests=[];errors=[]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH',p.chromium.executable_path),headless=True,args=['--no-sandbox'])
    page=b.new_page(viewport={'width':1600,'height':1100},accept_downloads=True);page.set_default_timeout(20000);page.on('pageerror',lambda e:errors.append(str(e)))
    url=os.environ.get('KESTREL_TEST_URL');mode=os.environ.get('KESTREL_TEST_MODE','file')
    if url:page.goto(url,wait_until='domcontentloaded');loading='served URL'
    elif mode=='dom':page.set_content((ROOT/'Kestrel-CAD.html').read_text(),wait_until='domcontentloaded');loading='standalone DOM diagnostic; no file or HTTP navigation'
    elif mode=='file':page.goto((ROOT/'Kestrel-CAD.html').as_uri(),wait_until='domcontentloaded');loading='standalone file navigation'
    else:raise ValueError('Unknown KESTREL_TEST_MODE')
    page.wait_for_function('document.documentElement.dataset.ready==="true" && Kestrel.TextSearch')
    def action(id):page.evaluate('(id)=>kestrel.run(id)',id)
    def fixture():
        page.evaluate('kestrel.docs=[kestrel.doc];delete kestrel._textSearchSettings');action('new');page.evaluate("""rich=>{const d=kestrel.doc;d.transaction('Fixture',()=>{d.add('TEXT',{id:'a',position:[0,0,0],height:4,text:'Valve valve'});d.add('MTEXT',{id:'b',position:[0,20,0],height:4,width:120,text:rich});d.add('TABLE',{id:'c',position:[0,50,0],rowHeight:8,columnWidth:30,cells:[['Part','Valve']]});});kestrel.selectionChanged();}""",r'Va{\C1;lve} — Ω')
    def test(name,fn):
        before=len(errors)
        try:page.evaluate('kestrel.closeDialog();kestrel.cancel(false)');fixture();fn();assert len(errors)==before,errors[before:];tests.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
        except Exception as e:traceback.print_exc();tests.append({'name':name,'status':'failed','error':str(e)});page.evaluate('kestrel.closeDialog();kestrel.cancel(false)')
    def values(find='Valve',replacement='Gate',**kwargs):
        for name,value in dict(find=find,replacement=replacement,**kwargs).items():
            e=page.locator('#modal [name="'+name+'"]')
            if e.evaluate('(e)=>e.type')=='checkbox':e.set_checked(value)
            elif e.evaluate('(e)=>e.tagName')=='SELECT':e.select_option(value)
            else:e.fill(value)
    def search(**kwargs):values(**kwargs);page.locator('#text-search').click()
    def state():return page.locator('#search-status').inner_text()
    def ribbon():
        page.locator('[data-ribbon="Text"]').click();page.locator('#ribbon [data-action="find-text"]').click();search();assert state().startswith('4 matches'),state();assert page.locator('#search-results mark').count()==4
    test('Text ribbon finds actual plain rich and table matches',ribbon)
    def rich():
        action('FIND');search(type='MTEXT');page.locator('#replace-current').click();assert page.evaluate('kestrel.doc.byId.get("b").text')==r'Gate{\C1;} — Ω';assert 'Replaced 1' in state()
    test('Replace current preserves real MTEXT control scopes',rich)
    def all():
        action('FIND');search();page.locator('#replace-all').click();assert 'Replaced 4' in state();page.evaluate('kestrel.closeDialog()');action('undo');assert page.evaluate('kestrel.doc.byId.get("a").text')=='Valve valve';assert page.evaluate('kestrel.doc.byId.get("c").cells[0][1]')=='Valve';action('redo');assert page.evaluate('kestrel.doc.byId.get("c").cells[0][1]')=='Gate'
    test('Replace all forms one native undo redo action',all)
    def case():
        action('FIND');search(caseSensitive=True,wholeWord=True);assert state().startswith('3 matches'),state()
    test('case and whole-word controls apply to visible text',case)
    def scope():
        page.evaluate('kestrel.doc.selection=new Set(["a"]);kestrel.selectionChanged()');action('FIND');search(selectionOnly=True);assert state().startswith('2 matches');page.locator('#search-next').click();page.locator('#text-search').click();assert state().startswith('2 matches')
    test('original selection stays fixed while navigating matches',scope)
    def zoom():
        action('FIND');search();page.locator('[data-hit="2"]').click();assert page.evaluate('[...kestrel.doc.selection]')==['b'];page.locator('#select-search-results').click();assert set(page.evaluate('[...kestrel.doc.selection]'))=={'a','b','c'}
    test('result navigation selects real objects and supports select all',zoom)
    def stale():
        action('FIND');search();page.evaluate('kestrel.doc.transaction("Edit",()=>kestrel.doc.add("POINT",{position:[0,0,0]}))');snapshot=page.evaluate('kestrel.doc.snapshot()');page.locator('#replace-all').click();assert 'changed' in state();assert page.evaluate('kestrel.doc.snapshot()')==snapshot
    test('stale results cannot replace newer document text',stale)
    def invalidation():
        action('FIND');search();page.locator('[name="wholeWord"]').check();assert page.locator('#replace-all').is_disabled();assert 'Search settings changed' in state()
    test('changing search options invalidates older replacements',invalidation)
    def fields():
        page.evaluate('Kestrel.Fields.setBinding(kestrel.doc,"a",{version:1,target:"text",template:"{{V}}",sources:[{name:"V",kind:"literal",value:"Valve"}]})');action('FIND');search();assert 'Associative field' in page.locator('#search-results').inner_text();page.locator('#replace-all').click();assert 'skipped 1' in state();assert page.evaluate('kestrel.doc.byId.get("a").text')=='Valve'
    test('Find protects computed fields while replacing other matches',fields)
    def locks():
        page.evaluate('kestrel.doc.transaction("Lock",()=>kestrel.doc.layer("architecture").locked=true)');action('FIND');search();assert state().startswith('4 matches') and '4 read-only' in state();assert page.locator('#replace-all').is_disabled()
    test('locked objects are discoverable but cannot be replaced',locks)
    def hidden():
        page.evaluate('kestrel.doc.transaction("Hide",()=>kestrel.doc.byId.get("a").hidden=true)');action('FIND');search(includeHidden=True);assert '2 read-only' in state();page.locator('#replace-all').click();assert page.evaluate('kestrel.doc.byId.get("a").text')=='Valve valve'
    test('hidden-search setting does not bypass edit restrictions',hidden)
    def injection():
        action('FIND');search(type='MTEXT',replacement=r'\H99x;<script>%%c');page.locator('#replace-current').click();assert page.evaluate('Kestrel.TextSearch.visibleRaw(kestrel.doc.byId.get("b").text,true).text')==r'\H99x;<script>%%c — Ω';assert page.locator('#search-results script').count()==0
    test('replacement formatting and markup are inserted literally',injection)
    def empty():
        action('FIND');search(find='Absent');assert state().startswith('0 matches');assert page.locator('#replace-current').is_disabled()
    test('zero-result searches disable replacement actions',empty)
    def persist():
        action('FIND');search();page.locator('#replace-all').click();page.evaluate('kestrel.closeDialog()')
        with page.expect_download() as dl:action('save')
        raw=json.loads(Path(dl.value.path()).read_text());page.evaluate('(d)=>kestrel.addDocument(Kestrel.Drawing.from(d))',raw);assert page.evaluate('kestrel.doc.byId.get("a").text')=='Gate Gate'
    test('saved and reopened project retains replaced native text',persist)
    def shortcut():
        page.locator('body').click(position={'x':850,'y':500});page.keyboard.press('Control+f');assert page.locator('#text-search').is_visible()
    test('Ctrl F opens native Find outside text entry controls',shortcut)
    def listeners():
        action('FIND');search();page.evaluate('kestrel.closeDialog()');action('DWGPROPS');page.locator('[name="Title"]').fill('Project');page.locator('#modal-submit').click();action('FIND');search();assert state().startswith('4 matches')
    test('reopening unrelated dialogs does not retain stale search listeners',listeners)
    def remember_type():
        action('FIND');search(type='MTEXT');page.evaluate('kestrel.closeDialog()');action('FIND');assert page.locator('[name="type"]').input_value()=='MTEXT';page.locator('#text-search').click();assert state().startswith('1 matches')
    test('reopening Find retains the chosen annotation-type filter',remember_type)
    def screenshot():
        action('FIND');search();page.screenshot(path=str(OUT/'text-search.png'))
    test('search result view renders bounded contextual previews',screenshot)
    b.close()
failed=sum(t['status']=='failed' for t in tests);(OUT/'text-search-browser-results.json').write_text(json.dumps({'passed':len(tests)-failed,'failed':failed,'javascript_errors':errors,'loading':loading,'tests':tests},indent=2)+'\n');print('RESULT',len(tests)-failed,'passed',failed,'failed');sys.exit(bool(failed or errors))
