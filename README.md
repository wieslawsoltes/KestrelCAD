# Kestrel CAD

**[Live editor (main)](https://wieslawsoltes.github.io/KestrelCAD/)** · [Production v2 review](docs/V2-REVIEW.md)

Local-first 2D drafting and 3D modeling in plain HTML, CSS and JavaScript. A custom WebGPU renderer, Canvas compatibility renderer, CAD ribbon, command line, layers, selection, grips and atomic undo/redo. No JavaScript framework, CDN, account or remote drawing service is required.

**Branch builds are not the live site.** Changes are proposed through PRs; GitHub Pages publishes `main` only after merge. This is an original Kestrel application, not an Autodesk product or a feature-complete AutoCAD replacement.

## Run locally

Python 3.10+:

```sh
python3 tools/serve.py --open
```

Open `http://localhost:8000/`. Windows users can double-click `start.bat`; macOS/Linux users can run `./start.sh`. The server binds to localhost. The standalone `Kestrel-CAD.html` is built with `python3 tools/build.py`; it can also be served by a static HTTPS host.

WebGPU is selected only if its adapter and pipelines initialize. Otherwise Canvas compatibility rendering is used. The status bar identifies the active renderer. No hardware GPU frame-rate claim has been verified.

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

## Modeling and fidelity

The baseline 3D tools create **polygon meshes**: primitives, extrude/revolve, BSP mesh union/subtract/intersect and section lines. These are not ACIS solids or exact analytic models. Mesh Boolean degeneracies and non-manifold results remain possible; check exported parts independently before manufacturing.

Native `.kcad` files retain supported editable objects and production metadata, but not undo history. DXF exchange reads ASCII/text DXF and writes AC1015/R2000. It supports a documented subset, not arbitrary lossless editing. Standard blocks/attributes and polyline hatch islands are preserved by v2; new table/leader and non-linear dimension modes export as display geometry. UCS, associations and layouts are native-only. Unsupported imported objects are reported. Keep the original drawing.

DWG requires separately installed GNU LibreDWG `dwg2dxf` / `dxf2dwg` executables and the local server. The optional bridge is not available on GitHub Pages. Neither codec is bundled; real native DWG conversion has not been verified here. The supported DXF subset remains the fidelity bottleneck even with a codec.

PNG captures the viewport. SVG supports vector output and physical layout pages. Browser fonts are approximate rather than SHX-compatible. Viewport text is a Canvas overlay, not depth-occluded 3D text.

## Tests and build

```sh
python3 -m pip install -r requirements-dev.txt
python3 -m playwright install chromium
python3 tools/verify.py --previews
```

Set `CHROMIUM_PATH` when Chromium is not at `/usr/bin/chromium`. Set `KESTREL_TEST_URL=http://localhost:8000/` to test a served application; otherwise browser tests load the standalone HTML. Tests include original core/browser/server checks, production object and UI checks, and independent ezdxf audits. Test dependencies are not application runtime dependencies.

Fresh results are written to `tests/results/`. `build-info.json` is generated after verification; the source test scripts are authoritative, not stale documentation counts. The WebGPU validation page is `tests/webgpu.html`; hardware execution is separate from Canvas browser interaction tests.

## Source layout

`src/math.js`, `geometry.js`, `model.js`, `csg.js`, `exchange.js`, `renderer.js` implement geometry, persistence and rendering. `production.js` adds persistent drafting objects. `ui.js`, `production-ui.js`, `app.js` implement the UI and editing workflows. `tools/serve.py` hosts the local editor and optional DWG codec. The application source is MIT licensed; optional third-party tools have separate licenses.
