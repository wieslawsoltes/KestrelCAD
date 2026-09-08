#!/usr/bin/env python3
"""Bundle source files into one dependency-free HTML application. No npm needed."""
from pathlib import Path
import argparse
import json
import re

ROOT = Path(__file__).resolve().parent.parent

def build(output: Path) -> None:
    html = (ROOT / 'index.html').read_text()
    css = (ROOT / 'src/style.css').read_text()
    html = re.sub(r'<link rel="stylesheet" href="src/style.css"\s*/?>', lambda _: '<style>\n'+css+'\n</style>', html)
    worker = '\n'.join((ROOT / 'src' / name).read_text() for name in ('math.js','geometry.js','model.js','exchange.js','production.js','kernel.js', 'constraints.js','dynamic-blocks.js','fonts.js','unicode-bidi.js','mtext.js','source-document.js','productivity.js'))
    worker += '\n' + re.sub(r"importScripts\([^;]+;", '', (ROOT / 'src/io-worker.js').read_text())
    script_data = json.dumps(worker).replace('</', '<\\/')
    html = html.replace('</head>', '<script>window.KESTREL_WORKER_SOURCE='+script_data+';</script>\n</head>')
    def inline(match):
        source = (ROOT / 'src' / match.group(1)).read_text()
        source = re.sub(r'</script', r'<\\/script', source, flags=re.I)
        return '<script>\n'+source+'\n</script>'
    html = re.sub(r'<script src="src/([\w-]+\.js)"></script>', inline, html)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding='utf-8')
    print(f'Built {output} ({output.stat().st_size:,} bytes)')

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, default=ROOT / 'Kestrel-CAD.html')
    build(p.parse_args().out.resolve())
