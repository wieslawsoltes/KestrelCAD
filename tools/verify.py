#!/usr/bin/env python3
"""Test current sources, build the editor and write source-bound release evidence."""
from __future__ import annotations
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from quality import fingerprint, reports

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previews', action='store_true')
    args = parser.parse_args()
    out = ROOT / 'tests/results'
    out.mkdir(exist_ok=True)
    (ROOT / 'examples').mkdir(exist_ok=True)
    for report in out.glob('*results.json'):
        report.unlink()
    source = fingerprint(ROOT)
    info = {'application': 'Kestrel CAD', 'status': 'running',
            'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'source_commit': os.environ.get('GITHUB_SHA', 'local'),
            'source_head': os.environ.get('SOURCE_HEAD', os.environ.get('GITHUB_SHA', 'local')),
            'source_fingerprint': source, 'python': sys.version.split()[0],
            'webgpu_hardware_verified': False, 'native_dwg_codec_verified': False,
            'completed_commands': []}
    def save():
        (ROOT / 'build-info.json').write_text(json.dumps(info, indent=2) + '\n')
    save()
    def run(*command: str, test: bool = True):
        print('RUN', ' '.join(command), flush=True)
        previous = set(out.glob('*results.json'))
        started = time.monotonic()
        subprocess.run(command, cwd=ROOT, check=True)
        if test and not set(out.glob('*results.json')) - previous:
            raise RuntimeError('Test suite did not create a fresh result report: ' + ' '.join(command))
        info['completed_commands'].append({'command': list(command), 'seconds': round(time.monotonic()-started, 3)})
    try:
        # These are required, not silently optional. New conventionally named suites
        # join automatically, so adding a test cannot accidentally omit it from CI.
        required = ('core.test.js', 'production.test.js', 'constraints.test.js',
                    'kernel-client.test.js', 'server.test.py', 'kernel.test.py',
                    'browser.test.py', 'production.browser.py', 'advanced.browser.py',
                    'constraints.browser.py', 'dxf_interop.py', 'production_interop.py')
        for filename in required:
            if not (ROOT / 'tests' / filename).is_file():
                raise RuntimeError('Required suite missing: ' + filename)
        nodes = sorted((ROOT / 'tests').glob('*.test.js'), key=lambda p: (p.name != 'core.test.js', p.name != 'production.test.js', p.name))
        for path in nodes:
            if path.name != 'gpu.test.js':  # Explicit hardware page; never counted as a Node pass.
                run('node', str(path.relative_to(ROOT)))
        run(sys.executable, 'tools/build.py', test=False)
        for path in sorted((ROOT / 'tests').glob('*.test.py')):
            if path.name != 'browser.test.py':
                run(sys.executable, str(path.relative_to(ROOT)))
        run(sys.executable, 'tests/browser.test.py')
        for path in sorted((ROOT / 'tests').glob('*.browser.py')):
            run(sys.executable, str(path.relative_to(ROOT)))
        for path in sorted((ROOT / 'tests').glob('*_interop.py')):
            run(sys.executable, str(path.relative_to(ROOT)))
        if args.previews:
            (ROOT / 'previews').mkdir(exist_ok=True)
            for source_name, target_name in (('production-ui.png', 'kestrel-production.png'),
                                             ('native-solids.png', 'kestrel-native-solids.png'),
                                             ('parametric-sketch.png', 'kestrel-parametric.png'),
                                             ('dynamic-blocks.png', 'kestrel-dynamic-blocks.png'),
                                             ('font-styles.png', 'kestrel-font-styles.png'),
                                             ('mtext-composition.png', 'kestrel-mtext.png'),
                                             ('spatial-assembly.png', 'kestrel-spatial-assembly.png')):
                if (out / source_name).exists():
                    shutil.copy2(out / source_name, ROOT / 'previews' / target_name)
        if fingerprint(ROOT) != source:
            raise RuntimeError('A test modified application/test source during verification.')
        info.update(status='passed', tests=reports(ROOT),
                    standalone_sha256=hashlib.sha256((ROOT / 'Kestrel-CAD.html').read_bytes()).hexdigest())
        info['total_passed'] = sum(s['passed'] for s in info['tests'].values())
        info['total_failed'] = 0
        lines = ['# Verification of current source', '',
                 f"Source commit: `{info['source_commit']}`", '',
                 f"**{info['total_passed']} checks passed; zero failed.**", '',
                 '| Suite | Passed | Failed |', '|---|---:|---:|']
        lines += [f"| {name} | {s['passed']} | {s['failed']} |" for name, s in info['tests'].items()]
        lines += ['', 'Browser suites include real UI operations and explicit scripted fixture setup.',
                  'Native kernel tests use the installed OpenCascade engine. Mocked DWG bridge tests do not verify a DWG codec.',
                  '**Hardware WebGPU execution and real native DWG conversion are not verified by these suites.**',
                  '', 'Full commands, timing, source/build/report hashes and runtime are in `build-info.json`.']
        (ROOT / 'VERIFICATION.md').write_text('\n'.join(lines) + '\n')
        print(f"RESULT {info['total_passed']} passed; 0 failed across {len(info['tests'])} suites.", flush=True)
    except BaseException as exc:
        info.update(status='failed', error=str(exc))
        raise
    finally:
        info['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save()


if __name__ == '__main__':
    main()
