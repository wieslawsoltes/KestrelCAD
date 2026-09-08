#!/usr/bin/env python3
"""Stateless, structured OpenCascade B-rep worker. No eval, shell, or client paths.

Coordinates and distances are in drawing units. STEP/IGES translation uses mm.
The server invokes this module in a time-limited process for each request.
"""
from __future__ import annotations
import base64
import io
import json
import math
from pathlib import Path
import sys
import tempfile

MAX_BREP = 16 * 1024 * 1024
MAX_TOPOLOGY = 20000
MAX_MESH = 500000
OPERATIONS = ('box', 'cylinder', 'cone', 'sphere', 'torus', 'extrude', 'revolve',
              'loft', 'sweep', 'union', 'subtract', 'intersect', 'fillet', 'chamfer',
              'shell', 'section', 'transform', 'import', 'export', 'inspect',
              'slice', 'separate', 'plane-surface', 'extract-faces', 'thicken', 'massprops',
              'acis-import', 'acis-export', 'acis-dxf', 'interference', 'extract-curves')


def num(x, label='number', lo=-1e8, hi=1e8):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or not lo <= x <= hi:
        raise ValueError(f'Invalid {label}; expected a finite value in [{lo}, {hi}].')
    return float(x)


def positive(x, label='size'):
    return num(x, label, 1e-6, 1e7)


def vector(x, label='vector'):
    if not isinstance(x, list) or len(x) != 3:
        raise ValueError(f'{label} must contain three coordinates.')
    return tuple(num(v, label) for v in x)


def decode(text):
    if not isinstance(text, str) or len(text) > MAX_BREP * 1.34:
        raise ValueError('Native payload exceeds 16 MiB.')
    try:
        data = base64.b64decode(text, validate=True)
    except Exception as exc:
        raise ValueError('Invalid base64 native data.') from exc
    if not data or len(data) > MAX_BREP:
        raise ValueError('Native payload is empty or exceeds 16 MiB.')
    return data


def affine(shape, values):
    """Apply a column-major affine matrix to authoritative B-rep geometry."""
    from OCP.gp import gp_GTrsf, gp_Mat, gp_XYZ, gp_Trsf
    from OCP.BRepBuilderAPI import BRepBuilderAPI_GTransform, BRepBuilderAPI_Transform
    import cadquery as cq
    if values is None:
        return shape
    if not isinstance(values, list) or len(values) != 16:
        raise ValueError('Transform requires sixteen coefficients.')
    m = [num(v, 'matrix coefficient') for v in values]
    if any(abs(m[i]) > 1e-10 for i in (3, 7, 11)) or abs(m[15]-1) > 1e-10:
        raise ValueError('Only affine transforms are supported.')
    mat = gp_Mat(m[0], m[4], m[8], m[1], m[5], m[9], m[2], m[6], m[10])
    if abs(mat.Determinant()) < 1e-18:
        raise ValueError('Transform is singular.')
    # GTransform converts even an identity-transformed circle/plane to B-splines.
    # That destroys canonical topology and can make Face.thicken() fail after a
    # normal browser round trip (which always supplies a transform matrix).
    # Use gp_Trsf for similarities; retain GTransform for actual skew/stretch.
    columns = [m[0:3], m[4:7], m[8:11]]
    gram = [[sum(a*b for a, b in zip(u, v)) for v in columns] for u in columns]
    scale2 = sum(gram[i][i] for i in range(3)) / 3
    similarity = all(abs(gram[i][j] - (scale2 if i == j else 0)) <= scale2*1e-12
                     for i in range(3) for j in range(3))
    if similarity:
        transform = gp_Trsf()
        transform.SetValues(m[0], m[4], m[8], m[12], m[1], m[5], m[9], m[13],
                            m[2], m[6], m[10], m[14])
        return cq.Shape.cast(BRepBuilderAPI_Transform(shape.wrapped, transform, True).Shape())
    transform = gp_GTrsf(mat, gp_XYZ(m[12], m[13], m[14]))
    return cq.Shape.cast(BRepBuilderAPI_GTransform(shape.wrapped, transform, True).Shape())


