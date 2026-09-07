#!/usr/bin/env python3
"""Stateless OpenCascade B-rep worker. Optional CadQuery dependency; not ACIS.

Only bounded JSON and in-memory/temporary-file data are accepted. No client file
paths, shell commands, Python expressions or executable plug-ins are evaluated.
"""
from __future__ import annotations
import base64
import io
import json
import math
import os
from pathlib import Path
import sys
import tempfile

MAX_BREP = 16 * 1024 * 1024
MAX_TOPOLOGY = 20000
MAX_MESH = 500000
OPERATIONS = frozenset('box cylinder cone sphere torus extrude revolve loft sweep union subtract intersect fillet chamfer shell section transform import export inspect'.split())


def num(value, label='number', lo=-1e8, hi=1e8):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{label} must be a finite number')
    value = float(value)
    if not math.isfinite(value) or not lo <= value <= hi:
        raise ValueError(f'{label} must be in [{lo}, {hi}]')
    return value


def positive(value, label='size'):
    return num(value, label, 1e-6, 1e7)


def vector(value, label='vector'):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f'{label} must have three coordinates')
    return tuple(num(x, label) for x in value)


def decode(value):
    if not isinstance(value, str) or len(value) > (MAX_BREP * 4 // 3 + 8):
        raise ValueError('Native data is missing or exceeds 16 MiB')
    try:
        result = base64.b64decode(value, validate=True)
    except Exception as exc:
        raise ValueError('Invalid base64 native data') from exc
    if not result or len(result) > MAX_BREP:
        raise ValueError('Native data is empty or too large')
    return result


def checked(shape):
    if shape is None or shape.wrapped.IsNull() or not shape.isValid():
        raise ValueError('Operation did not produce valid native topology')
    if len(shape.Edges()) > MAX_TOPOLOGY or len(shape.Faces()) > MAX_TOPOLOGY:
        raise ValueError('Native topology exceeds the operation limit')
    return shape


def affine(shape, values):
    if values is None:
        return shape
    if not isinstance(values, list) or len(values) != 16:
        raise ValueError('Transform must have 16 column-major values')
    m = [num(x, 'transform') for x in values]
    if any(abs(m[i]) > 1e-12 for i in (3, 7, 11)) or abs(m[15] - 1) > 1e-12:
        raise ValueError('Perspective transforms are not native solid transforms')
    determinant = m[0]*(m[5]*m[10]-m[9]*m[6])-m[4]*(m[1]*m[10]-m[9]*m[2])+m[8]*(m[1]*m[6]-m[5]*m[2])
    if abs(determinant) < 1e-18:
        raise ValueError('Singular native transform')
    import cadquery as cq
    from OCP.gp import gp_Mat, gp_GTrsf, gp_XYZ
    from OCP.BRepBuilderAPI import BRepBuilderAPI_GTransform
    matrix = gp_Mat(m[0],m[4],m[8],m[1],m[5],m[9],m[2],m[6],m[10])
    transform = gp_GTrsf(matrix, gp_XYZ(m[12],m[13],m[14]))
    return checked(cq.Shape.cast(BRepBuilderAPI_GTransform(shape.wrapped, transform, True).Shape()))


def read_shape(item):
    import cadquery as cq
    if not isinstance(item, dict) or item.get('provider') != 'OCCT':
        raise ValueError('A native OCCT body is required; a mesh is not a B-rep')
    data = decode(item.get('brep'))
    if b'CASCADE Topology' not in data[:512]:
        raise ValueError('Invalid OpenCascade BREP stream')
    return affine(checked(cq.Shape.importBrep(io.BytesIO(data))), item.get('transform'))


def wire(profile, closed=True):
    import cadquery as cq
    if not isinstance(profile, dict):
        raise ValueError('A profile object is required')
    kind = str(profile.get('type', '')).upper()
    normal = cq.Vector(*vector(profile.get('normal', [0,0,1]), 'profile normal'))
    if normal.Length < 1e-12:
        raise ValueError('Profile normal is zero')
    normal = normal.normalized()
    if kind in ('CIRCLE', 'ELLIPSE'):
        center = vector(profile.get('center', [0,0,0]), 'profile center')
        if kind == 'CIRCLE':
            edge = cq.Edge.makeCircle(positive(profile.get('radius'), 'radius'), center, normal)
        else:
            edge = cq.Edge.makeEllipse(positive(profile.get('rx'), 'ellipse radius X'), positive(profile.get('ry'), 'ellipse radius Y'), center, normal, vector(profile.get('xdir', [1,0,0]), 'ellipse axis'))
        return cq.Wire.assembleEdges([edge])
    points = profile.get('points')
    if not isinstance(points, list) or not 2 <= len(points) <= 2000:
        raise ValueError('A profile must contain 2–2000 points')
    points = [cq.Vector(*vector(p, 'profile point')) for p in points]
    if (points[0]-points[-1]).Length < 1e-10:
        points.pop()
    if closed and len(points) < 3:
        raise ValueError('A closed polygon requires three distinct vertices')
    bulges = profile.get('bulges', [])
    if not isinstance(bulges, list):
        raise ValueError('Invalid polyline bulges')
    edges = []
    for i in range(len(points) if closed else len(points)-1):
        a, b = points[i], points[(i+1) % len(points)]
        if (b-a).Length < 1e-10:
            raise ValueError('Zero-length profile edge')
        bulge = num(bulges[i], 'bulge', -10000, 10000) if i < len(bulges) else 0
        if abs(bulge) < 1e-12:
            edges.append(cq.Edge.makeLine(a,b))
        else:
            middle = (a+b)*0.5 - normal.cross(b-a)*(bulge*0.5)
            edges.append(cq.Edge.makeThreePointArc(a,middle,b))
    result = cq.Wire.assembleEdges(edges)
    if not result.isValid() or (closed and not result.IsClosed()):
        raise ValueError('Invalid or non-closed profile wire')
    return result


def selection(shape, indices, kind='edges'):
    values = shape.Edges() if kind.lower() in ('edge','edges') else shape.Faces()
    if not isinstance(indices, list) or not indices or len(indices) > MAX_TOPOLOGY:
        raise ValueError('Choose one or more topology indices')
    if any(isinstance(i,bool) or not isinstance(i,int) or not 0 <= i < len(values) for i in indices):
        raise ValueError('Topology index is out of range')
    if len(set(indices)) != len(indices):
        raise ValueError('Duplicate topology indices')
    return [values[i] for i in indices]


def pack(shape, tolerance=0.1):
    import cadquery as cq
    import OCP
    from OCP.BRepTools import BRepTools
    shape = checked(shape)
    BRepTools.Clean_s(shape.wrapped)
    stream = io.BytesIO()
    shape.exportBrep(stream)
    binary = stream.getvalue()
    if len(binary) > MAX_BREP:
        raise ValueError('Serialized native body exceeds 16 MiB')
    vertices, triangles = shape.tessellate(tolerance, 0.15) if shape.Faces() else ([], [])
    if len(vertices) > MAX_MESH or len(triangles) > MAX_MESH:
        raise ValueError('Display tessellation exceeds the mesh limit')
    edges, faces, polylines = [], [], []
    for i, edge in enumerate(shape.Edges()):
        length = float(edge.Length())
        kind = edge.geomType()
        edges.append({'index':i,'type':kind,'length':length,'center':list(edge.Center().toTuple())})
        count = 2 if kind == 'LINE' else min(256, max(16, int(length/max(tolerance,0.01))))
        sampled = edge.sample(count)[0]
        polylines.append([list(p.toTuple()) for p in sampled])
    for i, face in enumerate(shape.Faces()):
        faces.append({'index':i,'type':face.geomType(),'area':float(face.Area()),'center':list(face.Center().toTuple())})
    solids = shape.Solids()
    return {'provider':'OCCT','version':getattr(OCP,'__version__','unknown'),'cadquery':cq.__version__,
            'brep':base64.b64encode(binary).decode('ascii'),
            'mesh':{'type':'MESH','vertices':[list(v.toTuple()) for v in vertices],'faces':[list(t) for t in triangles]},
            'edges':edges,'faces':faces,'edgePolylines':polylines,
            'volume':sum(abs(float(s.Volume())) for s in solids),'area':float(shape.Area()),
            'solidCount':len(solids),'valid':True,'tolerance':tolerance}


def execute(request):
    if not isinstance(request, dict):
        raise ValueError('Expected a JSON operation object')
    operation = request.get('op', request.get('operation'))
    if operation not in OPERATIONS:
        raise ValueError('Unsupported native operation')
    params = request.get('params', {})
    if not isinstance(params, dict):
        raise ValueError('Invalid operation parameters')
    inputs = request.get('inputs', [])
    if not isinstance(inputs, list) or len(inputs) > 32:
        raise ValueError('At most 32 native inputs are accepted')
    tolerance = num(request.get('tolerance', 0.1), 'tessellation tolerance', 0.001, 1000)
    import cadquery as cq
    shapes = [read_shape(item) for item in inputs]
    def one():
        if len(shapes) != 1:
            raise ValueError('This operation requires exactly one native body')
        return shapes[0]
    def solid():
        values = one().Solids()
        if len(values) != 1:
            raise ValueError('This operation requires exactly one connected solid')
        return values[0]
    def holes():
        values = params.get('holes', [])
        if not isinstance(values, list) or len(values) > 64:
            raise ValueError('At most 64 inner profile wires are accepted')
        return [wire(p) for p in values]
    p = params
    if operation == 'box':
        shape = cq.Solid.makeBox(positive(p.get('width',20),'width'),positive(p.get('depth',30),'depth'),positive(p.get('height',10),'height'))
    elif operation == 'cylinder':
        shape = cq.Solid.makeCylinder(positive(p.get('radius',10),'radius'),positive(p.get('height',20),'height'))
    elif operation == 'cone':
        r1 = num(p.get('radius1',10),'first radius',0,1e7)
        r2 = num(p.get('radius2',0),'second radius',0,1e7)
        if max(r1,r2) < 1e-6 or abs(r1-r2) < 1e-12:
            raise ValueError('Cone radii must differ and cannot both be zero')
        shape = cq.Solid.makeCone(r1,r2,positive(p.get('height',10),'height'))
    elif operation == 'sphere':
        shape = cq.Solid.makeSphere(positive(p.get('radius',10),'radius'),angleDegrees1=-90,angleDegrees2=90)
    elif operation == 'torus':
        major = positive(p.get('majorRadius',p.get('major',20)),'major radius')
        minor = positive(p.get('minorRadius',p.get('minor',5)),'minor radius')
        if major <= minor:
            raise ValueError('Torus major radius must exceed minor radius')
        shape = cq.Solid.makeTorus(major,minor)
    elif operation == 'extrude':
        direction = vector(p.get('vector',[0,0,10]),'extrusion vector')
        if sum(x*x for x in direction) < 1e-12:
            raise ValueError('Extrusion vector cannot be zero')
        shape = cq.Solid.extrudeLinear(wire(p.get('profile')),holes(),direction,num(p.get('taper',0),'taper',-80,80))
    elif operation == 'revolve':
        a,b = vector(p.get('axisStart',[0,0,0])),vector(p.get('axisEnd',[0,0,1]))
        if sum((x-y)**2 for x,y in zip(a,b)) < 1e-12:
            raise ValueError('Revolution axis cannot be zero')
        shape = cq.Solid.revolve(wire(p.get('profile')),holes(),num(p.get('angle',360),'angle',0.01,360),a,b)
    elif operation == 'loft':
        profiles = p.get('profiles',[])
        if not isinstance(profiles,list) or not 2 <= len(profiles) <= 32:
            raise ValueError('Loft requires 2–32 profiles')
        shape = cq.Solid.makeLoft([wire(v) for v in profiles],bool(p.get('ruled',False)))
    elif operation == 'sweep':
        shape = cq.Solid.sweep(wire(p.get('profile')),[],wire(p.get('path'),False),True,bool(p.get('frenet',False)))
    elif operation in ('union','subtract','intersect'):
        if len(shapes) < 2:
            raise ValueError('Boolean operations require at least two native bodies')
        shape = shapes[0]
        for other in shapes[1:]:
            shape = {'union':shape.fuse,'subtract':shape.cut,'intersect':shape.intersect}[operation](other)
        shape = shape.clean()
        if not shape.Solids():
            raise ValueError('Boolean result contains no solid')
    elif operation in ('fillet','chamfer','shell'):
        source = solid()
        if operation == 'fillet':
            shape = source.fillet(positive(p.get('radius'),'fillet radius'),selection(source,p.get('edges')))
        elif operation == 'chamfer':
            distance = positive(p.get('distance'),'chamfer distance')
            other = p.get('distance2')
            shape = source.chamfer(distance,positive(other,'second distance') if other is not None else None,selection(source,p.get('edges')))
        else:
            from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeThickSolid
            from OCP.TopTools import TopTools_ListOfShape
            thickness = num(p.get('thickness'),'shell thickness',-1e7,1e7)
            if abs(thickness) < 1e-6:
                raise ValueError('Shell thickness cannot be zero')
            removed = TopTools_ListOfShape()
            for face in selection(source,p.get('faces'),'faces'):
                removed.Append(face.wrapped)
            builder = BRepOffsetAPI_MakeThickSolid()
            builder.MakeThickSolidByJoin(source.wrapped,removed,thickness,1e-5)
            if not builder.IsDone():
                raise ValueError('Native shell operation failed')
            shape = cq.Shape.cast(builder.Shape())
    elif operation == 'section':
        from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
        from OCP.gp import gp_Pln, gp_Pnt, gp_Dir
        origin = vector(p.get('origin',p.get('point',[0,0,0])))
        normal = vector(p.get('normal',[0,0,1]))
        if sum(x*x for x in normal) < 1e-12:
            raise ValueError('Section normal cannot be zero')
        builder = BRepAlgoAPI_Section(one().wrapped,gp_Pln(gp_Pnt(*origin),gp_Dir(*normal)),False)
        builder.Approximation(True)
        builder.Build()
        if not builder.IsDone():
            raise ValueError('Native section failed')
        shape = cq.Shape.cast(builder.Shape())
        if not shape.Edges():
            raise ValueError('Section plane does not intersect the body')
    elif operation in ('inspect','transform'):
        shape = one()
    elif operation == 'import':
        fmt = str(p.get('format','')).lower()
        if fmt not in ('step','iges','brep'):
            raise ValueError('Supported native imports: STEP, IGES, BREP. SAT/SAB are not implemented.')
        binary = decode(p.get('data'))
        with tempfile.TemporaryDirectory(prefix='kestrel-import-') as directory:
            path = Path(directory)/('input.'+fmt)
            path.write_bytes(binary)
            if fmt == 'step':
                shape = cq.importers.importStep(str(path)).val()
            elif fmt == 'brep':
                shape = cq.Shape.importBrep(io.BytesIO(binary))
            else:
                from OCP.IGESControl import IGESControl_Reader
                from OCP.IFSelect import IFSelect_RetDone
                reader = IGESControl_Reader()
                if reader.ReadFile(str(path)) != IFSelect_RetDone:
                    raise ValueError('IGES file could not be read')
                reader.TransferRoots()
                shape = cq.Shape.cast(reader.OneShape())
        scale = positive(p.get('scale',1),'import scale')
        if scale != 1:
            shape = shape.scale(scale)
    elif operation == 'export':
        shape = one()
        fmt = str(p.get('format','')).lower()
        if fmt not in ('step','iges','brep','stl'):
            raise ValueError('Supported native exports: STEP, IGES, BREP, STL')
        scale = positive(p.get('scale',1),'export scale')
        if scale != 1:
            shape = shape.scale(scale)
        with tempfile.TemporaryDirectory(prefix='kestrel-export-') as directory:
            path = Path(directory)/('output.'+fmt)
            if fmt == 'brep':
                stream=io.BytesIO(); shape.exportBrep(stream); binary=stream.getvalue()
            elif fmt == 'iges':
                from OCP.IGESControl import IGESControl_Writer
                writer=IGESControl_Writer('MM',0)
                if not writer.AddShape(shape.wrapped) or not writer.Write(str(path)):
                    raise ValueError('IGES export failed')
                binary=path.read_bytes()
            else:
                cq.exporters.export(shape,str(path),exportType=fmt.upper(),tolerance=tolerance)
                binary=path.read_bytes()
        if not binary or len(binary)>MAX_BREP:
            raise ValueError('Native export is empty or exceeds 16 MiB')
        return {'format':fmt,'data':base64.b64encode(binary).decode('ascii'),'bytes':len(binary),'unit':'mm' if fmt in ('step','iges') else 'drawing'}
    else:
        raise ValueError('Unsupported native operation')
    shape = affine(checked(shape),p.get('matrix'))
    return pack(shape,tolerance)


def main():
    # OpenCascade emits progress text on fd 1. Keep protocol stdout JSON-only.
    output=os.dup(1)
    os.dup2(2,1)
    try:
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_AS,(6*1024**3,6*1024**3))
            resource.setrlimit(resource.RLIMIT_CPU,(55,55))
            resource.setrlimit(resource.RLIMIT_FSIZE,(64*1024**2,64*1024**2))
        except (ImportError,ValueError,OSError):
            pass
        raw=sys.stdin.buffer.read(64*1024*1024+1)
        if len(raw)>64*1024*1024:
            raise ValueError('Request exceeds 64 MiB')
        result={'result':execute(json.loads(raw))}
    except ImportError:
        result={'error':'Optional native kernel is not installed. Install requirements-kernel.txt and restart the local server.'}
    except Exception as exc:
        result={'error':str(exc)[:2000]}
    with os.fdopen(output,'w',encoding='utf-8') as stream:
        json.dump(result,stream,allow_nan=False,separators=(',',':'))
        stream.write('\n')


if __name__=='__main__':
    main()
