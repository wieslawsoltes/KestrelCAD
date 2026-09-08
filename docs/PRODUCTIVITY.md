# Drafting productivity

The Productivity ribbon adds working selection, curve-station, quantity and layer-state workflows. The commands use the normal drawing database, native projects and atomic undo system. They do not require the optional native-solid server.

## Commands

| Command | Behavior |
| --- | --- |
| QSELECT | Filter editable objects by type, layer and literal text. Replace, add, remove or intersect the selection. Text filtering includes table cells and instance attributes. |
| COUNT | Count selected objects, or visible model-space objects when nothing is selected, grouped by type/layer/block definition. Report analytic supported-curve lengths and algebraic closed-boundary areas. |
| DIVIDE | Place internal POINT markers on equal divisions of a line, polyline, circle or circular arc. Closed curves receive one marker per division without duplicating the seam. |
| MEASURE | Place markers at fixed arc-length intervals. An exact open endpoint is included; the closing seam is not duplicated. |
| LENGTHEN | Change the total length, add/subtract a length increment, or apply a percentage to a line or circular arc, from either endpoint. The opposite endpoint stays fixed. |
| REVERSE | Reverse line/polyline/spline/conic traversal while retaining the geometric locus, rational weights and bulge orientation. |
| DATAEXTRACTION | Download CSV or JSON, or create an editable drawing TABLE containing type, layer, block, length and area. CSV includes individual attribute columns and protects textual cells against spreadsheet formula injection. |
| LAYERSTATESAVE | Save visibility, locks, color, linetype, lineweight and current layer. Overwriting a state requires an explicit choice. |
| LAYERSTATERESTORE | Restore or delete a saved state. Restoring leaves new layers intact and does not recreate deleted layers. |

## Precision and editing

LINE and straight polyline distances are evaluated in world XYZ. Circular arcs and bulged polyline segments use their analytical arc lengths, not the display tessellation. Marker blocks can align their X axis to the curve tangent. Marker creation retains the source curve and creates all markers in one transaction. Markers may use an existing configurable block definition; the block remains a real INSERT.

Station creation is bounded to 10,000 objects per operation. Invalid, degenerate or noncircular curves are rejected before any object is added. LENGTHEN does not turn an ARC into a full circle or collapse a line. Edits to actively constrained curves must use their driving dimensions or remove the conflicting graph first; endpoint references are never silently reassigned by reversing a curve.

Layer states and extraction tables persist in native projects. Undo restores prior curve coordinates, marker sets, table contents and layer appearances. Dialogs that captured a curve reject applying their result after a newer drawing edit.

## Quantity scope

Quantities operate on top-level objects. A block reference counts as one instance, not a recursive count of every member. Circle and supported closed-polyline areas include analytical bulge contributions; self-crossing boundaries have algebraic areas rather than Boolean-union areas. Unsupported quantities are empty, not fabricated zero-valued measurements. Extraction tables are snapshots and do not claim associative external spreadsheet/data-link support. JSON preserves exact scalar values; displayed table quantities use ten significant digits.

## Interchange

Point markers, static geometry and supported block references use the existing DXF exporter. Converted configurable blocks retain their evaluated static state using the existing block-variant export. The already integrated source-preserving export retains its safety checks: native-only layer-state metadata or unsupported definition edits may require an explicitly acknowledged compatibility export. This batch neither replaces the original-file archive nor claims unrestricted lossless DWG/DXF editing.

The native solid kernel remains OpenCascade, not ACIS. This batch does not add SAT/SAB compatibility, a general 3D assembly solver, proprietary dynamic-block evaluation, Big Fonts, complete MTEXT composition, or hardware-WebGPU certification.

## Verification

`node tests/productivity.test.js` checks geometry, quantities, block stations, validation, resource bounds, persistence and transactions. `python3 tests/productivity.browser.py` exercises the real standalone editor, ribbon, forms, CSV downloads, editable tables, stale-dialog rejection and undo/redo. Both suites are discovered by the existing exhaustive verification runner; merging requires the complete existing and new suites to pass on the final integrated source.
