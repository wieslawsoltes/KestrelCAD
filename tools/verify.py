#!/usr/bin/env python3
"""Run the current source test suites and rebuild the standalone app. No stale pass claims."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys,datetime
ROOT=Path(__file__).resolve().parent.parent
p=argparse.ArgumentParser();p.add_argument('--previews',action='store_true');args=p.parse_args()
def run(*command):subprocess.run(command,cwd=ROOT,check=True)
(ROOT/'tests/results').mkdir(exist_ok=True);(ROOT/'examples').mkdir(exist_ok=True)
run('node','tests/core.test.js');run('node','tests/production.test.js')
run(sys.executable,'tools/build.py')
run(sys.executable,'tests/server.test.py');run(sys.executable,'tests/browser.test.py')
run(sys.executable,'tests/production.browser.py');run(sys.executable,'tests/dxf_interop.py');run(sys.executable,'tests/production_interop.py')
for test in ('constraints.test.js','dynamic.test.js','preservation.test.js','shx.test.js'):
    if (ROOT/'tests'/test).exists():run('node','tests/'+test)
for test in ('kernel.test.py','advanced.browser.py'):
    if (ROOT/'tests'/test).exists():run(sys.executable,'tests/'+test)
if args.previews:
    import shutil
    (ROOT/'previews').mkdir(exist_ok=True)
    shutil.copy2(ROOT/'tests/results/production-ui.png',ROOT/'previews/kestrel-production.png')
reports={}
for f in sorted((ROOT/'tests/results').glob('*results.json')):
    d=json.loads(f.read_text());reports[f.stem]={'passed':d.get('passed'),'failed':d.get('failed')}
info={'application':'Kestrel CAD','built_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'tests':reports,'webgpu_hardware_verified':False,'native_dwg_codec_verified':False}
(ROOT/'build-info.json').write_text(json.dumps(info,indent=2)+'\n')
print('Verified current source:',json.dumps(reports))
