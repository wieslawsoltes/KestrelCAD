"""Geometry-only SAT/SAB translation of planar B-reps with straight boundaries.

No tessellation is used to manufacture export geometry. Unsupported curves,
non-manifold shells and broken links reject before a drawing can be changed.
The low-level ezdxf adapter is intentionally pinned and isolated in this file.
"""
from __future__ import annotations

from collections import Counter
import io
import math

MAX_RECORDS = 160000
MAX_FACES = 20000
MAX_BODIES = 32
MAX_BYTES = 16 * 1024 * 1024
TOL = 1e-7


def modules():
    import ezdxf
    if ezdxf.__version__ != '1.4.4':
        raise ValueError('SAT/SAB adapter requires ezdxf 1.4.4; install requirements-kernel.txt.')
    from ezdxf.acis import api, entities, sat, sab, hdr
    return api, entities, sat, sab, hdr


def scalar(value, label, minimum=1e-9, maximum=1e9):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f'Invalid ACIS {label}.')
    return float(value)


def xyz(value):
    values = tuple(value)
    if len(values) != 3 or any(not math.isfinite(v) or abs(v) > 1e8 for v in values):
        raise ValueError('Invalid or oversized ACIS coordinate.')
    return values


def chain(first, link, kind, circular=False):
    """Bounded traversal; third-party convenience iterators can loop forever."""
    result, seen, current = [], set(), first
    while not current.is_none:
        if id(current) in seen:
            if circular and current is first:
                return result
            raise ValueError(f'Broken ACIS {kind} cycle.')
        if current.type != kind or len(result) >= MAX_RECORDS:
            raise ValueError(f'Unsupported or oversized ACIS {kind} chain.')
        seen.add(id(current)); result.append(current)
        current = getattr(current, link)
    if circular:
        raise ValueError('Open ACIS face boundary; a closed coedge loop is required.')
    return result


def absent(value, label):
    if not value.is_none:
        raise ValueError(f'Unsupported ACIS {label}; geometry was not approximated.')


def parse(data, fmt):
    api, a, sat, sab, _ = modules()
    if not isinstance(data, bytes) or not data or len(data) > MAX_BYTES:
        raise ValueError('ACIS input must contain 1 byte to 16 MiB.')
    if fmt not in ('sat', 'sab'):
        raise ValueError('ACIS input format must be SAT or SAB.')
    try:
        encoded = data.decode('utf-8-sig') if fmt == 'sat' else data
        builder = sat.parse_sat(encoded) if fmt == 'sat' else sab.parse_sab(encoded)
    except Exception as exc:
        raise ValueError('Invalid ACIS ' + fmt.upper() + ' stream: ' + str(exc)[:300]) from exc
    expected = 700 if fmt == 'sat' else 21800
    if builder.header.version != expected:
        raise ValueError(f'This adapter accepts {fmt.upper()} version {expected}; found {builder.header.version}.')
    if not 1 <= len(builder.bodies) <= MAX_BODIES or len(builder.entities) > MAX_RECORDS:
        raise ValueError('ACIS requires 1–32 bodies and at most 160,000 records.')
    counts = Counter(record.name for record in builder.entities)
    report = {'format': fmt, 'version': builder.header.version,
              'unitMM': builder.header.units_in_mm, 'bodies': len(builder.bodies),
              'records': len(builder.entities), 'recordTypes': dict(sorted(counts.items())),
              'mode': 'planar-straight-brep', 'geometryOnly': True,
              'warnings': ['Geometry translation does not preserve ACIS application attributes or history.']}
    try:
        # ezdxf 1.4.4's Shell.restore_common expects the literal type
        # "next_shell" for a link to a "shell". Override only this adapter's
        # loader, not the dependency's global entity registry.
        class LinkedShell(a.Shell):
            def restore_common(self, loader, factory):
                a.SupportsPattern.restore_common(self, loader, factory)
                for name, kind in (("next_shell", "shell"), ("subshell", "subshell"),
                                   ("face", "face"), ("wire", "wire"), ("lump", "lump")):
                    setattr(self, name, a.restore_entity(kind, loader, factory))

        class Loader(a.FileLoader):
            def entity_factory(self, raw):
                if raw.name == 'shell' and id(raw) not in self.entities:
                    self.entities[id(raw)] = LinkedShell()
                return super().entity_factory(raw)

            def make_data_loader(self, values):
                cls = sat.SatDataLoader if fmt == 'sat' else sab.SabDataLoader
                return cls(values, self.version)

        loader = Loader(builder.header.version); loader.records = builder.entities
        loader.load_entities(); bodies = loader.bodies()
    except Exception as exc:
        raise ValueError('ACIS topology could not be decoded: ' + str(exc)[:300]) from exc
    if len(bodies) != len(builder.bodies):
        raise ValueError('Not all ACIS bodies were decoded.')
    return bodies, report