def wire(profile, closed=True):
    """Analytic circle/ellipse, straight and bulged polyline, or exact arc wire."""
    import cadquery as cq
    if not isinstance(profile, dict):
        raise ValueError('A structured profile is required.')
    kind = profile.get('type')
    if kind == 'spline':
        from native_curves import spline_wire
        return spline_wire(profile, closed)
    if kind in ('circle', 'ellipse'):
        center = vector(profile.get('center', [0, 0, 0]), 'center')
        normal = vector(profile.get('normal', [0, 0, 1]), 'normal')
        xdir = vector(profile.get('xdir', [1, 0, 0]), 'x axis')
        if sum(v*v for v in normal) < 1e-15:
            raise ValueError('Zero profile normal.')
        if kind == 'circle':
            edge = cq.Edge.makeCircle(positive(profile.get('radius'), 'radius'), center, normal)
        else:
            edge = cq.Edge.makeEllipse(positive(profile.get('rx'), 'x radius'), positive(profile.get('ry'), 'y radius'), center, normal, xdir)
        return cq.Wire.assembleEdges([edge])
    if kind != 'polyline':
        raise ValueError('Supported profiles: circle, ellipse, polyline with optional bulges.')
    points = profile.get('points')
    if not isinstance(points, list) or not 2 <= len(points) <= 2000:
        raise ValueError('Profile requires 2–2000 points.')
    pts = [cq.Vector(*vector(p, 'profile point')) for p in points]
    if (pts[0]-pts[-1]).Length < 1e-8:
        pts.pop()
    if len(pts) < (3 if closed else 2):
        raise ValueError('Too few profile vertices.')
    bulges = profile.get('bulges', [])
    if not isinstance(bulges, list) or len(bulges) > len(points):
        raise ValueError('Invalid bulges.')
    normal = cq.Vector(*vector(profile.get('normal', [0, 0, 1]))).normalized()
    edges = []
    count = len(pts) if closed else len(pts)-1
    for i in range(count):
        a, b = pts[i], pts[(i+1) % len(pts)]
        if (b-a).Length < 1e-8:
            raise ValueError('Profile contains a zero-length edge.')
        bulge = num(bulges[i], 'bulge', -1e5, 1e5) if i < len(bulges) else 0
        if abs(bulge) < 1e-12:
            edges.append(cq.Edge.makeLine(a, b))
        else:
            mid = (a+b)*0.5 - normal.cross(b-a)*(bulge*0.5)
            edges.append(cq.Edge.makeThreePointArc(a, mid, b))
    w = cq.Wire.assembleEdges(edges)
    if not w.isValid() or (closed and not w.IsClosed()):
        raise ValueError('Profile does not form a valid closed wire.')
    return w


def selection(shape, indices, kind):
    items = shape.Edges() if kind == 'edges' else shape.Faces()
    if not isinstance(indices, list) or not indices or len(indices) > MAX_TOPOLOGY:
        raise ValueError(f'Select one or more {kind} by their current topology index.')
    if any(isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < len(items) for i in indices):
        raise ValueError(f'Invalid {kind} index. Inspect the current solid first.')
    if len(set(indices)) != len(indices):
        raise ValueError('Duplicate topology index.')
    return [items[i] for i in indices]


def read_shape(item):
    import cadquery as cq
    if not isinstance(item, dict) or item.get('provider') != 'OCCT':
        raise ValueError('Select an OCCT B-rep body, not an approximate mesh.')
    data = decode(item.get('brep'))
    if b'CASCADE Topology' not in data[:512]:
        raise ValueError('Not an OpenCascade B-rep stream.')
    return affine(cq.Shape.importBrep(io.BytesIO(data)), item.get('transform'))


