#!/usr/bin/env python3
"""Regression: insert a project through App.insertData, not the clipboard shortcut."""
from pathlib import Path
import json, os, traceback
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'tests/results'
OUT.mkdir(exist_ok=True)
results, errors = [], []
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH', '/usr/bin/chromium'), headless=True, args=['--no-sandbox'])
    page = browser.new_page(viewport={'width': 1600, 'height': 1000})
    page.set_default_timeout(15000)
    page.on('pageerror', lambda e: errors.append(str(e)))
    if os.environ.get('KESTREL_TEST_URL'):
        page.goto(os.environ['KESTREL_TEST_URL'], wait_until='domcontentloaded')
    else:
        page.set_content((ROOT / 'Kestrel-CAD.html').read_text(), wait_until='domcontentloaded')
    page.wait_for_function('document.documentElement.dataset.ready === "true"')
    def test(name, script):
        before = len(errors)
        try:
            page.evaluate('''(script) => {
                const assert = (ok, message) => { if (!ok) throw Error(message); };
                const K = Kestrel, F = K.Fields;
                const bind = (source, extra = {}) => ({version:1, target:'text', template:'{{Value}}',
                    sources:[{name:'Value', ...source}], precision:2, ...extra});
                eval(script);
            }''', script)
            assert len(errors) == before, errors[before:]
            results.append({'name': name, 'status': 'passed'})
            print('PASS', name, flush=True)
        except Exception as exc:
            traceback.print_exc()
            results.append({'name': name, 'status': 'failed', 'error': str(exc)})
    setup = '''
        const source = new K.Drawing('Source project');
        source.transaction('fixture', () => {
            source.add('LINE', {id:'sourceLine', points:[[0,0,0],[30,40,0]]});
            source.add('TEXT', {id:'label', text:'cache', position:[0,20,0], height:3});
        });
        F.setBinding(source, 'label', bind({kind:'object', entity:'sourceLine', property:'length'}));
        kestrel.addDocument(new K.Drawing('Destination'));
        const dest = kestrel.doc;
        dest.transaction('colliding ID', () => dest.add('LINE', {id:'sourceLine',points:[[0,0,0],[999,0,0]]}));
    '''
    test('insert maps object IDs instead of binding to colliding destination IDs', setup + '''
        const original = source.snapshot(), ids = kestrel.insertData(source.serialize());
        const label = dest.byId.get(ids[1]);
        assert(ids.length === 2 && ids[0] !== 'sourceLine', 'new identities required');
        assert(label.fieldBindings[0].sources[0].entity === ids[0], 'field reference not remapped');
        assert(label.text === '50.00', 'bound to the wrong line');
        assert(dest.byId.get('sourceLine').points[1][0] === 999, 'original modified');
        assert(source.snapshot() === original, 'source mutated');
        dest.transaction('resize inserted source', () => {dest.byId.get(ids[0]).points[1]=[0,80,0];});
        assert(dest.byId.get(ids[1]).text === '80.00', 'inserted field not live');
    ''')
    test('insert remaps aggregates and forward field-to-field references', setup + '''
        source.transaction('add dependents', () => {
            source.add('TEXT', {id:'sum', text:'', position:[0,30,0], height:3});
            source.add('TEXT', {id:'double', text:'', position:[0,40,0], height:3});
        });
        F.setBinding(source,'sum',bind({kind:'aggregate',entities:['sourceLine'],method:'sum',property:'length'}));
        F.setBinding(source,'double',bind({kind:'field',entity:'sum',target:'text'}, {expression:'Value*2',template:'{{Result}}'}));
        const data = source.serialize(); data.entities.reverse();
        const ids = kestrel.insertData(data), map = new Map(data.entities.map((e,i)=>[e.id,ids[i]]));
        assert(dest.byId.get(map.get('sum')).fieldBindings[0].sources[0].entities[0] === map.get('sourceLine'), 'aggregate not mapped');
        assert(dest.byId.get(map.get('double')).fieldBindings[0].sources[0].entity === map.get('sum'), 'field not mapped');
        assert(dest.byId.get(map.get('double')).text === '100.00', 'forward dependency failed');
    ''')
    test('source-context links freeze with refreshed values and dependent chains freeze too', setup + '''
        F.setProperties(source, [{name:'Title',value:'Original title'}]);
        F.setBinding(source,'label',bind({kind:'property',key:'Title'}));
        source.transaction('chained property', () => source.add('TEXT',{id:'chain',text:'',position:[0,30,0],height:3}));
        F.setBinding(source,'chain',bind({kind:'field',entity:'label',target:'text'}));
        F.setProperties(dest, [{name:'Title',value:'Wrong destination title'}]);
        const data=source.serialize();data.entities[1].text='obsolete cache';data.entities[2].text='obsolete cache';
        const untouched=JSON.stringify(data), ids=kestrel.insertData(data);
        assert(dest.byId.get(ids[1]).text==='Original title', 'source field not refreshed');
        assert(dest.byId.get(ids[2]).text==='Original title', 'chain lost source value');
        assert(!dest.byId.get(ids[1]).fieldBindings && !dest.byId.get(ids[2]).fieldBindings, 'unsafe links retained');
        assert(dest.operationWarnings.some(w=>w.includes('frozen')), 'missing freeze warning');
        assert(JSON.stringify(data)===untouched, 'input data mutated');
    ''')
    test('insertion refreshes drawing fields in the source context', setup + '''
        F.setBinding(source,'label',bind({kind:'drawing',property:'name'}));
        const ids=kestrel.insertData(source.serialize());
        assert(dest.byId.get(ids[1]).text==='Source project', 'destination context used');
        assert(!dest.byId.get(ids[1]).fieldBindings, 'foreign drawing link retained');
    ''')
    test('unit conversion keeps numeric object links live and physical units accurate', setup + '''
        source.units='cm';dest.units='mm';
        source.transaction('physical label',()=>source.add('TEXT',{id:'physical',text:'',position:[0,30,0],height:3}));
        F.setBinding(source,'physical',bind({kind:'object',entity:'sourceLine',property:'length',units:'cm'}));
        const ids=kestrel.insertData(source.serialize());
        assert(dest.byId.get(ids[0]).points[1][0]===300, 'geometry not scaled');
        assert(dest.byId.get(ids[1]).text==='500.00', 'native-unit field not updated');
        assert(dest.byId.get(ids[2]).text==='50.00', 'explicit physical units changed');
    ''')
    test('insertion transfers block definitions and field-bearing attributes', setup + '''
        source.transaction('block',()=>{
            K.Production.ensure(source).blocks.push({id:'block',name:'Detail',entities:[],attributes:[{tag:'LEN',value:'?',position:[0,0,0],height:3}]});
            source.add('INSERT',{id:'reference',block:'block',matrix:Array.from(K.Math.M.identity()),attributes:{}});
        });
        F.setBinding(source,'reference',bind({kind:'object',entity:'sourceLine',property:'length'},{target:'attribute:LEN'}));
        const ids=kestrel.insertData(source.serialize()), ref=dest.byId.get(ids[2]);
        assert(dest.production.blocks.some(b=>b.id===ref.block), 'block definition missing');
        assert(ref.attributes.LEN==='50.00', 'attribute field not refreshed');
        assert(ref.fieldBindings[0].sources[0].entity===ids[0], 'attribute field not mapped');
    ''')
    test('insertion is one undoable change and redo preserves the complete reference graph', setup + '''
        kestrel.autosave();const before=dest.snapshot(), history=dest.undoStack.length;
        const ids=kestrel.insertData(source.serialize());
        assert(dest.undoStack.length===history+1, 'not one transaction');
        const after=dest.snapshot();dest.undo();assert(dest.snapshot()===before, 'undo changed preexisting drawing');
        dest.redo();assert(dest.snapshot()===after, 'redo failed');
        assert(dest.byId.get(ids[1]).fieldBindings[0].sources[0].entity===ids[0], 'redo field identity lost');
    ''')
    test('invalid source rejects without changing destination state or history', setup + '''
        const before=dest.snapshot(),history=JSON.stringify([dest.undoStack,dest.redoStack]),data=source.serialize();
        data.entities[1].fieldBindings[0].version=999;
        let failed=false;try{kestrel.insertData(data);}catch(e){failed=true;}
        assert(failed, 'invalid source accepted');
        assert(dest.snapshot()===before, 'drawing mutated');
        assert(JSON.stringify([dest.undoStack,dest.redoStack])===history, 'history mutated');
    ''')
    browser.close()
failed = sum(r['status'] == 'failed' for r in results)
(OUT / 'fields-insert-browser-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'javascript_errors':errors,'tests':results},indent=2)+'\n')
print('RESULT',len(results)-failed,'passed;',failed,'failed; JS errors:',errors)
raise SystemExit(bool(failed or errors))