def import_geometry(data, fmt, target_unit_mm=1.0, source_unit_mm=None):
    """Return real OCCT shapes, including face holes and multiple void shells."""
    import cadquery as cq
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing, BRepBuilderAPI_MakeSolid
    from OCP.ShapeFix import ShapeFix_Solid
    from OCP.TopAbs import TopAbs_SHELL, TopAbs_FACE
    from OCP.TopoDS import TopoDS
    from ezdxf.math import Vec3

    bodies, report = parse(data, fmt)
    target_unit_mm = scalar(target_unit_mm, 'target unit')
    unit = report['unitMM'] if source_unit_mm is None else scalar(source_unit_mm, 'source unit override')
    if not isinstance(unit, (int, float)) or not math.isfinite(unit) or unit <= 0:
        raise ValueError('Unitless ACIS file: explicitly choose source units before importing.')
    factor = scalar(unit / target_unit_mm, 'unit conversion')
    report.update(appliedUnitMM=unit, targetUnitMM=target_unit_mm, scale=factor)
    output, face_count = [], 0
    for body in bodies:
        absent(body.wire, 'wire body'); absent(body.pattern, 'body pattern')
        lumps = chain(body.lump, 'next_lump', 'lump')
        if not lumps:
            raise ValueError('An ACIS body contains no supported lumps.')
        transform = None if body.transform.is_none else body.transform.matrix
        if transform is not None:
            coefficients = list(transform)
            if any(not math.isfinite(v) for v in coefficients) or abs(transform.determinant()) < 1e-18:
                raise ValueError('Invalid ACIS body transform.')
        pieces = []
        for lump in lumps:
            if lump.body is not body:
                raise ValueError('Broken ACIS lump ownership.')
            shells = chain(lump.shell, 'next_shell', 'shell')
            if not shells:
                raise ValueError('ACIS lump contains no shells.')
            native_shells, all_double = [], []
            for shell in shells:
                absent(shell.wire, 'shell wires'); absent(shell.subshell, 'subshells')
                if shell.lump is not lump:
                    raise ValueError('Broken ACIS shell ownership.')
                faces = chain(shell.face, 'next_face', 'face')
                if not faces:
                    raise ValueError('ACIS shell contains no faces.')
                face_count += len(faces)
                if face_count > MAX_FACES:
                    raise ValueError('ACIS input exceeds 20,000 faces.')
                native_faces, uses = [], {}
                for face in faces:
                    if face.shell is not shell or face.surface.type != 'plane-surface':
                        raise ValueError('Only planar ACIS faces are supported; curved/unknown surfaces are not flattened.')
                    absent(face.subshell, 'face subshells')
                    loops = chain(face.loop, 'next_loop', 'loop')
                    if not loops:
                        raise ValueError('Unbounded ACIS plane has no closed boundary.')
                    normal = Vec3(xyz(face.surface.normal))
                    if normal.magnitude < 1e-12:
                        raise ValueError('Invalid ACIS plane normal.')
                    normal = normal.normalize() * (-1 if face.sense else 1)
                    polygons = []
                    for loop in loops:
                        if loop.face is not face:
                            raise ValueError('Broken ACIS loop ownership.')
                        coedges = chain(loop.coedge, 'next_coedge', 'coedge', circular=True)
                        if len(coedges) < 3:
                            raise ValueError('A straight-sided face requires at least three edges.')
                        points, ends = [], []
                        for i, coedge in enumerate(coedges):
                            if coedge.loop is not loop or coedge.prev_coedge is not coedges[i-1]:
                                raise ValueError('Broken ACIS coedge ownership or reverse link.')
                            absent(coedge.pcurve, 'parametric trim curves')
                            edge = coedge.edge
                            if edge.type != 'edge' or edge.curve.type != 'straight-curve':
                                raise ValueError('Only straight ACIS edges are supported; curved/unknown edges are not chorded.')
                            start, end = edge.start_vertex, edge.end_vertex
                            if start.type != 'vertex' or end.type != 'vertex' or start.point.type != 'point' or end.point.type != 'point':
                                raise ValueError('Missing ACIS edge vertices.')
                            a, b = Vec3(xyz(start.point.location)), Vec3(xyz(end.point.location))
                            if (b-a).magnitude <= TOL:
                                raise ValueError('ACIS boundary has a degenerate edge.')
                            direction = Vec3(xyz(edge.curve.direction))
                            if direction.magnitude < 1e-12:
                                raise ValueError('ACIS straight curve has a zero direction.')
                            for v, param in ((a, edge.start_param), (b, edge.end_param)):
                                scalar(param, 'edge parameter', -1e12, 1e12)
                                if (Vec3(edge.curve.evaluate(param))-v).magnitude > TOL*max(1, (b-a).magnitude):
                                    raise ValueError('ACIS curve parameters disagree with its vertices.')
                                if abs((v-Vec3(face.surface.origin)).dot(normal)) > TOL*max(1, (b-a).magnitude):
                                    raise ValueError('ACIS face vertices leave the declared plane.')
                            if coedge.sense:
                                a, b = b, a
                            points.append(a); ends.append(b)
                            uses.setdefault(id(edge), []).append(coedge)
                        if any((ends[i]-points[(i+1)%len(points)]).magnitude > TOL for i in range(len(points))):
                            raise ValueError('ACIS boundary endpoints do not connect.')
                        # Determine outer/inner from signed area, not record order.
                        area = sum(((points[i]-points[0]).cross(points[(i+1)%len(points)]-points[0]).dot(normal) for i in range(len(points))), 0)/2
                        polygons.append((area, points))
                    outer = [p for area, p in polygons if area > TOL*TOL]
                    inner = [p for area, p in polygons if area < -TOL*TOL]
                    if len(outer) != 1 or len(outer)+len(inner) != len(polygons):
                        raise ValueError('ACIS loop orientations require one outer boundary and disjoint inner holes.')
                    def native_wire(points):
                        return cq.Wire.makePolygon([cq.Vector(*xyz(p)) for p in points], close=True)
                    f = cq.Face.makeFromWires(native_wire(outer[0]), [native_wire(p) for p in inner])
                    if f.normalAt().dot(cq.Vector(*normal)) < 0:
                        f = cq.Face(f.wrapped.Reversed())
                    if not f.isValid():
                        raise ValueError('ACIS face boundaries are invalid or self-intersecting.')
                    native_faces.append(f); all_double.append(face.double_sided)
                # Require the explicit ACIS adjacency, not just coincident coordinates.
                double = all(f.double_sided for f in faces)
                if any(f.double_sided for f in faces) and not double:
                    raise ValueError('Mixed solid/surface sidedness in an ACIS shell.')
                for linked in uses.values():
                    if len(linked) > 2 or (not double and len(linked) != 2):
                        raise ValueError('ACIS solid shell is open or non-manifold.')
                    if len(linked) == 2:
                        a, b = linked
                        if a.sense == b.sense or a.partner_coedge is not b or b.partner_coedge is not a:
                            raise ValueError('ACIS edge partners are inconsistent or non-manifold.')
                    elif not linked[0].partner_coedge.is_none:
                        raise ValueError('ACIS open boundary has an external partner.')
                sew = BRepBuilderAPI_Sewing(TOL)
                for f in native_faces:
                    sew.Add(f.wrapped)
                sew.Perform()
                result = sew.SewedShape()
                if result.IsNull() or result.ShapeType() not in (TopAbs_SHELL, TopAbs_FACE):
                    raise ValueError('ACIS shell does not form one connected native surface.')
                if double:
                    native_shells.append(cq.Shape.cast(result))
                elif result.ShapeType() == TopAbs_SHELL and cq.Shell(result).Closed():
                    native_shells.append(cq.Shell(result))
                else:
                    raise ValueError('ACIS shell did not form a closed native boundary.')
            if all(all_double):
                pieces.extend(native_shells)
            elif any(all_double):
                raise ValueError('Mixed surface and solid shells in one ACIS lump.')
            else:
                make = BRepBuilderAPI_MakeSolid()
                for shell in native_shells:
                    make.Add(TopoDS.Shell_s(shell.wrapped))
                # Preserve the shell hierarchy (including voids), then orient it.
                fixer = ShapeFix_Solid(make.Solid()); fixer.Perform()
                solid = cq.Shape.cast(fixer.Solid())
                if not solid.isValid() or not solid.Solids() or solid.Volume() <= TOL**3:
                    raise ValueError('ACIS lump does not define a valid positive-volume solid.')
                pieces.append(solid)
        shape = pieces[0] if len(pieces) == 1 else cq.Compound.makeCompound(pieces)
        if transform is not None:
            from kernel import affine
            shape = affine(shape, list(transform))
        if factor != 1:
            shape = shape.scale(factor)
        if not shape.isValid():
            raise ValueError('Transformed ACIS body has invalid topology.')
        output.append(shape)
    report['faces'] = face_count
    return output, report