def checked(shape):
    if shape.isNull() or not shape.isValid():
        raise ValueError('The kernel did not produce valid topology; no drawing change was committed.')
    if len(shape.Faces()) > MAX_TOPOLOGY or len(shape.Edges()) > MAX_TOPOLOGY:
        raise ValueError('Result exceeds the 20,000 face/edge safety limit.')
    return shape


def pack(shape, tolerance):
    import cadquery as cq
    import OCP
    from OCP.BRepTools import BRepTools
    checked(shape)
    # Persist analytic curves and surfaces before generating a display triangulation.
    BRepTools.Clean_s(shape.wrapped)
    stream = io.BytesIO()
    if not shape.exportBrep(stream):
        raise ValueError('B-rep serialization failed.')
    data = stream.getvalue()
    if len(data) > MAX_BREP:
        raise ValueError('Native result exceeds 16 MiB.')
    verts, triangles = shape.tessellate(tolerance, 0.15)
    if len(verts) > MAX_MESH or len(triangles) > MAX_MESH:
        raise ValueError('Display mesh exceeds 500,000 vertices/triangles; increase display tolerance.')
    edge_rows, edge_lines = [], []
    for index, e in enumerate(shape.Edges()):
        edge_rows.append({'index': index, 'type': e.geomType(), 'length': e.Length(), 'center': e.Center().toTuple()})
        count = 2 if e.geomType() == 'LINE' else min(256, max(16, int(e.Length()/max(tolerance, 0.01))))
        samples = [p.toTuple() for p in e.sample(count)[0]]
        edge_lines.append(samples)
    face_rows = [{'index': i, 'type': f.geomType(), 'area': f.Area(), 'center': f.Center().toTuple()} for i, f in enumerate(shape.Faces())]
    solids = shape.Solids()
    return {'provider': 'OCCT', 'version': OCP.__version__, 'cadquery': cq.__version__,
            'brep': base64.b64encode(data).decode('ascii'),
            'mesh': {'type': 'MESH', 'vertices': [v.toTuple() for v in verts], 'faces': triangles},
            'edges': edge_rows, 'faces': face_rows, 'edgePolylines': edge_lines,
            'volume': sum(abs(s.Volume()) for s in solids), 'area': shape.Area(),
            'solidCount': len(solids), 'valid': True, 'tolerance': tolerance}


def mass_properties(shape, density=1):
    """Integrate the transformed B-rep, not its viewport triangulation.

    Mass assumes uniform density. Inertia is about the centroid in world axes.
    Overlapping solids are additive; callers must union them to remove overlap.
    """
    from OCP.GProp import GProp_GProps
    from OCP.BRepGProp import BRepGProp
    checked(shape)
    if not shape.Solids():
        raise ValueError('Volumetric mass properties require at least one closed solid.')
    density = positive(density, 'uniform density')
    props = GProp_GProps()
    for solid in shape.Solids():
        if not solid.Shells() or any(not shell.Closed() for shell in solid.Shells()):
            raise ValueError('Mass properties require closed solids.')
        component = GProp_GProps()
        BRepGProp.VolumeProperties_s(solid.wrapped, component, True, False, False)
        if component.Mass() <= 0:
            raise ValueError('A body has nonpositive oriented volume.')
        props.Add(component, density)
    tensor, principal = props.MatrixOfInertia(), props.PrincipalProperties()
    bounds = shape.BoundingBox()
    return {'density': density, 'volume': props.Mass()/density, 'mass': props.Mass(),
            'area': shape.Area(), 'centroid': list(props.CentreOfMass().Coord()),
            'inertia': [[tensor.Value(i,j) for j in (1,2,3)] for i in (1,2,3)],
            'principalMoments': list(principal.Moments()),
            'principalAxes': [list(a.Coord()) for a in (principal.FirstAxisOfInertia(),
                principal.SecondAxisOfInertia(), principal.ThirdAxisOfInertia())],
            'bounds': {'min': [bounds.xmin,bounds.ymin,bounds.zmin],
                       'max': [bounds.xmax,bounds.ymax,bounds.zmax]},
            'solidCount': len(shape.Solids()), 'inertiaReference': 'centroid, world axes',
            'overlapPolicy': 'additive; union overlapping bodies first'}


