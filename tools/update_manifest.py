#!/usr/bin/env python3
"""Refresh package integrity metadata after rebuilding derived assets."""
from pathlib import Path
import datetime
import hashlib
import json

ROOT = Path(__file__).resolve().parent.parent
EXCLUDED = {'.git', '.github', '.import', '_site', '__pycache__', '.venv'}
reports = {}
for name in ('core', 'browser', 'server', 'dxf-interop'):
    path = ROOT / 'tests/results' / (name + '-results.json')
    if path.exists():
        data = json.loads(path.read_text())
        reports[name] = {'passed': data.get('passed'), 'failed': data.get('failed')}
info = {'application': 'Kestrel CAD', 'built_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'tests': reports, 'webgpu_hardware_verified': False, 'native_dwg_codec_verified': False}
(ROOT / 'build-info.json').write_text(json.dumps(info, indent=2) + '\n')
lines = []
for path in sorted(ROOT.rglob('*')):
    rel = path.relative_to(ROOT)
    if any(part in EXCLUDED for part in rel.parts) or path.suffix == '.pyc' or rel.as_posix() == 'SHA256SUMS':
        continue
    if path.is_file() and not path.is_symlink():
        lines.append(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + rel.as_posix())
(ROOT / 'SHA256SUMS').write_text('\n'.join(lines) + '\n')
print(f'Updated checksums for {len(lines)} files.')
