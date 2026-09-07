#!/usr/bin/env python3
"""Real localhost HTTP tests plus explicitly MOCKED codec-protocol checks.
No external DWG converter is installed, invoked, or claimed to work by this suite.
Uses only the Python standard library. No browser policy modifications.
"""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('kestrel_local_server', ROOT / 'tools/serve.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

class QuietHandler(bridge.Handler):
    def log_message(self, *args):
        pass

server = bridge.ThreadingHTTPServer(('127.0.0.1', 0), QuietHandler)
server.daemon_threads = True
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
url = f'http://127.0.0.1:{server.server_port}'
results = []

def request(path='/', method='GET', body=None, headers=None):
    req = urllib.request.Request(url + path, data=body, method=method, headers=headers or {})
    try:
        response = urllib.request.urlopen(req, timeout=5)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.status, response.read(), dict(response.headers)

def test(name, fn):
    try:
        fn()
        results.append({'name': name, 'status': 'passed'})
        print('PASS', name, flush=True)
    except Exception as error:
        results.append({'name': name, 'status': 'failed', 'error': repr(error)})
        print('FAIL', name, repr(error), flush=True)

def eq(a, b):
    assert a == b, (a, b)

def static_app():
    status, body, headers = request()
    eq(status, 200)
    assert b'Kestrel CAD' in body
    eq(headers['X-Content-Type-Options'], 'nosniff')
    eq(headers['X-Frame-Options'], 'DENY')

def codec_missing():
    with patch.object(bridge, 'converter', return_value=None):
        status, body, _ = request('/api/capabilities')
        eq(status, 200)
        data = json.loads(body)
        eq(data['dwgRead'], False)
        eq(data['dwgWrite'], False)
        status, body, _ = request('/api/convert/dwg-to-dxf', 'POST', b'AC1015', {'X-Kestrel-Client':'1'})
        eq(status, 503)
        assert 'not installed' in json.loads(body)['error']

def no_symlink_escape():
    with tempfile.TemporaryDirectory() as temp:
        secret = Path(temp) / 'secret.txt'
        secret.write_text('not exposed')
        link = ROOT / 'tests' / '_escape_test.txt'
        try:
            link.symlink_to(secret)
            eq(request('/tests/_escape_test.txt')[0], 403)
        finally:
            link.unlink(missing_ok=True)

def mocked_protocol():
    # A test double verifies the bridge's arguments and IO checks. These bytes
    # are deliberately not a real DWG file and never reach the editor.
    seen = []
    def fake_run(args, **kwargs):
        eq(kwargs['shell'], False)
        eq(kwargs['timeout'], 60)
        eq(kwargs['stdin'], subprocess.DEVNULL)
        assert isinstance(args, list)
        output = Path(args[args.index('-o') + 1])
        assert output.parent == Path(kwargs['cwd'])
        source = Path(args[-1])
        seen.append((args, source.read_bytes()))
        output.write_bytes(b'0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n' if output.suffix == '.dxf' else b'AC1015_MOCK_PROTOCOL_ONLY')
        return subprocess.CompletedProcess(args, 0)
    with patch.object(bridge, 'converter', return_value='/explicit/mock-codec'), patch.object(bridge.subprocess, 'run', side_effect=fake_run):
        headers = {'X-Kestrel-Client':'1', 'Origin':url}
        eq(request('/api/convert/dwg-to-dxf', 'POST', b'AC1015_mock', headers)[0], 200)
        time.sleep(.04)
        eq(request('/api/convert/dxf-to-dwg', 'POST', b'0\nSECTION\n0\nEOF', headers)[0], 200)
        time.sleep(.04)
        assert '-a' in seen[1][0] and 'r2000' in seen[1][0]
        eq(seen[0][1], b'AC1015_mock')
        eq(request('/api/convert/dwg-to-dxf', 'POST', b'not a dwg', headers)[0], 422)
        eq(len(seen), 2)
        time.sleep(.04)
        eq(request('/api/convert/dxf-to-dwg', 'POST', b'', headers)[0], 413)

def bad_codec_output():
    def fake_run(args, **kwargs):
        Path(args[args.index('-o') + 1]).write_bytes(b'not the requested format')
        return subprocess.CompletedProcess(args, 0)
    with patch.object(bridge, 'converter', return_value='/mock'), patch.object(bridge.subprocess, 'run', side_effect=fake_run):
        eq(request('/api/convert/dxf-to-dwg', 'POST', b'0\nSECTION', {'X-Kestrel-Client':'1'})[0], 422)

def timeout_handling():
    with patch.object(bridge, 'converter', return_value='/mock'), patch.object(bridge.subprocess, 'run', side_effect=subprocess.TimeoutExpired('mock', 60)):
        eq(request('/api/convert/dxf-to-dwg', 'POST', b'0\nSECTION', {'X-Kestrel-Client':'1'})[0], 504)
    assert bridge.CONVERT_LOCK.acquire(blocking=False), 'Conversion lock not released'
    bridge.CONVERT_LOCK.release()

try:
    test('HTTP serves the actual application with security headers', static_app)
    test('HTTP serves JavaScript and the hardware validation page', lambda: (eq(request('/src/renderer.js')[0], 200), eq(request('/tests/webgpu.html')[0], 200)))
    test('Missing converters are honestly reported by capabilities and conversion API', codec_missing)
    test('Unrecognized Host header is rejected', lambda: eq(request(headers={'Host':'external.example'})[0], 403))
    test('Cross-origin reads are rejected', lambda: eq(request(headers={'Origin':'https://external.example'})[0], 403))
    test('Conversion requires a local application header', lambda: eq(request('/api/convert/dwg-to-dxf','POST',b'AC1015')[0],403))
    test('Cross-origin conversion is rejected', lambda: eq(request('/api/convert/dwg-to-dxf','POST',b'AC1015',{'X-Kestrel-Client':'1','Origin':'https://external.example'})[0],403))
    test('Unknown API endpoint returns 404', lambda: eq(request('/api/unknown')[0], 404))
    test('Directory listing is disabled', lambda: eq(request('/src/')[0], 403))
    test('Symbolic links cannot expose files outside the package', no_symlink_escape)
    test('MOCKED codec bridge verifies fixed arguments, signatures, limits and outputs', mocked_protocol)
    test('MOCKED malformed codec output is rejected', bad_codec_output)
    test('MOCKED native-codec timeout returns 504 and releases lock', timeout_handling)
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)

report = {'suite':'Local HTTP server and mocked codec protocol',
          'passed':sum(r['status']=='passed' for r in results),
          'failed':sum(r['status']=='failed' for r in results),
          'actual_native_dwg_conversion_tested':False,
          'tests':results}
out = ROOT/'tests/results'
out.mkdir(exist_ok=True)
(out/'server-results.json').write_text(json.dumps(report, indent=2))
print('RESULT', report['passed'], 'passed;', report['failed'], 'failed')
sys.exit(report['failed'] > 0)
