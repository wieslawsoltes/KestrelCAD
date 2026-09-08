# Editable curves from native geometry

`XEDGES` and `SECTIONCURVES` transfer native edge geometry into independent editable drafting entities. They use the optional local OpenCascade worker, not viewport triangles or polyline fits. The original B-rep bodies are retained. The resulting LINE, ARC, CIRCLE, ELLIPSE and rational SPLINE entities work in the ordinary browser editor and supported DXF exchange, including after opening the project on GitHub Pages.

## Extract edges

Select one or more visible top-level native objects and run `XEDGES`, or choose **Solids → Drafting from solids → Extract editable edges**. Leave the index field blank to extract all edges. For one source only, a comma-separated list such as `4,1` selects current zero-based topology indices in that order. Native edge-editing dialogs expose the current edge index table. These indices are not persistent topology names: they can change after a Boolean or another modeling operation.

The result contains each native edge once per source. A cylinder can therefore produce two circles and its seam edge; a box produces twelve lines. There is no hidden-line removal, silhouette computation, duplicate-edge elimination across different bodies, projection to the view plane, or automatic joining into closed profiles. Degenerate point-like edges are omitted and counted explicitly. Unsupported edge carriers cause the entire extraction to fail instead of silently replacing them with sampled segments.

## Extract a plane section

Select native objects and run `SECTIONCURVES`, or choose **Extract editable section curves** in the same ribbon group. Enter the plane origin and normal in the active UCS. The normal must be nonzero. The worker intersects the actual world-positioned native geometry with the plane, then transfers its resulting edges.

For a cylinder along world Z, a horizontal plane creates an analytic circle; an oblique plane can create an analytic ellipse. A tube preserves both outer and inner boundary curves. A missed section creates no geometry and no undo entry. Tangent intersections consisting only of isolated vertices likewise create no curve entities. A plane coincident with a surface follows the native kernel's section behavior rather than inventing a filled region.

The normal is transformed as a direction, without adding the UCS origin. Output geometry stays in world coordinates. Neither camera orientation nor display tessellation tolerance selects the section plane.

## Geometry representation

Straight carriers transfer their trimmed endpoints as LINE. Circular and elliptical carriers retain their center, full 3D axes and trimmed angular interval. Only complete closed circular carriers become CIRCLE; trimmed circular carriers become ARC. Elliptical arcs retain their start/end parameters.

Finite B-spline, Bezier, hyperbolic and parabolic edge carriers transfer through OCCT's B-spline conversion with their actual trim interval. The editable representation has control points, degree, an expanded clamped knot vector and positive rational weights. A periodic carrier is opened at its seam into an equivalent closed, nonperiodic, clamped representation. Knot intervals are normalized to 0–1 and weights are divided by their maximum; these changes do not change the mathematical curve locus. Conic conversions may change parameterization. No least-squares fit to display samples is used.

The kernel's geometric operations still use floating-point tolerances. In particular, surface intersection is not symbolic exact arithmetic. The extracted representation preserves the native intersection carrier; it does not certify arbitrary-file equivalence or arbitrary modeling tolerances.

## Rational spline profiles and paths

The existing native profile commands now accept finite, clamped SPLINE control data directly. A closed rational spline can define a planar region or an extrusion profile; an open spline can be a sweep path. Revolve and loft use the same validated profile path, subject to their existing native operation constraints. Open splines requested as closed profiles reject rather than receiving an invented closing line. Open elliptical arcs likewise reject rather than being silently treated as complete ellipses.

The worker subdivides a spline only at existing distinct knot boundaries. This is exact parameter subdivision, not a refit. It avoids handing native integration a single edge spanning derivative discontinuities. A degree-one, two-pole spline is represented as its equivalent native straight segment. More general paths remain spline geometry. Closed profiles must also satisfy the native operation's planarity, validity and material requirements; a closed flag alone is not proof of a usable solid profile.

## Persistence, DXF and precision

One successful extraction creates one transaction on the current visible, unlocked layer and selects the new entities. Sources can be locked for read-only extraction. Undo removes the curves, redo restores them, and `.kcad` retains the independent curves and original authoritative BREP. Output is a snapshot: subsequent source modeling does not recompute it, and it is not a persistent associative section or face reference.

Standard DXF writes actual analytic entities and SPLINE control points, knots and weights. The existing exchange worker uses the same writer. Group 42 knot tolerance is bounded below every distinct positive knot span instead of advertising a fixed `1e-7` tolerance that can make downstream readers round away meaningful knot detail. JavaScript de Boor evaluation now includes the exact final endpoint and does not discard a positive knot span merely because it is below a scene-length epsilon. Independent tests exercise both a closed periodic carrier converted to clamped form and a spline with a `1e-10` knot interval.

DXF export of the original native source body through the ordinary drawing exporter remains faceted according to its existing contract. Extracting edges does not turn that export into unrestricted native solid/DWG interchange. Use the dedicated native exchange tools for supported B-rep output.

## Limits and transactional behavior

Each request accepts 1–32 visible top-level native objects, at most 20,000 combined native faces/edges, and at most 2,000 visited output edges. Each spline has degree 1–10 and 2–2,000 poles; the request has at most 20,000 combined spline poles. Coordinates are bounded to the kernel's supported range (absolute value at most `1e8`), and rational weight ratios below `1e-12` reject as ill-conditioned. These are resource/conditioning guards, not throughput guarantees.

Plain meshes, nested block/xref traversal, arbitrary unsupported curve classes and unordered edge-to-wire assembly are outside these commands. A failed carrier conversion aborts all outputs. Client-side response validation rejects malformed or incomplete edge results before any document write. A newer edit, changed source object, closed/replaced dialog, or locked output layer prevents applying a stale result. The server retains its process, payload and timeout limits.

## Reproducible verification

```sh
node tests/native-curves.test.js
python3 tests/native-curves.test.py
python3 tests/native_curves_interop.py
python3 tools/build.py
python3 tests/native-curves.browser.py
python3 tools/verify.py --previews
```

Native tests use actual OCCT curves, bodies and STEP output. Client tests label synthetic transport fixtures and check geometry contracts, persistence and rollback. Browser tests run the actual served HTTP bridge, ribbon, dialogs, downloads, profile operations and stale-request rejection. Independent ezdxf audits require zero errors and zero automatic fixes, and compare downstream evaluated curve points with native reference geometry. Hardware WebGPU and real native DWG codecs remain separate verification paths.

Primary references: [XEDGES workflow](https://help.autodesk.com/cloudhelp/2020/ENU/AutoCAD-Core/files/GUID-6B6E69D0-62C1-4D96-B568-1818E3C997F4.htm), [OCCT curve conversion](https://dev.opencascade.org/doc/occt-7.6.0/refman/html/class_geom_convert.html), [DXF SPLINE fields](https://help.autodesk.com/cloudhelp/2016/ENU/AutoCAD-DXF/files/GUID-E1F884F8-AA90-4864-A215-3182D47A9C74.htm), and [ezdxf SPLINE API](https://ezdxf.readthedocs.io/en/stable/dxfentities/spline.html). The command implementation and interchange guarantees here are limited to the documented native geometry subset.