def bodies_from_shapes(shapes):
    """Map original OCCT edges/faces directly; never sample or weld vertices."""
    import cadquery as cq
    from OCP.BRepTools import BRepTools_WireExplorer
    from OCP.TopExp import TopExp
    from OCP.TopAbs import TopAbs_VERTEX, TopAbs_EDGE
    from OCP.TopTools import TopTools_IndexedMapOfShape
    from ezdxf.math import Vec3
    _, a, _, _, _ = modules()
    output, face_count = [], 0
    for shape in shapes:
        if not shape.isValid() or not shape.Faces():
            raise ValueError('ACIS export needs a valid native solid or bounded planar surface.')
        if any(f.geomType() != 'PLANE' for f in shape.Faces()) or any(e.geomType() != 'LINE' for e in shape.Edges()):
            raise ValueError('ACIS planar adapter rejects curved faces/edges. Export STEP for analytic curved bodies; no tessellation was substituted.')
        solids = shape.Solids()
        if solids:
            if sum(len(s.Faces()) for s in solids) != len(shape.Faces()):
                raise ValueError('Mixed loose surfaces and solids are not exported together.')
            components = [(s, s.Shells(), False) for s in solids]
        else:
            shells = shape.Shells()
            if shells and sum(len(s.Faces()) for s in shells) != len(shape.Faces()):
                raise ValueError('Mixed loose faces and shells are not exported together.')
            components = [(s, [s], True) for s in (shells or shape.Faces())]
        # Stray standalone edges must not vanish from a nominal compound.
        if sum(len(c.Edges()) for c, _, _ in components) != len(shape.Edges()):
            raise ValueError('ACIS export does not discard loose edges or shared components.')
        body = a.Body()
        for component, shells, double in components:
            lump = a.Lump(); body.append_lump(lump)
            vertices, edges = TopTools_IndexedMapOfShape(), TopTools_IndexedMapOfShape()
            TopExp.MapShapes_s(component.wrapped, TopAbs_VERTEX, vertices)
            TopExp.MapShapes_s(component.wrapped, TopAbs_EDGE, edges)
            vertex_map, edge_map, coedge_map = {}, {}, {}
            for shell in shells:
                out_shell = a.Shell(); lump.append_shell(out_shell)
                for face in shell.Faces():
                    face_count += 1
                    if face_count > MAX_FACES:
                        raise ValueError('ACIS export exceeds 20,000 faces.')
                    out_face = a.Face(); out_shell.append_face(out_face); out_face.double_sided = double
                    plane = a.Plane(); plane.origin = Vec3(xyz(face.Center().toTuple()))
                    plane.normal = Vec3(xyz(face.normalAt().toTuple())).normalize()
                    trial = Vec3(1, 0, 0) if abs(plane.normal.x) < .8 else Vec3(0, 1, 0)
                    plane.u_dir = (trial-plane.normal*trial.dot(plane.normal)).normalize(); plane.update_v_dir()
                    out_face.surface = plane
                    for wire in [face.outerWire(), *face.innerWires()]:
                        walk, ordered = BRepTools_WireExplorer(wire.wrapped, face.wrapped), []
                        while walk.More():
                            ordered.append((walk.Current(), walk.CurrentVertex())); walk.Next()
                        if len(ordered) != len(wire.Edges()) or len(ordered) < 3:
                            raise ValueError('Invalid native face boundary for ACIS export.')
                        out_loop, coedges = a.Loop(), []; out_face.append_loop(out_loop)
                        for i, (edge, vertex) in enumerate(ordered):
                            next_vertex = ordered[(i+1)%len(ordered)][1]
                            v_ids = [vertices.FindIndex(v) for v in (vertex, next_vertex)]
                            for v_id, v in zip(v_ids, (vertex, next_vertex)):
                                if v_id not in vertex_map:
                                    out_vertex = a.Vertex(); location = a.Point()
                                    location.location = Vec3(xyz(cq.Vertex(v).toTuple())); out_vertex.point = location
                                    vertex_map[v_id] = out_vertex
                            edge_id = edges.FindIndex(edge)
                            start, end = [vertex_map[v_id] for v_id in v_ids]
                            if edge_id not in edge_map:
                                out_edge, curve = a.Edge(), a.StraightCurve()
                                out_edge.start_vertex, out_edge.end_vertex = start, end
                                delta = end.point.location-start.point.location
                                if delta.magnitude <= TOL:
                                    raise ValueError('ACIS export boundary is too small.')
                                curve.origin, curve.direction = start.point.location, delta.normalize()
                                out_edge.curve, out_edge.end_param = curve, delta.magnitude
                                edge_map[edge_id] = out_edge
                                if start.edge.is_none: start.edge = out_edge
                                if end.edge.is_none: end.edge = out_edge
                                start.ref_count += 1; end.ref_count += 1
                            out_edge = edge_map[edge_id]
                            coedge = a.Coedge(); coedge.edge = out_edge
                            coedge.sense = start is out_edge.end_vertex
                            if out_edge.coedge.is_none: out_edge.coedge = coedge
                            if edge_id in coedge_map:
                                partner = coedge_map[edge_id]
                                if not partner.partner_coedge.is_none or partner.sense == coedge.sense:
                                    raise ValueError('Native shell is non-manifold or inconsistently oriented.')
                                partner.partner_coedge = coedge; coedge.partner_coedge = partner
                            else: coedge_map[edge_id] = coedge
                            coedges.append(coedge)
                        out_loop.set_coedges(coedges)
            if not double and any(c.partner_coedge.is_none for c in coedge_map.values()):
                raise ValueError('Native solid has an open boundary.')
        output.append(body)
    if not 1 <= len(output) <= MAX_BODIES:
        raise ValueError('Select 1–32 native bodies for ACIS export.')
    return output


