"""Read-only interference and clearance queries on transformed OCCT material.

No display triangulation is used for classification, volume or distance. Native
bounding boxes only reject Boolean candidates; every reported distance is solved.
"""
from __future__ import annotations
import math

MAX_PAIRS = 128
MAX_REGION_BODIES = 64


def pairs(count, params):
    """One set: unique unordered pairs. Two sets: A x (B minus A)."""
    if not 2 <= count <= 32:
        raise ValueError('Analysis requires 2–32 native bodies.')
    groups = params.get('groups')
    if groups is None:
        result = [(i, j) for i in range(count) for j in range(i + 1, count)]
    else:
        if not isinstance(groups, dict) or set(groups) != {'first', 'second'}:
            raise ValueError('Analysis groups require first and second index arrays.')
        def group(key):
            values = groups[key]
            if not isinstance(values, list) or not values or any(type(v) is not int or not 0 <= v < count for v in values):
                raise ValueError('Invalid analysis group indices.')
            if len(set(values)) != len(values):
                raise ValueError('Duplicate analysis group index.')
            return values
        first, second = group('first'), group('second')
        second = [v for v in second if v not in first]
        result = [(i, j) for i in first for j in second]
    if not result or len(result) > MAX_PAIRS:
        raise ValueError('Choose 1–128 distinct analysis pairs; reduce or split the sets.')
    return result


def material(shape):
    """Reject mixed/open topology; fuse compound solids to avoid double counts."""
    import cadquery as cq
    from OCP.BRep import BRep_Tool
    from kernel import checked
    def collect(s):
        kind = s.ShapeType()
        if kind == 'Solid':
            if not s.Shells() or any(not BRep_Tool.IsClosed_s(shell.wrapped) for shell in s.Shells()):
                raise ValueError('Analysis requires closed native solids, not open shells.')
            if not math.isfinite(s.Volume()) or s.Volume() <= 0:
                raise ValueError('Analysis requires positive-volume native solids.')
            return [s]
        if kind in ('Compound', 'CompSolid'):
            return [solid for child in s for solid in collect(child)]
        raise ValueError('Analysis requires pure native solids; surfaces, wires and meshes are not accepted.')
    solids = collect(shape)
    if not solids or len(solids) > 64:
        raise ValueError('Each analysis body must contain 1–64 closed solids.')
    # Boolean algorithms work on copies; input BREP bytes and placements are retained.
    result = solids[0].copy()
    if len(solids) > 1:
        result = result.fuse(*[s.copy() for s in solids[1:]])
    checked(result)
    if not result.Solids():
        raise ValueError('Could not normalize the native material union.')
    return result


def analyze(shapes, params, display_tolerance=.1):
    import cadquery as cq
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.TopTools import TopTools_ListOfShape
    from kernel import num, pack, MAX_TOPOLOGY
    plan = pairs(len(shapes), params)
    clearance = num(params.get('clearance', 0), 'minimum clearance', 0, 1e7)
    contact = num(params.get('contactTolerance', 1e-6), 'contact tolerance', 1e-9, 1)
    regions = params.get('regions', False)
    if type(regions) is not bool:
        raise ValueError('Create regions must be a boolean.')
    if sum(len(s.Faces()) + len(s.Edges()) for s in shapes) > MAX_TOPOLOGY:
        raise ValueError('Combined analysis topology exceeds 20,000 faces/edges.')
    # Validate every operand first, including unused group entries.
    sources = [material(s) for s in shapes]
    boxes = []
    for shape in sources:
        box = Bnd_Box()
        BRepBndLib.AddOptimal_s(shape.wrapped, box, False, True)
        boxes.append(box.Get())
    rows, bodies, booleans = [], [], 0
    for i, j in plan:
        a, b = sources[i], sources[j]
        try:
            distance = BRepExtrema_DistShapeShape(a.wrapped, b.wrapped)
            if not distance.IsDone() or distance.NbSolution() < 1:
                raise ValueError('Minimum distance did not converge.')
            gap = float(distance.Value())
            if not math.isfinite(gap) or gap < 0:
                raise ValueError('Nonfinite minimum distance.')
            witnesses = [[list(distance.PointOnShape1(k).Coord()), list(distance.PointOnShape2(k).Coord())]
                         for k in range(1, min(8, distance.NbSolution()) + 1)]
            if not all(math.isfinite(v) for pair in witnesses for p in pair for v in p):
                raise ValueError('Nonfinite distance witness.')
            volume, common_solids = 0., []
            lo, hi = boxes[i], boxes[j]
            separated = any(lo[k+3] < hi[k] or hi[k+3] < lo[k] for k in range(3))
            if not separated:
                args, tools = TopTools_ListOfShape(), TopTools_ListOfShape()
                args.Append(a.wrapped); tools.Append(b.wrapped)
                builder = BRepAlgoAPI_Common()
                builder.SetArguments(args); builder.SetTools(tools)
                builder.SetNonDestructive(True); builder.Build(); booleans += 1
                if not builder.IsDone():
                    raise ValueError('Intersection did not converge.')
                common = cq.Shape.cast(builder.Shape())
                if not common.isNull():
                    if not common.isValid():
                        raise ValueError('Invalid intersection topology.')
                    common_solids = common.Solids()
                    volume = sum(abs(s.Volume()) for s in common_solids)
                if not math.isfinite(volume):
                    raise ValueError('Nonfinite intersection volume.')
            status = ('interference' if volume > 0 else 'contact' if gap <= contact
                      else 'clearance' if gap < clearance else 'separated')
            row = {'first': i, 'second': j, 'status': status, 'distance': gap,
                   'volume': volume, 'witnesses': witnesses,
                   'witnessCount': distance.NbSolution(), 'innerSolution': bool(distance.InnerSolution())}
            if volume > 0 and regions:
                if len(bodies) >= MAX_REGION_BODIES:
                    raise ValueError('At most 64 overlap regions can be retained per analysis.')
                region = pack(cq.Compound.makeCompound(common_solids), display_tolerance)
                bodies.append({'first': i, 'second': j, **region})
            rows.append(row)
        except Exception as exc:
            raise ValueError(f'Analysis pair {i+1}/{j+1} failed: {exc}') from exc
    counts = {name: sum(row['status'] == name for row in rows)
              for name in ('interference', 'contact', 'clearance', 'separated')}
    return {'provider': 'OCCT', 'analysis': 'interference-clearance', 'schema': 1,
            'bodyCount': len(shapes), 'pairCount': len(rows), 'pairs': rows,
            'clearance': clearance, 'contactTolerance': contact, 'counts': counts,
            'booleanChecks': booleans, 'bodies': bodies,
            'warnings': ['Contact includes positive gaps within the stated tolerance.',
                         'Pairwise overlap volumes must not be summed as a unique assembly overlap.',
                         'Distances are minimum material distances, not penetration depths.']}
