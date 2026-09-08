"""Fresh, source-bound verification metadata used by the runner and publisher."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path


def fingerprint(root: Path) -> str:
    paths = [root / 'index.html']
    paths += sorted(root.glob('requirements*.txt'))
    for folder in ('src', 'tools', '.github/workflows', 'third_party'):
        paths += sorted(p for p in (root / folder).rglob('*') if p.is_file()
                        and '__pycache__' not in p.parts and p.suffix != '.pyc')
    paths += sorted(p for p in (root / 'tests').glob('*') if p.is_file()
                    and p.suffix in ('.js', '.py', '.html'))
    paths += [p for p in (root / 'tests/fixtures').glob('unicode-bidi-sample.json') if p.is_file()]
    h = hashlib.sha256()
    for path in sorted(set(paths)):
        h.update(path.relative_to(root).as_posix().encode() + b'\0')
        h.update(hashlib.sha256(path.read_bytes()).digest())
    return h.hexdigest()


def reports(root: Path) -> dict:
    out = {}
    for path in sorted((root / 'tests/results').glob('*results.json')):
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            raise ValueError(f'Invalid result object: {path.name}')
        for key in ('passed', 'failed'):
            if type(data.get(key)) is not int or data[key] < 0:
                raise ValueError(f'Invalid {key} count: {path.name}')
        if data['failed'] or data.get('javascript_errors'):
            raise ValueError(f'Failed suite: {path.name}')
        if isinstance(data.get('tests'), list):
            passed = sum(t.get('status') == 'passed' for t in data['tests'])
            failed = sum(t.get('status') == 'failed' for t in data['tests'])
            if (passed, failed) != (data['passed'], data['failed']):
                raise ValueError(f'Result counts disagree with checks: {path.name}')
        out[path.stem] = {'passed': data['passed'], 'failed': data['failed'],
                          'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    if not out:
        raise ValueError('No verification reports exist. Run tools/verify.py first.')
    return out


def require_verified(root: Path) -> dict:
    info = json.loads((root / 'build-info.json').read_text())
    if info.get('status') != 'passed' or info.get('source_fingerprint') != fingerprint(root):
        raise ValueError('Verification is missing, failed, or does not match current source.')
    if info.get('standalone_sha256') != hashlib.sha256((root / 'Kestrel-CAD.html').read_bytes()).hexdigest():
        raise ValueError('Standalone build changed after verification.')
    current = reports(root)
    if info.get('tests') != current:
        raise ValueError('Test reports changed after verification.')
    if info.get('total_passed') != sum(s['passed'] for s in current.values()):
        raise ValueError('Verification total does not match its suites.')
    return info