def encode_bodies(bodies, fmt, unit_mm):
    _, _, sat, sab, hdr = modules()
    class PreciseHeader(hdr.AcisHeader):
        def dumps(self):
            rows = super().dumps()
            rows[2] = repr(self.units_in_mm) + ' 9.9999999999999995e-007 1e-010 '
            return rows

    class PreciseNumbers(sat.SatDataExporter):
        def write_double(self, value):
            if not math.isfinite(value):
                raise ValueError('Non-finite ACIS scalar.')
            self.data.append(repr(float(value)))

    class PreciseSAT(sat.SatExporter):
        def make_data_exporter(self, record):
            return PreciseNumbers(self, record.data)

    # The dependency's default :g formatting has six significant digits;
    # rounding a rotated plane independently of its vertices breaks topology.
    header = PreciseHeader(); header.set_version(700 if fmt == 'sat' else 21800)
    header.units_in_mm = scalar(unit_mm, 'drawing unit'); header.product_id = 'Kestrel CAD planar BREP adapter'
    header.asm_end_marker = fmt == 'sab'
    exporter = PreciseSAT(header) if fmt == 'sat' else sab.SabExporter(header)
    for body in bodies:
        exporter.export(body)
    return ('\n'.join(exporter.dump_sat())+'\n').encode('utf-8') if fmt == 'sat' else exporter.dump_sab()


