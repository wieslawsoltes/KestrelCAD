# Kestrel CAD

**[Launch Kestrel CAD](https://wieslawsoltes.github.io/KestrelCAD/)** · [Download the complete application](https://wieslawsoltes.github.io/KestrelCAD/Kestrel-CAD.zip) · [Standalone HTML](https://wieslawsoltes.github.io/KestrelCAD/Kestrel-CAD.html)

**A local-first 2D drafting and 3D mesh-modeling application in plain HTML, CSS, and JavaScript.**

A custom ribbon-style desktop interface, editable drawing database, command line, precision input, dark/light themes, custom WebGPU renderer, Canvas compatibility renderer, native project files, and an ASCII DXF exchange implementation. No JavaScript framework, npm install, third-party rendering engine, CDN, account, or remote drawing service is required.

This is a working implementation, not a collection of mock screens. It is also **not a feature-complete replacement for AutoCAD**. The format and modeling limitations below are important, particularly for professional drawings. Its interface uses familiar CAD workflows with original Kestrel branding and artwork; it is not an Autodesk product.

## Run online

Open **https://wieslawsoltes.github.io/KestrelCAD/**. No installation or account is required. The hosted editor keeps drawing processing in your browser; native project and DXF imports/exports work without a server. The optional DWG codec requires the local Python bridge and is not available on the GitHub Pages site.

GitHub Actions rebuilds and publishes the static site after changes to `main`. The workflow runs the dependency-free core tests, builds the standalone edition, and stages only public application assets. The complete source package and the GPU validation page are available alongside the editor.

## Start the application

Unzip the package first. A modern desktop browser and **Python 3.10 or newer** are sufficient for the recommended local launch.

**Windows:** double-click `start.bat`.

**macOS / Linux:** run `./start.sh`, or run this from the package directory:

```sh
python3 tools/serve.py --open
```

The server listens only on `127.0.0.1`; the editor opens at:

```text
http://localhost:8000/
```

Choose a different port with `python3 tools/serve.py --port 8080 --open`. Stop the server with Ctrl+C. The launchers do not install packages or converters.

**Single-file edition:** `Kestrel-CAD.html` contains the entire application, including the worker and examples. It can be opened directly for a portable preview, subject to the browser's local-file restrictions, or served from localhost/HTTPS. Localhost is recommended for WebGPU availability and consistent storage behavior. The optional DWG bridge requires `tools/serve.py`; it is not embedded in the HTML file.

The app selects WebGPU when an adapter and all pipelines initialize successfully. The status bar reports the actual active backend. It automatically uses **Canvas 2D** when WebGPU is unavailable, fails initialization, or loses its device. The compatibility renderer is substantially slower for dense 3D geometry and is not a GPU performance substitute.

## First drawing

The initial document is the fully editable **Courtyard House** architectural example. Open the mechanical **Precision Fixture** example from Insert → Example drawings or through the command palette.

Press Ctrl+N for a blank drawing. Enter these commands into the command line at the bottom:

```text
LINE 0,0 100,0 @0,80 ENTER
REC 150,0 250,80
CIRCLE 200,40 20
FIT
```

`100,50` is an absolute XY coordinate; `100,50,20` includes Z. `@25,0` is an offset from the last point. `@100<45` is a relative polar point. Enter finishes a path; `C` closes a polyline when the polyline tool is active. Escape cancels the current tool or clears selection. Circle accepts a numeric radius after its center. Rotate and scale accept a numeric angle or scale factor after the base point.

Select a closed rectangle or circle and choose **Model → Extrude** to create a mesh. Use the view controls or Shift+middle-drag to orbit. Boolean subtraction uses the selection order: select the retained body first, then add the cutting body with Shift-click.

Save with Ctrl+S to download an editable `.kcad` project. Browser autosave is convenient but is not a substitute for project files.

## Implemented features

| Area | Working implementation |
|---|---|
| Workspace | Ribbon tabs, multiple documents, layers/explorer, property inspector, command line and history, searchable command palette, context menu, view controls, dark/light themes |
| 2D creation | Lines, polylines, rectangles, polygons, circles, three-point arcs, ellipses, control-point splines, points, text, aligned dimensions, simple hatches |
| Precision | Absolute/relative XYZ input, relative polar input, grid snapping, endpoint/midpoint/center/quadrant snaps, line-intersection snaps, ortho and polar tracking |
| Selection | Click selection, additive selection, left-to-right containment window, right-to-left crossing window, groups, filters, editable grips, depth-aware mesh face picking |
| Modification | Move, copy, rotate, scale, mirror, offset, line trim/extend, two-line fillet/chamfer, rectangular/polar arrays, join/explode, match properties, delete |
| Properties | Per-entity geometry editing, color/line type/lineweight, layer assignment, text and dimension settings, mesh position and volume |
| Layers | Create/manage, current layer, visibility, locks, colors, line types, lineweights, show-all and purge-unused actions |
| 3D | Box, cylinder, cone, sphere, torus, extrusion of simple closed planar profiles, revolution around a world axis, mesh union/subtract/intersect, horizontal Z-section lines, 3D translation/rotation/uniform scale |
| Navigation | Top/bottom/front/back/left/right/isometric views, pan/orbit, cursor-centered zoom, fit, orthographic/perspective views |
| Rendering | Instanced anti-aliased WebGPU line quads, depth-tested lit triangles, 4× MSAA, wireframe/shaded/shaded-edges/x-ray styles, camera-relative vertex positions, retained GPU buffers, adaptive grid, Canvas annotation overlay |
| History | Atomic undo/redo transactions, rollback on failed edits, in-app copy/cut/paste with unit-aware insertion |
| Files | Native `.kcad` projects, supported ASCII DXF import/export, optional local DWG conversion, SVG, viewport PNG, fitted browser print sheet |
| Diagnostics | Actual backend/adapter and geometry counters, CPU frame submission time, selectable 100–100,000-line stress scene, drawing audit, import reports |

**Operation boundaries:** trim/extend edits LINE entities; explode polylines first. Fillet/chamfer operates on two planar lines, not arbitrary solid edges. Polyline offsets use mitered corners without automatic self-intersection cleanup. Splines created through the UI use control points rather than an interpolating fit-point solver. Basic drafting takes place in world XY; this is not an arbitrary-UCS sketcher. Mirroring transforms the selection in place; use Copy first to retain the original.

## File formats and fidelity

### Native `.kcad`

JSON containing editable entity geometry, layers, units, groups, drawing name and view. Native files preserve the application's own model without DXF conversion. They do **not** preserve undo history. Projects are validated on import for supported entities, finite coordinates, identifiers and mesh indices.

### DXF: local reader and writer

The application reads **ASCII/text DXF**, including applicable legacy Windows code pages and Unicode escapes. It explicitly rejects binary DXF. The writer emits **R2000 / AC1015 ASCII DXF**.

| DXF content | Treatment |
|---|---|
| LINE, POINT | Editable entities |
| LWPOLYLINE, ordinary POLYLINE | Vertices, closure, elevation/OCS, bulges where representable; 3D paths supported |
| CIRCLE, ARC, ELLIPSE | Analytical parameters, plane orientation and axes; export normalizes ellipse axes |
| SPLINE | Control points, degree, knots and positive rational weights; no general NURBS surface support |
| TEXT / MTEXT | Editable text and insertion/orientation data; browser-font approximation, not SHX/font/layout equivalence |
| Layers | Names, colors, visibility/locks and common line settings |
| BLOCK / INSERT / MINSERT | Expanded into independent editable geometry, including transforms and repeated insert spacing; block identity is not retained |
| Aligned DIMENSION | Supported native aligned dimension representation; other dimensions can become display geometry when their anonymous blocks are available |
| HATCH | Simple polyline boundaries; bulged boundaries are sampled. Multiple boundary islands and edge-loop patterns are not supported |
| 3DFACE / polyface / mesh data | Faceted editable meshes where handled by the importer |
| SOLID / TRACE | Planar face geometry |
| Attributes | Visible supported attribute text can be expanded; not a complete attribute/block-management system |
| Paper space, unsupported/custom entities | Skipped or approximated with an import report; not silently claimed to survive |

Meshes export as **3DFACE**, not ACIS `3DSOLID`. Complex dimensions, linetypes, fonts, hatches, xrefs, custom/proxy objects, dynamic blocks, constraints, materials, paper-space layouts and application-specific metadata are not preserved losslessly. Inspect the import report and compare any important drawing with its source. Always retain the original file.

### DWG: optional external native codec

There is **no bundled DWG decoder or writer** and no filename-renaming workaround. DWG operations use the following explicit local path:

```text
Open DWG: browser → localhost bridge → installed dwg2dxf → supported DXF importer
Save DWG: supported DXF exporter → localhost bridge → installed dxf2dwg → download
```

Install GNU LibreDWG separately through its official project/distribution instructions, and make its `dwg2dxf` and/or `dxf2dwg` executables available on PATH. Alternatively, give the bridge explicit executable paths before launching it:

```sh
export KESTREL_DWG2DXF=/absolute/path/to/dwg2dxf
export KESTREL_DXF2DWG=/absolute/path/to/dxf2dwg
python3 tools/serve.py --open
```

In PowerShell, use `$env:KESTREL_DWG2DXF = 'C:\path\dwg2dxf.exe'` and the equivalent `KESTREL_DXF2DWG` variable. Restart the local server after changing its environment.

Open **Manage → DWG codec** to see whether each converter is actually detected. Missing converters produce an explicit message. Reader and writer availability are independent. Codec detection does not certify compatibility with every DWG version or entity. The bridge requests R2000 output from the writer; conversion remains subject to the external codec's capabilities and the application's supported DXF subset.

**Actual native DWG conversion was not tested in the build environment because the external converters were not installed.** The bridge's HTTP behavior, command construction, missing-codec reporting, output checks and timeout handling have been tested; codec protocol tests use clearly labeled test doubles, not real DWG files. No test-double output is included as an example drawing.

### Images and printing

PNG captures the real viewport, including annotations. SVG exports vector paths and text in a top or current projection. The A3 sheet/print feature is **fit-to-page**, not a calibrated engineering-scale plotter, multi-viewport paper space, or a full hidden-line 3D drawing generator. Use DXF and a dedicated plotting workflow for controlled-scale deliverables.

## Renderer architecture and performance

The renderer is custom code, not a wrapper around a third-party 3D engine.

CPU geometry and matrices use JavaScript double precision. GPU vertex data is rebased around a camera-relative origin before conversion to Float32. Visible line segments are batched into instanced screen-width quads. Mesh triangles are batched into lit pipelines with depth testing. A frame typically submits a grid batch, a triangle batch and a line batch, as applicable. Buffers grow geometrically and are retained across camera motion; the scene is rebuilt when drawing data, selection, style or theme requires it. Rendering is requested on changes rather than running an idle animation loop. DXF parsing/export uses a worker.

Annotation glyphs, grips, cursor feedback and other transient overlays use a 2D canvas. Text is not GPU-depth-occluded. The Canvas compatibility renderer uses a full-resolution software depth/color pass for opaque shaded triangles and depth-tested line visibility. Its x-ray transparency is sorted rather than order-independent, and opaque fill edges do not have the WebGPU path's multisample antialiasing. Dense coplanar or degenerate geometry can still show artifacts.

The displayed `ms` value measures **CPU processing/submission**, not GPU execution time or frames per second. No GPU frame-rate, million-object, or production-scale performance claim has been verified. Drawing edits, selection indexing, geometry tessellation, mesh Booleans and history snapshots can remain CPU-heavy. Curve/mesh tessellation is finite; there is no adaptive surface/B-rep kernel or general topology repair.

## Known modeling and product limits

This release does not implement a parametric constraint solver, ACIS/B-rep solid kernel, NURBS surfaces, solid-edge fillets, loft/sweep surface tooling, associative dimensions/hatches, arbitrary UCS sketch planes, external references, raster references, SHX fonts, dynamic blocks, geospatial coordinate systems, collaboration, a plugin API, full paper space or certified interchange.

Mesh Booleans use a BSP polygon algorithm. Simple nondegenerate closed inputs are tested, but touching/coplanar faces, self-intersections, tiny features, poor topology or extreme scale differences can fail or create non-manifold output. Edge cleanup in the viewport is not mesh repair. Exported faceted models should be checked before manufacturing or analysis. Volume is computed from mesh triangles, not an exact analytic solid model.

Limits protect against some pathological inputs but are not capacity guarantees: 64 MiB file input; up to 200,000 native entities and 3 million native vertices; finite block expansion and Boolean limits; undo snapshots capped at 80 entries with a soft 32 MB history budget. Large drawings may need much more memory than their file size and can exhaust browser storage. DXF is not a preservation container for unsupported source data.

## Keyboard and mouse

| Action | Control |
|---|---|
| Open / Save / New | Ctrl+O / Ctrl+S / Ctrl+N |
| Undo / Redo | Ctrl+Z / Ctrl+Y |
| Select all / Delete | Ctrl+A / Delete |
| In-app copy / cut / paste | Ctrl+C / Ctrl+X / Ctrl+V |
| Command palette / Help | Ctrl+K / F1 |
| Command history | F2 |
| Object snap / Grid / Ortho / Grid snap / Polar | F3 / F7 / F8 / F9 / F10 |
| Finish / Cancel | Enter / Escape |
| Zoom / Pan | Wheel / middle-drag |
| Orbit | Shift+middle-drag, right-drag, or Orbit tool |
| Window / Crossing selection | Drag left→right / right→left |
| Add or remove from selection | Shift-click |
| Move a grip | Select an object, then drag its grip |
| Edit text | Double-click a text object |

Use Ctrl as documented on desktop browsers; platform/browser shortcuts can intercept some keys. The in-app clipboard is not an operating-system CAD clipboard. Commands operate on actual drawing entities; Ctrl+K searches the implemented command inventory.

## Verification and reproducible tests

Tests and machine-readable results are included. The build's browser runs used **Chromium 144**, offline document loading and the **Canvas compatibility renderer**, because browser navigation is administratively restricted in the build environment and WebGPU is not exposed in that loading context. No administrator settings were changed. The screenshots are actual app captures from that renderer, not generated design images.

### Run core tests

Node.js is needed only for this test suite, not for running the app:

```sh
node tests/core.test.js
```

Core checks cover geometry, camera transforms, curves, hatching, primitives, extrusion/revolution, Boolean volumes, history, validation, DXF round trips, Unicode, and both examples.

### Independent DXF interoperability checks

Python `ezdxf` is a **test-only** dependency, not shipped application code:

```sh
python3 -m pip install ezdxf
python3 tests/dxf_interop.py
node tests/core.test.js
python3 tests/dxf_interop.py
```

The independent producer builds an external fixture; the app imports it and exports its own fixtures; ezdxf checks geometry and audits the resulting files. Audits in the included successful run reported zero errors and zero fixes. This is useful interoperability evidence, not certification of arbitrary DWG/DXF files or testing in Autodesk AutoCAD.

### Browser interactions

Python Playwright and a Chromium executable are **test-only** requirements:

```sh
python3 -m pip install playwright
python3 tools/build.py
python3 tests/browser.test.py
```

The default test executable is `/usr/bin/chromium`; override it with `CHROMIUM_PATH`. To exercise a normally served app instead of offline `set_content` loading, start the server and set:

```sh
KESTREL_TEST_URL=http://localhost:8000/ python3 tests/browser.test.py
```

Browser checks mix genuine mouse/keyboard/UI interaction with scripted fixture setup and selection. They include actual native/DXF/PNG/SVG downloads and worker-based DXF import. The suite records the active backend and any uncaught JavaScript errors.

### Server checks

```sh
python3 tests/server.test.py
```

Uses only Python's standard library and a temporary localhost port. Includes clearly distinguished mocked codec-protocol checks; no real native converter is required or implied.

### Real WebGPU validation on your hardware

With the local server running, open:

```text
http://localhost:8000/tests/webgpu.html
```

Click **Run WebGPU tests**. This page uses the production shaders and pipelines, performs real GPU texture readbacks, verifies that lines/solids produce pixels, checks line depth occlusion, large-coordinate rendering, retained buffers, visual styles, themes and resize, and captures validation errors. Save the JSON report to record that machine's results.

**The GPU checks are included but have not been executed successfully on a GPU in the build environment.** An unavailable API or Canvas fallback is explicitly not counted as a pass. Their initial display is “Not run,” not a fabricated result. Use both visual inspection and this hardware validation before relying on the WebGPU path.

## Source layout

```text
index.html                 multi-file application entry
Kestrel-CAD.html            standalone bundle (generated)
src/style.css              custom responsive dark/light UI
src/ui.js                  original icons, ribbon and command registry
src/math.js                vectors, matrices, projection, camera and planar utilities
src/geometry.js            analytic curves, tessellation, primitives and transforms
src/model.js               document database, validation, history and spatial index
src/csg.js                 polygon BSP mesh Boolean implementation
src/renderer.js            WGSL, WebGPU pipelines and Canvas compatibility renderer
src/exchange.js            supported DXF reader/writer and SVG export
src/io-worker.js           worker-based drawing exchange
src/examples.js            editable architectural and mechanical examples
src/app.js                 tools, mouse/keyboard interaction, panels and file workflows
examples/                  both examples as .kcad and .dxf
previews/                  actual running-app screenshots
tools/serve.py             localhost static server and optional DWG bridge
tools/build.py             dependency-free standalone bundler
tests/                     core, browser, independent DXF, server and GPU checks
```

After changing source files, rebuild the single-file edition:

```sh
python3 tools/build.py
```

No build step is required for `index.html` itself. Runtime development objects are exposed as `window.Kestrel` (modules) and `window.kestrel` (application instance).

## Storage, privacy and security

Core editing and DXF/native exchange happen locally in the browser. No analytics, cloud account or remote upload is implemented. Autosave uses the current browser origin's local storage and can be unavailable, cleared or full. Different origins/ports have separate storage. Save portable project files regularly; native files, not browser state, are the durable backup.

The optional Python bridge binds to loopback, restricts Host/Origin, requires a custom header for conversion, uses fixed subprocess arguments without a shell, runs one conversion at a time in temporary directories, checks outputs and enforces input/output and timeout limits. It does not expose a general command execution API. Do not reconfigure it as a public conversion service.

**External native codecs are not sandboxed. Only convert trusted drawings.** HTTP checks, temporary directories and timeouts are not an OS sandbox and do not remove vulnerabilities in an external parser. The converter's license and installation remain separate from this application's MIT-licensed source. Never treat successful import, mesh volume or a clean DXF audit as engineering validation.

## Technical references

These public primary references informed the implementation and interoperability checks; no external application runtime library is bundled:

- WebGPU specification: https://www.w3.org/TR/webgpu/
- Chrome WebGPU troubleshooting / secure-context guidance: https://developer.chrome.com/docs/web-platform/webgpu/troubleshooting-tips
- GNU LibreDWG project and codec installation information: https://www.gnu.org/software/libredwg/
- LibreDWG command-line implementation: https://github.com/LibreDWG/libredwg/tree/master/programs
- ezdxf INSERT / block transform documentation: https://ezdxf.readthedocs.io/en/stable/blocks/insert.html
- ezdxf DXF text internals: https://ezdxf.readthedocs.io/en/stable/dxfinternals/entities/mtext.html
- ezdxf transform documentation: https://ezdxf.readthedocs.io/en/stable/transform.html

## License

Application source and bundled original example drawings are provided under the MIT license in `LICENSE`. Python, browsers, optional test dependencies and optional external DWG converters have their own licenses. Autodesk, AutoCAD, DWG and DXF names are referenced only to describe workflow and compatibility targets; no affiliation or endorsement is implied.