def pack_many(items, tolerance):
    """All results are validated before a single atomic client transaction."""
    if not items or len(items) > 64:
        raise ValueError('Multi-body operation requires 1–64 results.')
    bodies = [dict(pack(shape, tolerance), sourceIndex=index, **extra)
              for index, shape, extra in items]
    if sum(len(b['mesh']['vertices']) for b in bodies) > MAX_MESH:
        raise ValueError('Combined result exceeds the display vertex limit.')
    result = {'bodies': bodies}
    if len(json.dumps(result)) > 48*1024*1024:
        raise ValueError('Combined native result exceeds the 48 MiB response limit.')
    return result


def slice_body(source, origin, normal, keep):
    """Intersect with analytic infinite half-spaces, with no bounding-box cutters."""
    import cadquery as cq
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeHalfSpace
    from OCP.gp import gp_Pln, gp_Pnt, gp_Dir
    o, n = vector(origin, 'plane origin'), vector(normal, 'plane normal')
    norm = math.sqrt(sum(v*v for v in n))
    if norm < 1e-12:
        raise ValueError('Slicing plane needs a nonzero normal.')
    if keep not in ('positive', 'negative', 'both'):
        raise ValueError('Choose the positive side, negative side, or both sides.')
    n = tuple(v/norm for v in n)
    face = cq.Face(BRepBuilderAPI_MakeFace(gp_Pln(gp_Pnt(*o), gp_Dir(*n))).Face())
    if not source.Faces():
        raise ValueError('Slice requires a native solid or surface, not section wires.')
    out = []
    for side, sign in [('positive',1), ('negative',-1)]:
        point = gp_Pnt(*(o[i] + sign*n[i] for i in range(3)))
        halfspace = cq.Solid(BRepPrimAPI_MakeHalfSpace(face.wrapped, point).Solid())
        part = source.intersect(halfspace).clean()
        pieces = part.Solids() if source.Solids() else part.Faces()
        if pieces:
            checked(part)
            out.append((side, part))
    if len(out) != 2:
        raise ValueError('The plane must cross the body interior; tangency alone is not a slice.')
    return [(side, part) for side, part in out if keep == 'both' or keep == side]


