# Kestrel CAD

**[Live editor (main)](https://wieslawsoltes.github.io/KestrelCAD/)** · [Production v2 review](docs/V2-REVIEW.md)

Local-first 2D drafting and 3D modeling in plain HTML, CSS and JavaScript. A custom WebGPU renderer, Canvas compatibility renderer, CAD ribbon, command line, layers, selection, grips and atomic undo/redo. No JavaScript framework, CDN, account or remote drawing service is required.

**Branch builds are not the live site.** Changes are proposed through PRs; GitHub Pages publishes `main` only after merge. This is an original Kestrel application, not an Autodesk product or a feature-complete AutoCAD replacement.

## Native quantity annotations

FIELD now binds validated native-body volume and surface-area values, with cubed/squared unit conversion, live source updates and undo. FIELDTABLE selects quantity columns for native solid selections. Nonuniform surface-area transforms explicitly require native recomputation rather than using display triangles. [Native quantity semantics](docs/FIELDS.md#native-solid-quantities).

## Annotation search and replacement

`FIND`, `REPLACE`, and Ctrl/Cmd+F search visible annotation content, preserve rich MTEXT controls during replacement, protect linked fields and locked objects, and group changes with their derived updates into a single undo step. [Scopes, Unicode behavior and safety boundaries](docs/TEXT-SEARCH.md).

## Editable native edges and section curves

`XEDGES` and `SECTIONCURVES` create editable analytic lines, conics and rational splines from the actual native B-rep, with the source retained and one-step undo. The native profile tools also accept clamped rational spline profiles and open spline sweep paths. DXF knot tolerances and browser spline endpoint evaluation preserve small knot spans. [Native curve workflows and boundaries](docs/NATIVE-CURVES.md).

## Native interference and clearance

`INTERFERE` / `CLEARANCE` compare real native solid material in one or two sets. Reports include overlap volume, minimum gaps and closest points; retain independent BREP overlap solids or gap lines with undo, without modifying sources. Available in **Solids → Material checks** using the optional local kernel. [Usage and numerical boundaries](docs/NATIVE-ANALYSIS.md).

## Polar stretch for configurable blocks

`BACTION` now authors `polar-stretch` actions: coordinated reach and angle changes, frame-based vertex stretching, explicit whole-member movement and rotate-only targets. Native solids retain authoritative BREP and update only their placement. Definitions, per-instance overrides, undo/redo, clipboard and evaluated DXF stay integrated. [Geometry semantics and limitations](docs/POLAR-STRETCH.md).

## Associative annotations and linked schedules

`FIELD` binds TEXT/MTEXT, leaders, table cells and INSERT attributes to analytic measurements, drawing/custom properties, named parameters, aggregates and safe formulas. Source edits update their labels in the same undo step; missing references show diagnostics rather than stale quantities. `DWGPROPS`, `FIELDTABLE` and the linked `DATAEXTRACTION` output support editable metadata and fixed-selection schedules. Native save, clipboard remapping, MTEXT composition and static ASCII/binary DXF remain integrated. [Field authoring, schema and boundaries](docs/FIELDS.md).

## Run locally

Python 3.10+:

```sh
python3 tools/serve.py --open
```

Open `http://localhost:8000/`. Windows users can double-click `start.bat`; macOS/Linux users can run `./start.sh`. The server binds to localhost. The standalone `Kestrel-CAD.html` is built with `python3 tools/build.py`; it can also be served by a static HTTPS host.

WebGPU is selected only if its adapter and pipelines initialize. Otherwise Canvas compatibility rendering is used. The status bar identifies the active renderer. No hardware GPU frame-rate claim has been verified.

## Rich multiline annotations

Use **MTEXT** to create a native rich annotation, **MTEXTEDIT** or double-click to edit, and **MTEXTDEMO** for the working multilingual example. Raw formatting, fractions, paragraphs, masks, native columns and bidirectional runs persist through project saves and undo. Single-column DXF remains genuine MTEXT; unsafe converted column/shear exports reject explicitly. See [MTEXT commands and boundaries](docs/MTEXT.md).

## Everyday drafting

The original editor supports lines, polylines, rectangles, polygons, circles, arcs, ellipses, control-point splines, text, aligned dimensions and hatches. Modify with move/copy/rotate/scale/mirror/offset, line trim/extend, two-line fillet/chamfer, arrays, join/explode, groups and property editing. There are editable architectural and mechanical examples.

```text
LINE 0,0 100,0 @0,80 ENTER
RECTANGLE 150,0 250,80
CIRCLE 200,40 20
FIT
```

Ctrl+N/O/S creates/opens/saves a project. Ctrl+Z/Y undoes/redoes. Ctrl+K searches commands. Enter finishes a path; Escape cancels. Wheel zooms, middle-drag pans, Shift+middle-drag orbits. Left-to-right selection contains; right-to-left crosses. F3/F7/F8/F9/F10 toggle object snapping, grid, ortho, grid snapping and polar tracking.

## Production drafting v2

Use the **Drafting** ribbon tab for shared blocks and attributes, additional dimension modes/styles, associative hatch islands, leaders, editable tables, stretch/break/align, local reference snapshots, UCS, layouts and scaled output. Native project version 2 persists this metadata and reads version 1 projects.

Create a block from selected geometry with BLOCK, insert instances with BINSERT, edit the shared geometry with BEDIT and save it with BCLOSE. ATTEDIT edits attribute definitions and per-instance values. Copy/paste across drawing tabs brings referenced definitions, layers and dimension styles with it.

DIMLINEAR measures projected X/Y distance rather than aligned length. Selected line endpoints can be associated with the dimension. HATCHISLANDS uses selected closed boundaries and even-odd fill; nested boundaries create holes and islands. TABLE cells and leader text are editable.

LAYOUT stores paper dimensions in millimeters and viewport scale denominators. PLOT downloads an SVG with physical page dimensions or opens a print preview. This is top-view output, not complete paper-space CAD editing. Browser print settings must use actual size/100% scale. See the [review](docs/V2-REVIEW.md) for command-by-command boundaries and known gaps.

## Parametric sketching

The **Parametric** ribbon adds named expressions and maintained planar geometric/dimensional constraints. `PARAMDEMO` creates a fully constrained rectangle: edit `Width` in **Parameters**, and `Height = Width * 0.6` follows. Constraint bars show the stored relationships; `SHOWCONSTRAINTS` toggles them.

`GEOMCONSTRAINT` supports horizontal/vertical, coincident, signed X/Y and true distance, fixed point/entity, parallel/perpendicular/collinear, equal length/radius, concentric, radius/diameter, signed angle, tangent, point-on-line/circle, midpoint and symmetry. Use `CONSTRAINTS` to edit, suppress or delete equations, `PARAMETERS` for dependent expressions, `SOLVE` for numerical rank/remaining degrees of freedom, and `CONSTRAINTMODE` to suspend or re-enable solving. Edits solve atomically and roll back on nonconvergence. Ordinary undo, native save/load, unit conversion and compatible clipboard transfers retain the system.

This is a bounded **planar nonlinear solver**, not a 3D assembly or general NURBS constraint engine. One saved plane per drawing; lines, straight polylines, points, circles and arcs; 160 free scalar variables and 256 constraint records. Numerical rank is local, not a global proof. Parameter length units remain explicit during physical unit conversion. Equations persist in `.kcad`; ordinary DXF exchange contains evaluated geometry, not the native constraint graph. See [sketch constraints](docs/PARAMETRIC.md).

## Configurable blocks

The **Blocks** ribbon adds independent typed instance parameters, safe derived expressions, lookup tables, visibility states, flip, move/stretch/rotate/scale and rectangular-array actions. `DYNAMICDEMO` opens two configurable fabrication plates; select one and use the inspector or `BPROPERTIES`. `BRESET` restores defaults, `BDEFINE` edits the shared behavior and `BACTION` adds an action. Changes participate in undo, native persistence and definition-aware clipboard transfer.

Block members now render using their own layer/color/line properties, with nested layer visibility and ByBlock inheritance. DXF exports the evaluated appearance as static standard block variants, **not** proprietary AutoCAD dynamic-block actions. Advanced behavior authoring uses validated JSON; no custom graphical parameter grips are implemented. See [configurable block workflows and limits](docs/DYNAMIC-BLOCKS.md).

## Native B-rep modeling

The **Solids** ribbon adds an optional local **OpenCascade** kernel through CadQuery. It is not ACIS and does not read/write SAT or SAB. Install the pinned optional engine in a Python 3.11+ environment:

```sh
python3 -m pip install -r requirements-kernel.txt
python3 tools/serve.py --open
```

Native box, cylinder, cone, sphere, torus, extrude (including inner wires), revolve, loft, sweep, union/subtract/intersect, solid-edge fillet/chamfer, shell, section, affine transformation, and STEP/IGES/BREP exchange operate on real B-rep topology. Analytic curves/surfaces are retained separately from the display triangulation. Invalid results are rejected before committing an undoable drawing change. Existing approximate meshes are **not** silently upgraded to exact solids.

Projects retain native BREP bytes and transformations; the display mesh remains viewable on GitHub Pages without installing the engine. Native computation, inspection, and exchange require the local server. SOLIDINFO reports native topology and mass properties. Edge/face operations use numerical indices from the **current** topology; there is no persistent topological naming across topology-changing features. SOLIDDETACH explicitly converts a native object to a plain editable mesh; undo restores it.

STEP/IGES exchange uses millimeters with explicit drawing-unit conversion. IGES may import as surfaces rather than sewn solids. STL is explicitly tessellated. Native interoperability uses OCCT numerical tolerances, not symbolic arithmetic or a guarantee for arbitrary industrial files. See [native modeling details](docs/NATIVE-SOLIDS.md).

## Modeling and fidelity

The baseline 3D tools create **polygon meshes**: primitives, extrude/revolve, BSP mesh union/subtract/intersect and section lines. These are not ACIS solids or exact analytic models. Mesh Boolean degeneracies and non-manifold results remain possible; check exported parts independently before manufacturing.

Native `.kcad` files retain supported editable objects and production metadata, but not undo history. DXF exchange reads ASCII and binary DXF; compatibility export writes the supported AC1015/R2000 subset. Imported originals can instead be saved through the guarded source-record editor described below. It supports a documented subset, not arbitrary lossless editing. Standard blocks/attributes and polyline hatch islands are preserved by v2; new table/leader and non-linear dimension modes export as display geometry. UCS, associations and layouts are native-only. Unsupported imported objects are reported. Keep the original drawing.

DWG requires separately installed GNU LibreDWG `dwg2dxf` / `dxf2dwg` executables and the local server. The optional bridge is not available on GitHub Pages. Neither codec is bundled; real native DWG conversion has not been verified here. The supported DXF subset remains the fidelity bottleneck even with a codec.

PNG captures the viewport. SVG supports vector output and physical layout pages. User-provided supported SHX/SHP fonts render as stroke geometry; outline fonts use browser text shaping. Missing dependencies are reported. Outline viewport text remains a Canvas overlay, not depth-occluded 3D text.

## Tests and build

```sh
python3 -m pip install -r requirements-dev.txt -r requirements-kernel.txt
python3 -m playwright install chromium
python3 tools/verify.py --previews
```

Set `CHROMIUM_PATH` when Chromium is not at `/usr/bin/chromium`. Set `KESTREL_TEST_URL=http://localhost:8000/` to test a served application; otherwise browser tests load the standalone HTML. Tests include original core/browser/server checks, production object and UI checks, and independent ezdxf audits. Playwright is test-only. CadQuery is an optional local modeling dependency; it is never downloaded by the running browser. The native browser suite exercises the actual localhost worker and requires normal localhost navigation.

Fresh results are written to `tests/results/`. `build-info.json` is generated after verification; the source test scripts are authoritative, not stale documentation counts. The WebGPU validation page is `tests/webgpu.html`; hardware execution is separate from Canvas browser interaction tests.

## Source layout

`src/math.js`, `geometry.js`, `model.js`, `csg.js`, `exchange.js`, `renderer.js` implement geometry, persistence and rendering. `production.js` adds persistent drafting objects. `ui.js`, `production-ui.js`, `app.js` implement the UI and editing workflows. `tools/serve.py` hosts the local editor and optional DWG codec. The application source is MIT licensed; optional third-party tools have separate licenses.

## Text styles and user-provided fonts

The Text ribbon provides STYLE, FONTLOAD, FONTREPORT and TEXTSTYLE. Load your own
SHX/SHP stroke fonts or browser-supported outline fonts without uploading them.
Named style definitions, typography overrides, clipboard transfer and supported
DXF STYLE/TEXT records are preserved. SHX glyph strokes are real drawing geometry
and self-contained SVG paths; missing fonts/glyphs are reported. Font files are not
bundled or included in project downloads. See [font workflows and fidelity limits](docs/FONTS.md).

## Original-file retention and binary DXF

The Exchange ribbon provides `SOURCEORIGINAL`, `SOURCEINFO`, `DXFSAVE`,
`DXFEXPORT` and `DXFBINARY`. Opening a DXF preserves its entire original file,
including unknown records, alongside editable supported geometry in the native
project. Guarded DXF saves patch supported edits while retaining other records;
unsupported changes refuse rather than silently discard content. Compatibility
export is explicitly acknowledged for imported drawings. Binary DXF uses real
typed records, including legacy group codes and exact 64-bit metadata values.
Original DWG bytes and converter DXF are retained separately when the optional
codec is available; this is not unrestricted lossless DWG editing.
See [source fidelity, commands and supported edit boundaries](docs/SOURCE-DOCUMENTS.md).


## Free-space 3D constraints and assembly mates

The **Assembly** ribbon adds world-XYZ geometric and dimensional constraints for points,
lines and straight polylines, and rigid poses for meshes, retained native B-rep bodies
and block references. `3DASSEMBLY` opens a parameter-driven lift example. `3DPARAMETERS`,
`3DCONSTRAINTS` and `3DDOF` edit expressions, manage relationships and report local freedoms.
Hinge, slider, coaxial, plane and fastened mates coexist with the planar solver on disjoint
geometry. Failed solves roll back atomically. Native project persistence, unit conversion
and complete-selection clipboard transfer retain the graph. This is a bounded numerical
solver, not general deformable-solid/contact or proprietary DWG constraint compatibility.
See [spatial constraint authoring, numerical limits and tests](docs/SPATIAL-CONSTRAINTS.md).


## Planar ACIS exchange

`ACISIN`, `ACISOUT` and `SOLIDDXF` translate native planar B-reps with straight
edges, holes and void shells using the local worker. SAT 700, SAB 21800 and actual
ACIS-backed DXF solids are supported without manufacturing triangle solids.
Curved/unknown geometry rejects. These commands exchange selected geometry, not
lossless ACIS application metadata or a complete drawing. Original SAT/SAB files
remain separate. Install the updated `requirements-kernel.txt`.
See [commands, units, topology checks and compatibility boundaries](docs/ACIS-EXCHANGE.md).

## Joint limits and drives

**Assembly → Joint limits / drive** (`JOINTLIMITS`, `DRIVEJOINT`) adds minimum/maximum
slider travel and signed hinge angles, optional position drivers, named expressions,
transactional rollback, and separate unilateral-stop diagnostics. Native projects,
undo/redo and complete-selection clipboard retain settings.
See [joint travel and its numerical limits](docs/JOINT-LIMITS.md).

## Polar configurable blocks and lookup matching

The **Blocks** ribbon's `BACTION` dialog includes parameter-driven polar arrays
about arbitrary 3D axes, with full/partial clockwise or counterclockwise sweeps
and optional nonrotating copies. `BLOOKUPMATCH` selects the unique lookup-table
row matching numeric and boolean output properties; ambiguity and unmatched
values reject atomically. Native projects retain the behavior; DXF carries
evaluated static variants. See [polar blocks and lookup matching](docs/POLAR-BLOCKS.md).
