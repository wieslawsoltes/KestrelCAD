# Production drafting v2 — reconstructed and verified

## Recovery finding

The earlier conversation described a v2 package, but the package was not retained. The remote `feature/production-drafting-v2` branch contained only an import workflow, not v2 source changes. This PR reconstructs real functionality from main at `b64c9627c25899b0676ec8890506cbe39c22cf86`. It does not claim to recover missing bytes or rely on the previously claimed 113 checks.

## New working paths

`Drafting` is a new ribbon tab. Every command below is also searchable using Ctrl+K.

| Commands | Implementation |
|---|---|
| BLOCK, BINSERT, BEDIT, BCLOSE, ATTEDIT | Shared definitions, transformed references, nested blocks, separate definition editor, per-instance attributes, explode/undo; native persistence. Clipboard transfer remaps referenced definitions and style/layer dependencies. |
| DIMLINEAR, DIMRADIUS, DIMDIAMETER, DIMANGULAR, DIMORDINATE, DIMSTYLE | Actual measurement geometry and text; shared dimension style settings. Linear dimensions can reference selected line endpoints and update with edits. Missing sources are marked broken rather than silently discarded. |
| HATCHISLANDS | Pattern/solid hatch with even-odd islands, including nested islands. Selected boundaries are associated and regenerate on edits. |
| MLEADER, TABLE | Editable leaders and table cells stored as native objects. |
| STRETCH, BREAK, ALIGN | Crossing-vertex stretch for straight lines/polylines; analytic line/circle/arc break; two-point alignment in 3D, with optional scale. |
| XATTACH, XREF | Local native/DXF reference snapshots; explicit reload, unload, load, bind, detach. File data is not fetched from a remote URL. |
| UCS | Orthonormal drawing plane; plane-aware numeric input, snapping and basic creation tools. |
| LAYOUT, PLOT | Persistent millimeter paper sizes, independent clipped top-view viewports, per-viewport scales and frozen layers. Physically dimensioned SVG and browser print preview. |

Transactions include production metadata. Failed validation rolls back the document. Definition cycles, missing references, singular/projective matrices, malformed geometry, excessive hatch complexity and invalid table/layout/style data are rejected.

## Regression fixed during this implementation

An initial UI wrapper dropped the screen-coordinate argument to `acceptPoint`. Existing browser trim/extend interactions caught it. The wrapper now forwards that argument and all 51 original browser checks pass again. The old `DIMLINEAR` alias is no longer routed to aligned dimension creation.

## Interchange boundaries

The DXF writer emits real BLOCK/BLOCK_RECORD/INSERT and ATTDEF/ATTRIB records. Named shared blocks and per-instance attribute values survive a native→DXF→native round trip. Non-orthogonal block transforms cannot be represented as ordinary INSERT transforms and are explicitly expanded to geometry on export.

Polyline hatch boundary islands survive DXF exchange. Linear and aligned DIMENSION objects are supported. Other newly-created dimension modes, tables and leaders export as display geometry, **not** native AutoCAD objects. Dimension style round-trip is not complete. References become ordinary blocks in DXF; their external attachment semantics are native-only. UCS, associations and paper layout metadata are native-only in this PR. There is no lossless arbitrary DWG/DXF claim.

Block editing updates geometry, layers and dimension styles. Defining new nested blocks within an active block-edit session is not supported. Block appearance is grouped at reference level in the current renderer. AutoCAD dynamic action graphs are not implemented here.

Layouts plot world-XY/top view. They do not implement general paper-space CAD editing, rotated 3D viewports, CTB/STB, SHX metrics or hidden-line production drawings. Browser printing must use 100%/actual size without margins; print-driver scaling is outside the editor's control. Preview/edit layout data through LAYOUT; model-space geometry remains editable in the main viewport.

STRETCH does not deform arbitrary solids or partially selected conics; BREAK does not yet split splines. The UCS construction grid and some overlay previews still use world coordinates, even though supported tool results use the chosen plane. General constraint solving and true B-rep operations are in the next PR.

## Reproduce checks

```sh
python3 -m pip install -r requirements-dev.txt
python3 -m playwright install chromium
# Set CHROMIUM_PATH to the installed browser executable when not /usr/bin/chromium.
python3 tools/verify.py --previews
```

New fixtures are independently read and audited with ezdxf. The browser tests drive real dialogs, commands and file downloads with explicit fixture setup. WebGPU hardware and actual DWG conversion are not covered. No Autodesk application or licensed codec has been used to certify results.
