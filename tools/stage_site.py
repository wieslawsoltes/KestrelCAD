#!/usr/bin/env python3
"""Stage the static GitHub Pages site and a complete downloadable source package."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import zipfile

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / '_site'
EXCLUDED = {'.git', '.import', '_site', '__pycache__', '.venv'}


def main() -> None:
    if OUT.exists():
        if OUT.is_symlink():
            raise RuntimeError('Refusing to replace a symbolic-link staging directory')
        shutil.rmtree(OUT)
    OUT.mkdir()
    for name in ('index.html', 'Kestrel-CAD.html', 'README.md', 'VERIFICATION.md', 'LICENSE', '.nojekyll'):
        shutil.copy2(ROOT / name, OUT / name)
    for name in ('src', 'examples', 'previews'):
        shutil.copytree(ROOT / name, OUT / name)
    (OUT / 'tests').mkdir()
    for name in ('webgpu.html', 'gpu.test.js'):
        shutil.copy2(ROOT / 'tests' / name, OUT / 'tests' / name)
    package = OUT / 'Kestrel-CAD.zip'
    with zipfile.ZipFile(package, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(ROOT.rglob('*')):
            rel = path.relative_to(ROOT)
            if any(part in EXCLUDED for part in rel.parts) or path.suffix == '.pyc':
                continue
            if path.is_file() and not path.is_symlink():
                archive.write(path, Path('Kestrel-CAD') / rel)
    info = {
        'application': 'Kestrel CAD',
        'repository': os.environ.get('GITHUB_REPOSITORY', 'wieslawsoltes/KestrelCAD'),
        'commit': os.environ.get('GITHUB_SHA', 'local'),
        'package_sha256': hashlib.sha256(package.read_bytes()).hexdigest(),
        'dwg_bridge': 'Local server only; not available on GitHub Pages',
    }
    (OUT / 'deployment.json').write_text(json.dumps(info, indent=2) + '\n')
    print(f'Staged {len(list(OUT.rglob("*")))} entries at {OUT}')


if __name__ == '__main__':
    main()
