#!/usr/bin/env python3
"""Capture the actual running standalone UI; requires test-only Playwright.
These screenshots document the Canvas compatibility path, not a GPU benchmark.
"""
from pathlib import Path
import json
import os
import re
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'previews'
OUT.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'), headless=True, args=['--no-sandbox'])
    page = browser.new_page(viewport={'width':1600, 'height':1000}, device_scale_factor=1)
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.set_content((ROOT/'Kestrel-CAD.html').read_text(),wait_until='domcontentloaded')
    page.wait_for_function('document.documentElement.dataset.ready === "true"',timeout=30000)
    page.mouse.move(10,10)
    page.wait_for_timeout(1300)
    page.screenshot(path=str(OUT/'kestrel-2d-dark.png'))
    page.evaluate("kestrel.run('theme')")
    page.wait_for_timeout(400)
    page.screenshot(path=str(OUT/'kestrel-2d-light.png'))
    page.evaluate("kestrel.run('theme');kestrel.run('demo-3d')")
    page.wait_for_timeout(4000)
    page.screenshot(path=str(OUT/'kestrel-3d-dark.png'))
    diagnostics=page.evaluate('kestrel.diagnosticData()')
    (OUT/'capture-info.json').write_text(json.dumps({'renderer':diagnostics,'javascript_errors':errors,'description':'Actual offline standalone app screenshots; Canvas compatibility renderer.'},indent=2))
    assert not errors,errors
    # Verify that the GPU harness honestly says UNAVAILABLE in this context.
    html=(ROOT/'tests/webgpu.html').read_text()
    def inline(match):
        code=(ROOT/'tests'/match.group(1)).resolve().read_text()
        return '<script>'+code.replace('</script','<\\/script')+'</script>'
    html=re.sub(r'<script src="([^"]+)"></script>',inline,html)
    page.set_content(html,wait_until='domcontentloaded')
    page.locator('#run').click()
    page.wait_for_function('!!window.kestrelGPUReport')
    report=page.evaluate('kestrelGPUReport')
    assert report['status'].startswith('UNAVAILABLE'),report
    assert report['passed']==0
    (ROOT/'tests/results/gpu-environment.json').write_text(json.dumps(report,indent=2))
    browser.close()
    print('Captured actual previews and verified unavailable-GPU reporting.')
