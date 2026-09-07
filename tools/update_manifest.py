#!/usr/bin/env python3
"""Refresh package checksums without fabricating or overwriting test results."""
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parent.parent
EXCLUDED = {'.git', '.github', '.import', '.transfer', '_site', '__pycache__', '.venv'}

def main():
    lines = []
    for path in sorted(ROOT.rglob('*')):
        rel = path.relative_to(ROOT)
        if any(part in EXCLUDED for part in rel.parts) or path.suffix == '.pyc' or rel.as_posix() == 'SHA256SUMS':
            continue
        if path.is_file() and not path.is_symlink():
            lines.append(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + rel.as_posix())
    (ROOT / 'SHA256SUMS').write_text('\n'.join(lines) + '\n')
    print(f'Updated checksums for {len(lines)} files. Verification metadata is unchanged.')

if __name__ == '__main__':
    main()