def execute(request):
    import cadquery as cq
    if not isinstance(request, dict) or request.get('op') not in OPERATIONS:
        raise ValueError('Unknown B-rep operation.')
    op, p = request['op'], request.get('params', {})
    if not isinstance(p, dict):
        raise ValueError('Operation parameters must be an object.')
    raw_inputs = request.get('inputs', [])
    if not isinstance(raw_inputs, list) or len(raw_inputs) > 32:
        raise ValueError('At most 32 input bodies are allowed.')
    shapes = [checked(read_shape(s)) for s in raw_inputs]
    tolerance = num(request.get('tolerance', .1), 'display tolerance', .001, 1000)
    def one():
        if len(shapes) != 1:
            raise ValueError('Select exactly one native body.')
        return shapes[0]
    def profile():
        return wire(p.get('profile'))
    if op == 'acis-import':
        from acis_exchange import import_geometry
        import hashlib
        if shapes:
            raise ValueError('ACIS import accepts a file, not selected bodies.')
        data = decode(p.get('data'))
        restored, report = import_geometry(data, p.get('format'), p.get('unitMM', 1), p.get('sourceUnitMM'))
        report['sha256'] = hashlib.sha256(data).hexdigest()
        result = pack_many([(0, checked(s), {}) for s in restored], tolerance)
        result['exchange'] = report
        return result
    if op in ('acis-export', 'acis-dxf'):
        from acis_exchange import export_geometry, export_dxf
        if not shapes:
            raise ValueError('Select at least one native body for ACIS exchange.')
        fmt = 'dxf' if op == 'acis-dxf' else p.get('format', 'sat')
        data = export_dxf(shapes, p.get('version', 'R2018'), p.get('units', 'mm')) if op == 'acis-dxf' else export_geometry(shapes, fmt, p.get('unitMM', 1))
        return {'format': fmt, 'data': base64.b64encode(data).decode('ascii'), 'bytes': len(data),
                'bodies': len(shapes), 'mode': 'planar-straight-brep', 'geometryOnly': True,
                'warnings': ['Only selected native body geometry is exported; drawing annotations, attributes and application history are not included.']}
    if op == 'extract-curves':
        from native_curves import extract
        return extract(shapes, p)
    if op == 'interference':
        from native_analysis import analyze
        return analyze(shapes, p, tolerance)
    if op == 'massprops':
        if not shapes or any(not s.Solids() for s in shapes):
            raise ValueError('Select native closed solids for mass properties.')
        shape = cq.Compound.makeCompound(shapes)
        return mass_properties(shape, p.get('density', 1))
    if op == 'slice':
        if not shapes:
            raise ValueError('Select native solids or surfaces to slice.')
        origin, normal, keep = p.get('origin', [0,0,0]), p.get('normal', [0,0,1]), p.get('keep', 'both')
        return pack_many([(i, part, {'side':side}) for i, shape in enumerate(shapes)
                          for side, part in slice_body(shape, origin, normal, keep)], tolerance)
    if op == 'separate':
        source = one()
        solids = source.Solids()
        if len(solids) < 2:
            raise ValueError('Separate requires a composite body with multiple solids.')
        return pack_many([(0, solid, {}) for solid in solids], tolerance)
    if op == 'extract-faces':
        source = one()
        return pack_many([(0, f, {}) for f in selection(source, p.get('faces'), 'faces')], tolerance)
    if op == 'plane-surface':
        holes = p.get('holes', [])
        if not isinstance(holes, list) or len(holes) > 64:
            raise ValueError('At most 64 inner profiles are allowed.')
        shape = cq.Face.makeFromWires(profile(), [wire(h) for h in holes])
    elif op == 'thicken':
        source = one()
        if source.Solids() or len(source.Faces()) != 1:
            raise ValueError('Thicken requires one native face; extract a face from a body first.')
        thickness = num(p.get('thickness'), 'thickness', -1e7, 1e7)
        if abs(thickness) < 1e-6:
            raise ValueError('Thickness must be nonzero.')
        shape = source.Faces()[0].thicken(thickness)
        if not shape.Solids():
            raise ValueError('The offset did not create a closed solid.')
    elif op == 'box':
        shape = cq.Solid.makeBox(positive(p.get('width')), positive(p.get('depth')), positive(p.get('height')))
    elif op == 'cylinder':
        shape = cq.Solid.makeCylinder(positive(p.get('radius')), positive(p.get('height')))
    elif op == 'cone':
        r1 = num(p.get('radius1'), 'first radius', 0, 1e7)
        r2 = num(p.get('radius2', 0), 'second radius', 0, 1e7)
        if max(r1, r2) < 1e-6 or abs(r1-r2) < 1e-8:
            raise ValueError('Cone radii must differ and not both be zero; use a cylinder for equal radii.')
        shape = cq.Solid.makeCone(r1, r2, positive(p.get('height')))
    elif op == 'sphere':
        shape = cq.Solid.makeSphere(positive(p.get('radius')), angleDegrees1=-90, angleDegrees2=90)
    elif op == 'torus':
        major, minor = positive(p.get('major')), positive(p.get('minor'))
        if major <= minor:
            raise ValueError('Torus major radius must exceed minor radius.')
        shape = cq.Solid.makeTorus(major, minor)
    elif op in ('extrude', 'revolve'):
        outer = profile()
        holes = p.get('holes', [])
        if not isinstance(holes, list) or len(holes) > 64:
            raise ValueError('At most 64 inner profiles are allowed.')
        inner = [wire(h) for h in holes]
        if op == 'extrude':
            delta = vector(p.get('vector', [0, 0, 10]))
            if sum(v*v for v in delta) < 1e-12:
                raise ValueError('Extrusion vector must be nonzero.')
            shape = cq.Solid.extrudeLinear(outer, inner, delta, num(p.get('taper', 0), 'taper', -80, 80))
        else:
            shape = cq.Solid.revolve(outer, inner, num(p.get('angle', 360), 'angle', .01, 360), vector(p.get('axisStart', [0,0,0])), vector(p.get('axisEnd', [0,0,1])))
    elif op == 'loft':
        profiles = p.get('profiles')
        if not isinstance(profiles, list) or not 2 <= len(profiles) <= 32:
            raise ValueError('Loft requires 2–32 closed profiles.')
        shape = cq.Solid.makeLoft([wire(v) for v in profiles], bool(p.get('ruled', False)))
    elif op == 'sweep':
        shape = cq.Solid.sweep(profile(), [], wire(p.get('path'), closed=False), True, bool(p.get('frenet', False)))
    elif op in ('union', 'subtract', 'intersect'):
        if len(shapes) < 2:
            raise ValueError('Select at least two native bodies in operand order.')
        shape = shapes[0]
        for other in shapes[1:]:
            shape = getattr(shape, {'union':'fuse', 'subtract':'cut', 'intersect':'intersect'}[op])(other)
        shape = shape.clean()
        if not shape.Solids():
            raise ValueError('Operation has no solid result.')
    elif op in ('fillet', 'chamfer', 'shell'):
        source = one()
        if len(source.Solids()) != 1:
            raise ValueError('This operation requires one connected solid.')
        source = source.Solids()[0]
        if op == 'fillet':
            shape = source.fillet(positive(p.get('radius')), selection(source, p.get('edges'), 'edges'))
        elif op == 'chamfer':
            shape = source.chamfer(positive(p.get('distance')), positive(p['distance2']) if p.get('distance2') is not None else None, selection(source, p.get('edges'), 'edges'))
        else:
            thickness = num(p.get('thickness'), 'thickness', -1e7, 1e7)
            if abs(thickness) < 1e-6:
                raise ValueError('Shell thickness must be nonzero.')
            # Use the underlying OCCT thick-solid algorithm, not triangle offsets.
            from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeThickSolid
            from OCP.TopTools import TopTools_ListOfShape
            faces = TopTools_ListOfShape()
            for f in selection(source, p.get('faces'), 'faces'):
                faces.Append(f.wrapped)
            builder = BRepOffsetAPI_MakeThickSolid()
            builder.MakeThickSolidByJoin(source.wrapped, faces, thickness, 1e-5)
            if not builder.IsDone():
                raise ValueError('Shell construction failed.')
            shape = cq.Shape.cast(builder.Shape())
    elif op == 'section':
        from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
        from OCP.gp import gp_Pln, gp_Pnt, gp_Dir
        origin = vector(p.get('origin', [0,0,0]))
        normal = vector(p.get('normal', [0,0,1]))
        builder = BRepAlgoAPI_Section(one().wrapped, gp_Pln(gp_Pnt(*origin), gp_Dir(*normal)), False)
        builder.Approximation(True)
        builder.Build()
        if not builder.IsDone():
            raise ValueError('Section construction failed.')
        shape = cq.Shape.cast(builder.Shape())
        if not shape.Edges():
            raise ValueError('The plane does not intersect the body.')
    elif op in ('transform', 'inspect'):
        shape = one()
    elif op == 'import':
        fmt = p.get('format')
        if fmt not in ('step', 'iges', 'brep'):
            raise ValueError('Import formats: STEP, IGES, OCCT BREP. Use the dedicated ACIS exchange commands for planar SAT/SAB geometry.')
        data = decode(p.get('data'))
        with tempfile.TemporaryDirectory(prefix='kestrel-kernel-') as tmp:
            path = Path(tmp)/('input.'+fmt)
            path.write_bytes(data)
            if fmt == 'step':
                roots = cq.importers.importStep(str(path)).vals()
                if not roots:
                    raise ValueError('STEP contains no transferred shapes.')
                shape = roots[0] if len(roots) == 1 else cq.Compound.makeCompound(roots)
            elif fmt == 'brep':
                shape = cq.Shape.importBrep(str(path))
            else:
                from OCP.IGESControl import IGESControl_Reader
                from OCP.IFSelect import IFSelect_RetDone
                reader = IGESControl_Reader()
                if reader.ReadFile(str(path)) != IFSelect_RetDone:
                    raise ValueError('Invalid IGES file.')
                reader.TransferRoots()
                shape = cq.Shape.cast(reader.OneShape())
        factor = positive(p.get('scale', 1), 'unit scale')
        if factor != 1:
            shape = shape.scale(factor)
    elif op == 'export':
        shape = one()
        factor = positive(p.get('scale', 1), 'unit scale')
        if factor != 1:
            shape = shape.scale(factor)
        fmt = p.get('format', 'step')
        if fmt not in ('step', 'iges', 'brep', 'stl'):
            raise ValueError('Export formats: STEP, IGES, OCCT BREP, STL.')
        with tempfile.TemporaryDirectory(prefix='kestrel-kernel-') as tmp:
            path = Path(tmp)/('output.'+fmt)
            if fmt == 'brep':
                shape.exportBrep(str(path))
            elif fmt == 'iges':
                from OCP.IGESControl import IGESControl_Writer
                writer = IGESControl_Writer('MM', 0)
                writer.AddShape(shape.wrapped)
                if not writer.Write(str(path)):
                    raise ValueError('IGES writing failed.')
            else:
                cq.exporters.export(shape, str(path), exportType=fmt.upper(), tolerance=tolerance)
            data = path.read_bytes()
        if len(data) > MAX_BREP:
            raise ValueError('Export exceeds 16 MiB.')
        return {'format': fmt, 'data': base64.b64encode(data).decode('ascii'), 'bytes': len(data), 'unit': 'mm' if fmt in ('step','iges') else 'drawing'}
    else:
        raise ValueError('Unsupported operation.')
    shape = affine(shape, p.get('matrix'))
    return pack(shape, tolerance)


def main():
    # Native libraries can write diagnostics to stdout; keep JSON protocol separate.
    import os
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (6*1024**3, 6*1024**3))
        resource.setrlimit(resource.RLIMIT_CPU, (55, 55))
        resource.setrlimit(resource.RLIMIT_FSIZE, (64*1024**2, 64*1024**2))
    except (ImportError, ValueError, OSError):
        pass  # Windows still has server wall-clock and input/output limits.
    original = os.dup(1)
    os.dup2(2, 1)
    try:
        raw = sys.stdin.buffer.read(64*1024*1024+1)
        if len(raw) > 64*1024*1024:
            raise ValueError('Request exceeds 64 MiB.')
        response = {'result': execute(json.loads(raw))}
    except ImportError:
        response = {'error': 'Optional OpenCascade engine is not installed. Install requirements-kernel.txt locally.'}
    except Exception as exc:
        response = {'error': (str(exc) or type(exc).__name__)[:2000]}
    with os.fdopen(original, 'w', encoding='utf-8') as out:
        json.dump(response, out, allow_nan=False)
        out.write('\n')


if __name__ == '__main__':
    main()
