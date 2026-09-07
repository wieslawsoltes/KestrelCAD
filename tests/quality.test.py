#!/usr/bin/env python3
"""Release evidence regression checks; no network access or fabricated app passes."""
from pathlib import Path
import hashlib
import importlib.util
import json
import tempfile

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('quality', ROOT / 'tools/quality.py')
quality = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quality)
results = []

def test(name, fn):
    try:
        fn()
        results.append({'name': name, 'status': 'passed'})
        print('PASS', name)
    except Exception as exc:
        results.append({'name': name, 'status': 'failed', 'error': repr(exc)})
        print('FAIL', name, exc)

def rejects(fn):
    try:
        fn()
    except (ValueError, FileNotFoundError):
        return
    raise AssertionError('Invalid release was accepted')

with tempfile.TemporaryDirectory() as folder:
    root = Path(folder)
    (root / 'tests/results').mkdir(parents=True)
    (root / 'src').mkdir()
    (root / 'index.html').write_text('editor')
    (root / 'src/app.js').write_text('const app = true;')
    (root / 'Kestrel-CAD.html').write_text('bundle')
    report_path = root / 'tests/results/unit-results.json'
    def evidence():
        report_path.write_text(json.dumps({'passed': 1, 'failed': 0, 'tests': [{'name':'real assertion','status':'passed'}]}))
        info = {'status':'passed', 'source_fingerprint':quality.fingerprint(root),
                'standalone_sha256':hashlib.sha256((root/'Kestrel-CAD.html').read_bytes()).hexdigest(),
                'tests':quality.reports(root), 'total_passed':1}
        (root/'build-info.json').write_text(json.dumps(info))
    test('missing verification rejects publication', lambda: rejects(lambda: quality.require_verified(root)))
    evidence()
    test('matching fresh source, bundle and reports permit publication', lambda: quality.require_verified(root))
    def stale_source():
        (root/'src/app.js').write_text('const app = false;')
        rejects(lambda: quality.require_verified(root))
        (root/'src/app.js').write_text('const app = true;')
    test('source edits invalidate test evidence', stale_source)
    def stale_bundle():
        (root/'Kestrel-CAD.html').write_text('changed bundle')
        rejects(lambda: quality.require_verified(root))
        (root/'Kestrel-CAD.html').write_text('bundle')
    test('changed standalone output invalidates publication', stale_bundle)
    def mutated_report():
        data=json.loads(report_path.read_text());data['note']='unverified mutation'
        report_path.write_text(json.dumps(data))
        rejects(lambda: quality.require_verified(root));evidence()
    test('report checksum mutation rejects publication', mutated_report)
    def bad_count():
        report_path.write_text(json.dumps({'passed':99,'failed':0,'tests':[{'status':'passed'}]}))
        rejects(lambda: quality.reports(root));evidence()
    test('claimed counts must match actual check records', bad_count)
    def failed():
        report_path.write_text(json.dumps({'passed':0,'failed':1}))
        rejects(lambda: quality.reports(root));evidence()
    test('a failed suite cannot be published', failed)
    def errors():
        report_path.write_text(json.dumps({'passed':1,'failed':0,'javascript_errors':['uncaught']}))
        rejects(lambda: quality.reports(root));evidence()
    test('uncaught browser errors invalidate verification', errors)
    def invalid_count():
        report_path.write_text(json.dumps({'passed':True,'failed':0}))
        rejects(lambda: quality.reports(root));evidence()
    test('booleans are not accepted as pass counts', invalid_count)
    def status():
        info=json.loads((root/'build-info.json').read_text());info['status']='failed'
        (root/'build-info.json').write_text(json.dumps(info))
        rejects(lambda: quality.require_verified(root));evidence()
    test('failed or interrupted verification cannot pass from partial reports', status)
    def more_suite():
        extra=root/'tests/results/extra-results.json';extra.write_text(json.dumps({'passed':1,'failed':0}))
        rejects(lambda: quality.require_verified(root));extra.unlink();evidence()
    test('added unrecorded suites require a new complete run', more_suite)
    def bad_total():
        info=json.loads((root/'build-info.json').read_text());info['total_passed']=2
        (root/'build-info.json').write_text(json.dumps(info))
        rejects(lambda: quality.require_verified(root));evidence()
    test('aggregate total must match suite totals', bad_total)

failed=sum(t['status']=='failed' for t in results)
(ROOT/'tests/results/quality-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'tests':results},indent=2)+'\n')
raise SystemExit(bool(failed))
