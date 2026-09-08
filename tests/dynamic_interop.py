#!/usr/bin/env python3
"""Independent ezdxf reader/auditor checks the actual evaluated block export."""
from pathlib import Path
import json
import ezdxf
ROOT = Path(__file__).resolve().parent.parent
results = []
drawing = ezdxf.readfile(ROOT / 'tests/fixtures/dynamic-variants.dxf')
inserts = list(drawing.modelspace().query('INSERT'))
def check(name, fn):
    try:
        fn()
        results.append({'name': name, 'status': 'passed'})
        print('PASS', name)
    except Exception as error:
        results.append({'name': name, 'status': 'failed', 'error': str(error)})
        print('FAIL', name, error)
def audit():
    report = drawing.audit()
    assert not report.errors and not report.fixes, [(e.code, e.message) for e in [*report.errors, *report.fixes]]
def variants():
    assert len(inserts) == 2
    assert inserts[0].dxf.name != inserts[1].dxf.name
    assert all(i.dxf.name in drawing.blocks for i in inserts)
def geometry():
    for insert, expected in zip(inserts, (100, 700)):
        members = list(insert.virtual_entities())
        line = next(e for e in members if e.dxftype() == 'LINE')
        assert line.dxf.start.isclose((expected, 0, 0))
        assert line.dxf.end.isclose((expected + 100, 0, 0))
        circle = next(e for e in members if e.dxftype() == 'CIRCLE')
        assert circle.dxf.radius == 5
        assert len(members) == 2
def appearance():
    first = inserts[0]
    assert first.dxf.true_color == 0xff0000
    line = next(e for e in drawing.blocks[first.dxf.name] if e.dxftype() == 'LINE')
    assert line.dxf.color == 0  # ByBlock, not a NaN true-color record.
    assert not line.dxf.hasattr('true_color')
check('independent evaluated-block DXF audit has zero errors and repairs', audit)
check('independent reader sees separate standard evaluated variant definitions', variants)
check('independent virtual geometry preserves both parameter-specific positions', geometry)
check('standard ByBlock color inherits its true-color reference', appearance)
failed = sum(r['status'] == 'failed' for r in results)
(ROOT / 'tests/results/dynamic-interop-results.json').write_text(json.dumps({'passed':len(results)-failed,'failed':failed,'tests':results},indent=2)+'\n')
raise SystemExit(bool(failed))
