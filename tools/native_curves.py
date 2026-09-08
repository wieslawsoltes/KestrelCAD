"""Transfer native edge carriers to editable drafting curves, never polylines.

Carrier conversion preserves the kernel's geometry. Surface intersection itself
retains OCCT numerical tolerances; this is not symbolic exact arithmetic.
"""
from __future__ import annotations
import math

MAX_CURVES = 2000
MAX_POLES = 20000


def extract_edge(edge):
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GeomAbs import (GeomAbs_Line, GeomAbs_Circle, GeomAbs_Ellipse,
                             GeomAbs_BSplineCurve, GeomAbs_BezierCurve,
                             GeomAbs_Hyperbola, GeomAbs_Parabola)
    from OCP.Geom import Geom_TrimmedCurve
    from OCP.GeomConvert import GeomConvert
    from kernel import vector
    if BRep_Tool.Degenerated_s(edge.wrapped):
        return None
    curve = BRepAdaptor_Curve(edge.wrapped)
    first, last = curve.FirstParameter(), curve.LastParameter()
    if not math.isfinite(first) or not math.isfinite(last) or not first < last or max(abs(first), abs(last)) > 1e100:
        raise ValueError('Native edge must have a finite nonzero parameter interval.')
    def xyz(p):
        return list(vector(list(p.Coord()), 'curve coordinate'))
    kind = curve.GetType()
    if kind == GeomAbs_Line:
        return {'type': 'LINE', 'points': [xyz(curve.Value(first)), xyz(curve.Value(last))]}
    if kind in (GeomAbs_Circle, GeomAbs_Ellipse):
        conic = curve.Circle() if kind == GeomAbs_Circle else curve.Ellipse()
        rx = conic.Radius() if kind == GeomAbs_Circle else conic.MajorRadius()
        ry = conic.Radius() if kind == GeomAbs_Circle else conic.MinorRadius()
        full = abs(last-first - 2*math.pi) <= 1e-12 and edge.IsClosed()
        data = {'type': ('CIRCLE' if full else 'ARC') if kind == GeomAbs_Circle else 'ELLIPSE',
                'center': xyz(conic.Location()), 'normal': xyz(conic.Axis().Direction()),
                'axisX': [v*rx for v in xyz(conic.XAxis().Direction())],
                'axisY': [v*ry for v in xyz(conic.YAxis().Direction())]}
        if kind == GeomAbs_Circle:
            data['radius'] = rx
        else:
            data.update(rx=rx, ry=ry)
        if not full:
            data.update(startAngle=first, endAngle=last)
        return data
    if kind not in (GeomAbs_BSplineCurve, GeomAbs_BezierCurve, GeomAbs_Hyperbola, GeomAbs_Parabola):
        raise ValueError('This edge carrier cannot be transferred without approximation.')
    carrier = BRep_Tool.Curve_s(edge.wrapped, 0., 0.)  # includes location
    spline = GeomConvert.CurveToBSplineCurve_s(Geom_TrimmedCurve(carrier, first, last))
    if spline.IsPeriodic():
        raise ValueError('Native periodic carrier could not be opened at its edge seam.')
    degree, count = spline.Degree(), spline.NbPoles()
    if not 1 <= degree <= 10 or not 2 <= count <= 2000:
        raise ValueError('Editable spline requires degree 1–10 and 2–2000 control points.')
    knots = [spline.Knot(i) for i in range(1, spline.NbKnots()+1)
             for _ in range(spline.Multiplicity(i))]
    if len(knots) != count+degree+1 or spline.Multiplicity(1) != degree+1 or spline.Multiplicity(spline.NbKnots()) != degree+1:
        raise ValueError('Native spline conversion did not produce a clamped knot sequence.')
    low, span = knots[0], knots[-1]-knots[0]
    weights = [spline.Weight(i) for i in range(1,count+1)]
    maximum = max(weights)
    weights = [w/maximum for w in weights]
    if min(weights) < 1e-12 or not all(math.isfinite(w) for w in weights):
        raise ValueError('Native rational weights exceed the supported conditioning range.')
    return {'type':'SPLINE', 'controlPoints':[xyz(spline.Pole(i)) for i in range(1,count+1)],
            'degree':degree, 'knots':[(k-low)/span for k in knots], 'weights':weights,
            'closed':bool(edge.IsClosed())}


