#!/usr/bin/env python3
"""Real standalone browser workflows for the productivity feature batch."""
from pathlib import Path
import csv
import io
import json
import os
import sys
import traceback
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'tests/results'
OUT.mkdir(exist_ok=True)
results, errors = [], []
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH', p.chromium.executable_path), headless=True, args=['--no-sandbox'])
    page = browser.new_page(viewport={'width': 1600, 'height': 1000}, accept_downloads=True)
    page.set_default_timeout(20000)
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto((ROOT / 'Kestrel-CAD.html').as_uri(), wait_until='domcontentloaded')
    page.wait_for_function('document.documentElement.dataset.ready === "true" && Kestrel.Productivity.installed')
    def action(name):
        page.evaluate('(name) => kestrel.run(name)', name)
    def submit(fields=None):
        for key, value in (fields or {}).items():
            element = page.locator('#modal [name="' + key + '"]')
            if element.evaluate('(e) => e.tagName') == 'SELECT':
                element.select_option(str(value))
            else:
                element.fill(str(value))
        page.locator('#modal-submit').click()
        page.wait_for_function('!document.querySelector("#modal").open || !document.querySelector("#modal-error").hidden')
        assert not page.locator('#modal-error').is_visible(), page.locator('#modal-error').inner_text()
    def fixture():
        action('new')
        page.evaluate("""() => { const d=kestrel.doc; d.transaction('Fixture',()=>{
            d.add('LINE',{points:[[0,0,0],[20,0,0]]});
            d.add('CIRCLE',{center:[30,0,0],radius:5});
            d.selection=new Set([d.entities[0].id]);
        }); kestrel.selectionChanged(); }""")
    def select(index=0):
        page.evaluate('(i) => {kestrel.doc.selection=new Set([kestrel.doc.entities[i].id]);kestrel.selectionChanged();}', index)
    def test(name, fn):
        before = len(errors)
        try:
            page.evaluate('kestrel.closeDialog();kestrel.cancel(false)')
            fixture()
            fn()
            assert len(errors) == before, errors[before:]
            results.append({'name': name, 'status': 'passed'})
            print('PASS', name, flush=True)
        except Exception as error:
            traceback.print_exc()
            results.append({'name': name, 'status': 'failed', 'error': str(error)})
            page.evaluate('kestrel.closeDialog();kestrel.cancel(false)')
    def ribbon():
        page.locator('[data-ribbon="Productivity"]').click()
        page.locator('#ribbon [data-action="productivity-select"]').click()
        submit({'type':'CIRCLE'})
        assert page.evaluate('kestrel.doc.selected()[0].type') == 'CIRCLE'
    test('Productivity ribbon quick-select changes actual selection', ribbon)
    def divide():
        action('productivity-divide')
        submit({'value':5})
        assert page.evaluate('kestrel.doc.entities.filter(e=>e.type==="POINT").map(e=>e.position[0])') == [4,8,12,16]
        action('undo')
        assert page.evaluate('kestrel.doc.entities.length') == 2
        action('redo')
        assert page.evaluate('kestrel.doc.entities.length') == 6
    test('Divide creates exact curve stations with one undo and redo', divide)
    def measure():
        action('productivity-measure')
        submit({'value':4})
        assert page.evaluate('kestrel.doc.entities.filter(e=>e.type==="POINT").map(e=>e.position[0])') == [4,8,12,16,20]
    test('Measure creates editable equally spaced points', measure)
    def lengthen():
        action('productivity-lengthen')
        submit({'mode':'delta','value':7,'end':'start'})
        assert page.evaluate('kestrel.doc.entities[0].points') == [[-7,0,0],[20,0,0]]
        action('undo')
        assert page.evaluate('kestrel.doc.entities[0].points[0]') == [0,0,0]
    test('Lengthen dialog preserves the opposite endpoint and supports undo', lengthen)
    def reverse():
        action('productivity-reverse')
        assert page.evaluate('kestrel.doc.entities[0].points') == [[20,0,0],[0,0,0]]
        action('undo')
        assert page.evaluate('kestrel.doc.entities[0].points') == [[0,0,0],[20,0,0]]
    test('Reverse edits actual curve direction without changing its locus', reverse)
    def quantities():
        page.evaluate('kestrel.doc.selection.clear();kestrel.selectionChanged()')
        action('productivity-count')
        assert 'CIRCLE' in page.locator('#modal').inner_text()
        assert 'LINE' in page.locator('#modal').inner_text()
        page.evaluate('kestrel.closeDialog()')
    test('Count report contains real drawing quantities', quantities)
    def download_csv():
        page.evaluate('kestrel.doc.selection.clear();kestrel.selectionChanged()')
        action('productivity-extract')
        with page.expect_download() as download:
            submit({'format':'csv'})
        rows = list(csv.DictReader(io.StringIO(Path(download.value.path()).read_text())))
        assert len(rows) == 2
        assert rows[0]['type'] == 'LINE' and float(rows[0]['length']) == 20
        assert rows[1]['type'] == 'CIRCLE'
    test('Data extraction downloads actual parseable CSV', download_csv)
    def extraction_table():
        page.evaluate('kestrel.doc.selection.clear();kestrel.selectionChanged()')
        action('productivity-extract')
        submit({'format':'table','position':'10,20,0'})
        assert page.evaluate('kestrel.doc.entities.at(-1).type') == 'TABLE'
        assert page.evaluate('kestrel.doc.entities.at(-1).cells.length') == 3
        assert page.evaluate('Kestrel.Drawing.from(kestrel.doc.serialize()).entities.at(-1).cells[1][3]') == '20'
        action('undo')
        assert page.evaluate('kestrel.doc.entities.length') == 2
    test('Data extraction creates a persistent editable table snapshot', extraction_table)
    def layers():
        action('productivity-layer-save')
        submit({'name':'Working'})
        page.evaluate("kestrel.doc.transaction('Hide layer',()=>{kestrel.doc.layer(kestrel.doc.entities[0]).visible=false;})")
        action('productivity-layer-restore')
        submit({'name':'Working'})
        assert page.evaluate('kestrel.doc.visible(kestrel.doc.entities[0])')
        action('undo')
        assert not page.evaluate('kestrel.doc.visible(kestrel.doc.entities[0])')
    test('Layer state dialogs restore visibility with undo', layers)
    def stale():
        action('productivity-divide')
        page.evaluate("kestrel.doc.transaction('New edit',()=>kestrel.doc.add('POINT',{position:[0,10,0]}))")
        page.locator('#modal-submit').click()
        page.wait_for_function('!document.querySelector("#modal-error").hidden')
        assert 'changed' in page.locator('#modal-error').inner_text().lower()
        assert page.evaluate('kestrel.doc.entities.length') == 3
        page.evaluate('kestrel.closeDialog()')
    test('Stale station dialog rejects without applying a partial edit', stale)
    page.screenshot(path=str(OUT/'productivity-tools.png'))
    browser.close()
failed = sum(row['status']=='failed' for row in results)
(OUT/'productivity-browser-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'javascript_errors':errors,'tests':results},indent=2))
print('Productivity browser:',len(results)-failed,'passed;',failed,'failed; JavaScript errors:',errors)
sys.exit(bool(failed or errors))