def export_geometry(shapes, fmt='sat', unit_mm=1.0):
    if fmt not in ('sat', 'sab'):
        raise ValueError('ACIS output must be SAT or SAB.')
    bodies = bodies_from_shapes(shapes)
    data = encode_bodies(bodies, fmt, unit_mm)
    if len(data) > MAX_BYTES:
        raise ValueError('ACIS export exceeds 16 MiB.')
    return data


def export_dxf(shapes, version='R2018', unit='mm'):
    """Actual 3DSOLID/BODY records, not 3DFACE approximations."""
    import ezdxf
    from ezdxf import units
    unit_names = {'mm': units.MM, 'cm': units.CM, 'm': units.M, 'in': units.IN, 'ft': units.FT}
    unit_mm = {'mm': 1, 'cm': 10, 'm': 1000, 'in': 25.4, 'ft': 304.8}
    if version not in ('R2000', 'R2010', 'R2013', 'R2018') or unit not in unit_names:
        raise ValueError('Invalid solid DXF version or drawing units.')
    bodies = bodies_from_shapes(shapes)
    doc = ezdxf.new(version); doc.units = unit_names[unit]
    binary_payload = version in ('R2013', 'R2018')
    for shape, body in zip(shapes, bodies):
        entity = doc.modelspace().add_3dsolid() if shape.Solids() else doc.modelspace().add_body()
        data = encode_bodies([body], 'sab' if binary_payload else 'sat', unit_mm[unit])
        if binary_payload: entity.sab = data
        else: entity.sat = data.decode('utf-8').splitlines()
    output = io.StringIO(); doc.write(output)
    data = output.getvalue().encode(doc.output_encoding, errors='dxfreplace')
    if len(data) > MAX_BYTES:
        raise ValueError('Solid DXF export exceeds 16 MiB.')
    return data