def extract(shapes, params):
    import cadquery as cq
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
    from OCP.gp import gp_Pln, gp_Pnt, gp_Dir
    from kernel import selection, vector, MAX_TOPOLOGY
    mode = params.get('mode', 'edges')
    if mode not in ('edges','section') or not 1 <= len(shapes) <= 32:
        raise ValueError('Choose edge extraction or plane section of 1–32 native bodies.')
    if sum(len(s.Edges())+len(s.Faces()) for s in shapes) > MAX_TOPOLOGY:
        raise ValueError('Combined curve-extraction topology exceeds 20,000 faces/edges.')
    if 'edges' in params and (mode != 'edges' or len(shapes) != 1):
        raise ValueError('Explicit edge indices require one native body in edge mode.')
    plane = None
    if mode == 'section':
        origin = vector(params.get('origin',[0,0,0]), 'section origin')
        normal = vector(params.get('normal',[0,0,1]), 'section normal')
        if math.hypot(*normal) < 1e-12:
            raise ValueError('Section normal must be nonzero.')
        plane = gp_Pln(gp_Pnt(*origin),gp_Dir(*normal))
    rows, degenerate, poles, visited = [], 0, 0, 0
    for source_index, source in enumerate(shapes):
        shape = source
        if plane is not None:
            builder = BRepAlgoAPI_Section(source.wrapped, plane, False)
            builder.Approximation(False); builder.Build()
            if not builder.IsDone():
                raise ValueError(f'Native section failed for body {source_index+1}.')
            shape = cq.Shape.cast(builder.Shape())
            if shape.isNull():
                continue
            if not shape.isValid():
                raise ValueError('Native section returned invalid topology.')
        edges = shape.Edges()
        indices = params.get('edges')
        chosen = list(enumerate(edges)) if indices is None else list(zip(indices,selection(shape,indices,'edges')))
        visited += len(chosen)
        if visited > MAX_CURVES:
            raise ValueError('At most 2,000 native edges can be extracted at once.')
        for edge_index, edge in chosen:
            try:
                entity = extract_edge(edge)
                if entity is None:
                    degenerate += 1
                    continue
                poles += len(entity.get('controlPoints',[]))
                if poles > MAX_POLES:
                    raise ValueError('Combined spline control-point limit is 20,000.')
                rows.append({'sourceIndex':source_index,'edgeIndex':edge_index,'entity':entity})
            except Exception as exc:
                raise ValueError(f'Body {source_index+1}, edge {edge_index}: {exc}') from exc
    return {'provider':'OCCT','schema':1,'operation':'extract-curves','mode':mode,
            'bodyCount':len(shapes),'curveCount':len(rows),'curves':rows,'degenerateEdges':degenerate,
            'warnings':['Output curves are independent snapshots, not persistent topological references.',
                        'Section geometry uses OCCT intersection tolerances; no display tessellation is copied.']}


def spline_wire(profile, closed):
    """Rebuild a finite, clamped rational drafting spline for native profile tools."""
    import cadquery as cq
    from OCP.Geom import Geom_BSplineCurve
    from OCP.gp import gp_Pnt
    from OCP.TColgp import TColgp_Array1OfPnt
    from OCP.TColStd import TColStd_Array1OfReal,TColStd_Array1OfInteger
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from kernel import num,vector
    points,knots,degree = profile.get('controlPoints'),profile.get('knots'),profile.get('degree')
    if not isinstance(points,list) or not 2 <= len(points) <= 2000 or type(degree) is not int or not 1 <= degree <= min(10,len(points)-1):
        raise ValueError('Invalid native spline degree or control-point count.')
    points = [vector(p,'spline pole') for p in points]
    if not isinstance(knots,list) or len(knots) != len(points)+degree+1:
        raise ValueError('Spline knot count must equal poles + degree + 1.')
    knots = [num(k,'spline knot',-1e100,1e100) for k in knots]
    if any(a>b for a,b in zip(knots,knots[1:])) or knots[-1] <= knots[0]:
        raise ValueError('Invalid spline knot sequence.')
    unique,mults = [],[]
    for k in knots:
        if unique and k == unique[-1]:mults[-1] += 1
        else:unique.append(k);mults.append(1)
    if mults[0] != degree+1 or mults[-1] != degree+1 or any(m>degree for m in mults[1:-1]):
        raise ValueError('Native profiles require a clamped nonperiodic spline.')
    weights = profile.get('weights',[1]*len(points))
    if not isinstance(weights,list) or len(weights) != len(points):
        raise ValueError('Invalid spline weight count.')
    weights = [num(w,'spline weight',1e-100,1e100) for w in weights]
    maximum = max(weights); weights = [w/maximum for w in weights]
    if min(weights)<1e-12:raise ValueError('Spline weights exceed conditioning range.')
    pp,ww = TColgp_Array1OfPnt(1,len(points)),TColStd_Array1OfReal(1,len(points))
    kk,mm = TColStd_Array1OfReal(1,len(unique)),TColStd_Array1OfInteger(1,len(unique))
    for i,(p,w) in enumerate(zip(points,weights),1):pp.SetValue(i,gp_Pnt(*p));ww.SetValue(i,w)
    low,span = unique[0],unique[-1]-unique[0]
    for i,(k,m) in enumerate(zip(unique,mults),1):kk.SetValue(i,(k-low)/span);mm.SetValue(i,m)
    curve = Geom_BSplineCurve(pp,ww,kk,mm,degree,False)
    # Split only at existing knot boundaries. This is exact subdivision, not
    # sampling, and avoids integrating across discontinuous parameter derivatives.
    edges = ([cq.Edge.makeLine(points[0], points[-1])] if degree == 1 and len(points) == 2 else
             [cq.Edge(BRepBuilderAPI_MakeEdge(curve, curve.Knot(i), curve.Knot(i+1)).Edge())
              for i in range(1,curve.NbKnots())])
    result = cq.Wire.assembleEdges(edges)
    if not result.isValid() or (closed and not result.IsClosed()):
        raise ValueError('Spline profile is not a valid closed wire; open splines can be sweep paths.')
    return result
