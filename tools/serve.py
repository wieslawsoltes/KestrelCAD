#!/usr/bin/env python3
"""Kestrel CAD localhost server and optional LibreDWG conversion bridge.

No pip dependencies. Run from any directory: python3 tools/serve.py [--port 8000].
Converters are external executables, never downloaded or bundled by this app.
Only trusted local drawings should be passed to an external native codec.
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import webbrowser

ROOT = Path(__file__).resolve().parent.parent
MAX_BYTES = 64 * 1024 * 1024
CONVERT_LOCK = threading.BoundedSemaphore(1)


def converter(name: str) -> str | None:
    """Allow an explicit absolute executable path or normal PATH lookup."""
    override = os.environ.get('KESTREL_' + name.upper())
    if override:
        p = Path(override).expanduser().resolve()
        return str(p) if p.is_file() and os.access(p, os.X_OK) else None
    return shutil.which(name)


def capabilities() -> dict:
    read, write = converter('dwg2dxf'), converter('dxf2dwg')
    return {
        'application': 'Kestrel CAD bridge', 'version': '1.0.0',
        'dwgRead': bool(read), 'dwgWrite': bool(write),
        'brep': bool(importlib.util.find_spec('cadquery')),
        'brepProvider': 'OpenCascade via CadQuery (not ACIS)',
        'reason': ('Separate local converters detected; interoperability still depends on codec and DXF entity support.'
                   if read or write else 'GNU LibreDWG converters were not found on PATH. DXF and native project files work without them.'),
        'limits': {'inputBytes': MAX_BYTES, 'outputBytes': MAX_BYTES, 'timeoutSeconds': 60},
    }


class Handler(SimpleHTTPRequestHandler):
    server_version = 'KestrelLocal/1.0'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'same-origin')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def local_request(self, post: bool = False) -> bool:
        host = self.headers.get('Host', '')
        allowed = {f'localhost:{self.server.server_port}', f'127.0.0.1:{self.server.server_port}'}
        if host not in allowed:
            self.json_response(403, {'error': 'Only a localhost Host header is allowed.'})
            return False
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + host:
            self.json_response(403, {'error': 'Cross-origin requests are not allowed.'})
            return False
        if post and self.headers.get('X-Kestrel-Client') != '1':
            self.json_response(403, {'error': 'Missing local application request header.'})
            return False
        return True

    def json_response(self, status: int, data: dict):
        content = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        if not self.local_request():
            return
        path = urlsplit(self.path).path
        if path == '/api/capabilities':
            self.json_response(200, capabilities())
        elif path.startswith('/api/'):
            self.json_response(404, {'error': 'Unknown API endpoint.'})
        elif path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
        else:
            # Disallow symbolic links escaping the package directory.
            translated = Path(self.translate_path(self.path)).resolve()
            if not translated.is_relative_to(ROOT):
                self.send_error(403, 'Path outside application root')
                return
            super().do_GET()

    def do_HEAD(self):
        if self.local_request():
            translated = Path(self.translate_path(self.path)).resolve()
            if not translated.is_relative_to(ROOT):
                self.send_error(403)
            else:
                super().do_HEAD()

    def list_directory(self, path):
        self.send_error(403, 'Directory listings are disabled')
        return None

    def do_POST(self):
        if not self.local_request(post=True):
            return
        if urlsplit(self.path).path == '/api/kernel':
            self.native_worker('kernel.py')
            return
        routes = {
            '/api/convert/dwg-to-dxf': ('dwg2dxf', '.dwg', '.dxf', 'application/dxf'),
            '/api/convert/dxf-to-dwg': ('dxf2dwg', '.dxf', '.dwg', 'application/octet-stream'),
        }
        route = routes.get(urlsplit(self.path).path)
        if not route:
            self.json_response(404, {'error': 'Unknown conversion endpoint.'})
            return
        name, source_ext, output_ext, mime = route
        exe = converter(name)
        if not exe:
            self.json_response(503, {'error': f'{name} is not installed. Install GNU LibreDWG separately or exchange ASCII DXF.'})
            return
        if self.headers.get('Transfer-Encoding'):
            self.json_response(400, {'error': 'Chunked request bodies are not supported.'})
            return
        try:
            length = int(self.headers.get('Content-Length', '-1'))
        except ValueError:
            length = -1
        if not 1 <= length <= MAX_BYTES:
            self.json_response(413, {'error': 'Request body must be between 1 byte and 64 MiB.'})
            return
        if not CONVERT_LOCK.acquire(blocking=False):
            self.json_response(429, {'error': 'Another local conversion is running.'})
            return
        try:
            self.connection.settimeout(20)
            content = self.rfile.read(length)
            if len(content) != length:
                raise ValueError('Incomplete request body.')
            if source_ext == '.dwg' and not content.startswith((b'AC10', b'AC1.', b'AC2.', b'MC0.0')):
                raise ValueError('Input does not have a recognized DWG signature.')
            with tempfile.TemporaryDirectory(prefix='kestrel-cad-') as temp:
                directory = Path(temp)
                source, output = directory / ('input' + source_ext), directory / ('output' + output_ext)
                source.write_bytes(content)
                # Fixed argument list, fixed filenames and isolated cwd: no shell or user flags.
                args = [exe, '-v0', '-o', str(output)]
                if name == 'dxf2dwg':
                    args += ['-a', 'r2000']
                args.append(str(source))
                # Keep potentially verbose converter diagnostics out of RAM.
                with (directory / 'codec.log').open('w+b') as log:
                    result = subprocess.run(args, cwd=temp, stdin=subprocess.DEVNULL,
                                            stdout=log, stderr=subprocess.STDOUT,
                                            timeout=60, check=False, shell=False)
                    log.seek(0, os.SEEK_END)
                    log.seek(max(0, log.tell() - 3000))
                    detail = log.read(3000).decode('utf-8', 'replace').strip()
                if result.returncode != 0 or not output.is_file():
                    raise ValueError(f'{name} failed (exit {result.returncode}). {detail}')
                if not 1 <= output.stat().st_size <= MAX_BYTES:
                    raise ValueError('Converted output is empty or exceeds 64 MiB.')
                data = output.read_bytes()
                if output_ext == '.dwg' and not data.startswith(b'AC10'):
                    raise ValueError('Converter output is not a recognized DWG file.')
                if output_ext == '.dxf' and b'SECTION' not in data[:4096]:
                    raise ValueError('Converter did not produce an ASCII DXF file.')
                self.send_response(200)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Content-Disposition', f'attachment; filename="converted{output_ext}"')
                self.end_headers()
                self.wfile.write(data)
        except subprocess.TimeoutExpired:
            self.json_response(504, {'error': 'The local codec exceeded the 60-second conversion limit.'})
        except (OSError, ValueError) as error:
            self.json_response(422, {'error': str(error)[:3500]})
        finally:
            CONVERT_LOCK.release()


    def native_worker(self, script):
        """Execute one allowlisted native task in a disposable, bounded subprocess."""
        if script not in ('kernel.py', 'font_engine.py'):
            self.json_response(404, {'error': 'Unknown worker.'})
            return
        if self.headers.get('Transfer-Encoding') or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            self.json_response(400, {'error': 'A length-delimited JSON request is required.'})
            return
        try:
            length = int(self.headers.get('Content-Length', '-1'))
        except ValueError:
            length = -1
        if not 1 <= length <= MAX_BYTES:
            self.json_response(413, {'error': 'Request size must be between 1 byte and 64 MiB.'})
            return
        if not CONVERT_LOCK.acquire(blocking=False):
            self.json_response(429, {'error': 'Another native operation is running.'})
            return
        try:
            self.connection.settimeout(20)
            content = self.rfile.read(length)
            if len(content) != length:
                raise ValueError('Incomplete request body.')
            # Parsing here rejects malformed input before starting expensive native imports.
            if not isinstance(json.loads(content), dict):
                raise ValueError('Expected a structured request object.')
            with tempfile.TemporaryDirectory(prefix='kestrel-native-') as tmp:
                with (Path(tmp)/'result.json').open('w+b') as output, (Path(tmp)/'worker.log').open('w+b') as log:
                    result = subprocess.run([sys.executable, str(ROOT/'tools'/script)], input=content,
                                            stdout=output, stderr=log, cwd=tmp, timeout=60,
                                            check=False, shell=False)
                    output.seek(0, os.SEEK_END)
                    if output.tell() > MAX_BYTES:
                        raise ValueError('Native result exceeds 64 MiB.')
                    output.seek(0)
                    if result.returncode:
                        raise ValueError('Native worker failed. The drawing was not modified.')
                    response = json.load(output)
            self.json_response(422 if 'error' in response else 200, response)
        except subprocess.TimeoutExpired:
            self.json_response(504, {'error': 'Native operation exceeded the 60-second time limit.'})
        except (OSError, ValueError) as error:
            self.json_response(422, {'error': str(error)[:2000]})
        finally:
            CONVERT_LOCK.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--open', action='store_true', help='Open the local app in your default browser')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('Port must be between 1024 and 65535.')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.daemon_threads = True
    url = f'http://localhost:{args.port}'
    print(f'Kestrel CAD — {url}\nServing {ROOT}\nDWG codec: {capabilities()["reason"]}\nPress Ctrl+C to stop.', flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
