#!/usr/bin/env python3
"""One-time, fail-closed integration of the additive productivity modules.

The resulting PR contains ordinary readable source. This installer is removed
from the final feature commit; it is not part of the runtime application.
"""
from pathlib import Path
import ast
import re
import subprocess
import sys
ROOT = Path(__file__).resolve().parent.parent
index = ROOT / 'index.html'
source = index.read_text()
for name in ('productivity.js', 'productivity-ui.js'):
    if not (ROOT / 'src' / name).is_file():
        raise RuntimeError('Missing feature module: ' + name)
pattern = r'<script\b[^>]*\bsrc=[\"\'](?:\./)?src/app\.js[\"\'][^>]*>\s*</script>'
match = re.search(pattern, source, re.I)
if not match:
    raise RuntimeError('Application script boundary changed; manual integration is required.')
if 'async' in match.group(0).lower():
    raise RuntimeError('Unexpected async application script.')
if 'src/productivity.js' not in source:
    defer = ' defer' if re.search(r'\bdefer\b', match.group(0)) else ''
    insertion = ''.join('<script src="src/' + name + '"' + defer + '></script>\n' for name in ('productivity.js', 'productivity-ui.js'))
    source = source[:match.start()] + insertion + source[match.start():]
    index.write_text(source)

def build():
    subprocess.run([sys.executable, 'tools/build.py'], cwd=ROOT, check=True)
    text = (ROOT / 'Kestrel-CAD.html').read_text()
    return 'K.Productivity = {' in text and 'Productivity ribbon and command integration' in text.lower().replace('productivity ribbon','Productivity ribbon')

# Existing builds either inline script tags or use an explicit ordered list.
# A marker check ensures the standalone editor really contains both modules.
subprocess.run([sys.executable, 'tools/build.py'], cwd=ROOT, check=True)
standalone = (ROOT / 'Kestrel-CAD.html').read_text()
if 'K.Productivity = {' not in standalone or 'D.installUI = install' not in standalone:
    path = ROOT / 'tools/build.py'
    text = path.read_text()
    tree = ast.parse(text)
    lines = text.splitlines(keepends=True)
    byte_lines = [line.encode('utf-8') for line in lines]
    offsets = [0]
    for line in byte_lines:
        offsets.append(offsets[-1] + len(line))
    replacements = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.List, ast.Tuple)):
            continue
        strings = [e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        for element in node.elts:
            if not isinstance(element, ast.Constant) or not isinstance(element.value, str):
                continue
            value = element.value
            if value.split('/')[-1] != 'app.js':
                continue
            prefix = value[:-len('app.js')]
            if prefix + 'productivity.js' in strings:
                continue
            offset = offsets[element.lineno - 1] + element.col_offset
            insertion = (repr(prefix + 'productivity.js') + ', ' + repr(prefix + 'productivity-ui.js') + ', ').encode('utf-8')
            replacements.append((offset, insertion))
    if not replacements:
        raise RuntimeError('Standalone source list not recognized; refusing an incomplete build.')
    data = text.encode('utf-8')
    for offset, insertion in sorted(replacements, reverse=True):
        data = data[:offset] + insertion + data[offset:]
    path.write_bytes(data)
    subprocess.run([sys.executable, 'tools/build.py'], cwd=ROOT, check=True)
    standalone = (ROOT / 'Kestrel-CAD.html').read_text()
if 'K.Productivity = {' not in standalone or 'D.installUI = install' not in standalone:
    raise RuntimeError('The standalone build omitted productivity code.')
for name in ('productivity.js', 'productivity-ui.js'):
    if source.count('src/' + name) != 1:
        raise RuntimeError('Duplicate or missing runtime module: ' + name)
# Do not leave a self-modifying integration path in the merged application.
for relative in ('tools/integrate_productivity.py', '.github/workflows/productivity-integration.yml'):
    (ROOT / relative).unlink(missing_ok=True)
print('Integrated readable source and standalone editor; temporary integration files removed.')
