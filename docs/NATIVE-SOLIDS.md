# Native solid modeling

## Workflows

Use **Solids**, not **Model**, for native B-rep objects. SOLIDBOX, SOLIDCYLINDER, SOLIDCONE, SOLIDSPHERE and SOLIDTORUS have numeric size and UCS-placement dialogs. Select closed profiles then SOLIDEXTRUDE or SOLIDREVOLVE. Inner selected profiles become holes. SOLIDLOFT follows profile selection order. SOLIDSWEEP takes a profile then a path. Source profiles are retained; a feature-history dependency graph is not yet provided.

SOLIDUNION, SOLIDSUBTRACT and SOLIDINTERSECT operate in selection order and replace their operands atomically. SOLIDFILLET and SOLIDCHAMFER modify native edges, not triangle edges. SOLIDSHELL removes selected faces with signed thickness. SOLIDSECTION creates a native edge result against an arbitrary plane. A failed or empty result leaves the drawing unchanged.

SOLIDINFO inspects the current transformed body. Fillet, chamfer and shell dialogs refresh topology before showing index tables. Indices are for the current serialized shape only; they are not persistent identifiers through future feature changes. Native solids support ordinary move/rotate/scale/mirror by retaining an authoritative affine matrix alongside the display mesh. Direct vertex manipulation is rejected until SOLIDDETACH is explicitly used.

STEPIMPORT accepts STEP, IGES or OCCT BREP through a local file picker. STEPEXPORT offers STEP, IGES, BREP and tessellated STL. STEP and IGES are exchanged in mm, with drawing-unit conversion. The native .kcad project keeps exact B-rep data; normal DXF export remains faceted 3DFACE rather than ACIS 3DSOLID.

## Implementation and limits

The plain JavaScript frontend stores an OCCT BREP stream, an affine transform, native topology/mass metadata and an independent display tessellation. The optional Python worker uses real CadQuery 2.8.0 / OCCT shape operations. The server accepts only same-origin localhost requests with the application header. A single native job runs at once. The worker accepts a structured operation allowlist, not Python expressions, executable paths or shell commands. Temporary files have fixed names in private temporary directories. The server enforces 64 MiB request/output and 60 seconds wall time. On platforms with `resource`, the worker also caps virtual address space, CPU time and output file size.

Native BREP/file inputs are limited to 16 MiB; results to 20,000 edges/faces and 500,000 display vertices/triangles. These are safety limits, not performance promises. The engine is optional and is not shipped inside the standalone HTML or run by GitHub Pages. CadQuery/OCCT retain their own licenses; no proprietary SDK or font binary is bundled.

A B-rep kernel uses finite-precision curves, surfaces and tolerances. It is not exact symbolic arithmetic, an ACIS implementation, a complete SAT/SAB translator, or proof that every topology is valid for manufacturing. Imported IGES data may be disconnected faces rather than closed solids. Fillet and shell operations can fail on degenerate geometry or infeasible radii; such failures are reported rather than replaced by approximate meshes.

## Verification

`tests/kernel.test.py` exercises the real installed engine, including analytical volumes, native profiles/holes, loft/sweep, Boolean results, edge operations, shelling, STEP/BREP round trips, IGES surfaces, unit conversion and rejected requests. `tests/kernel-client.test.js` uses a clearly labeled synthetic transport fixture solely for persistence/transform/integrity checks. `tests/advanced.browser.py` exercises the real localhost bridge through browser dialogs and downloads; it does not mock native results. The complete verification runner executes all suites. In environments that prohibit browser navigation, run native browser checks in an ordinary local or CI environment; do not treat a blocked run as a pass.

Primary implementation references:
- https://cadquery.readthedocs.io/en/latest/classreference.html
- https://occt3d.com/dev/doc/overview/html/occt_user_guides__modeling_algos.html
- https://pypi.org/project/cadquery/2.8.0/
