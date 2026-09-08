# Associative annotations, drawing properties and linked tables

Kestrel-native fields keep annotation text connected to object measurements, drawing properties, named parameters, other fields and formulas. Their definitions live in `.kcad`; the evaluated text remains ordinary, renderable TEXT/MTEXT, leader content, table cells or block attributes. This is an original declarative evaluator, not an interpreter for proprietary DWG/DXF field codes.

## Commands and authoring

| Command | Operation |
| --- | --- |
| `FIELD` | Create an MTEXT field or edit fields on a selected annotation, table or attributed INSERT. |
| `UPDATEFIELD` | Recompute every native field in the drawing; a no-op creates no extra undo entry. |
| `FIELDINFO` | Show resolved values and errors without changing drawing content. |
| `FIELDREMOVE` | Freeze all fields on selected hosts to their current cached text; undo restores the definitions. |
| `DWGPROPS` | Edit drawing name, Title, Subject, Author, Keywords, Comments and typed custom properties. |
| `FIELDTABLE` | Create a linked schedule for the selected source identities. |
| `DATAEXTRACTION` | Existing CSV/JSON/snapshot output plus a linked-field table option. |

The Text ribbon has an **Associative annotations** group. Select a curve, use **Insert or edit field**, select its property, choose precision/output units and an insertion point, then create the field. New annotations use editable text height and paragraph width, not an arbitrary model-scale default. Positions use the current UCS; coordinate-valued source properties are world XYZ.

Selecting TEXT, MTEXT, LEADER, TABLE or a block reference with attributes edits that host instead of creating a second annotation. Choose an existing binding to load its settings or enter a new target. Table targets are zero-based `cell:row:column`; block targets are `attribute:TAG`. Changing the target adds or replaces that target; it does not delete other bindings. Double-click text editing opens the field template for a field-controlled annotation.

The preview is read-only and uses literal DOM text, never injected HTML. Each opened editor owns its own event listeners. A stale dialog cannot overwrite a newer drawing edit or a different active document. Normal edits to a controlled text value are rejected with a clear instruction to edit the field or freeze it first. Styling, placement, source geometry and unconstrained cells remain editable.

## References and numeric semantics

A single source uses `{{Value}}`. Multiple named sources use their names; an optional formula produces `{{Result}}`. Example definition on a text entity:

```json
{
  "version": 1,
  "target": "text",
  "template": "Length {{Length}} cm; total {{Result}}",
  "sources": [
    {"name": "Length", "kind": "object", "entity": "partLength", "property": "length", "units": "cm"},
    {"name": "Rate", "kind": "literal", "value": 2.5}
  ],
  "expression": "Length * Rate",
  "precision": 3,
  "trimZeros": false
}
```

Use actual stable entity IDs from the drawing, not the example ID. The formula/multiple-source mode exposes this source-descriptor array and the safe mathematical expression. Formulas use the existing Kestrel expression grammar, not JavaScript. Values stay numeric at full internal precision until formatting. Decimal places range from 0 to 12; trailing-zero suppression is optional. Formula variables must be numbers, not implicitly parsed display strings. Boolean literals display `true`/`false`.

Supported sources:

- **Object properties:** ID, type, layer name, block name, length, enclosed area, circular radius/diameter, world insertion/center/start XYZ, text, named attribute, or a table cell. Use `tag` for attributes, and zero-based `row`/`column` for cells. Length is analytic for lines, circles, circular arcs and bulged polylines. Enclosed area includes full circles/ellipses and supported closed planar polylines. Open paths, spline/ellipse lengths, plain-mesh areas and native-solid mass properties are not approximated from display triangles; incompatible requests are unresolved.
- **Drawing metadata:** `{"kind":"drawing","property":"name"}`, `units`, or `entityCount`. The count includes all top-level objects, including annotations, not recursively expanded block members.
- **Custom properties:** `{"kind":"property","key":"Title"}`. Names are case-sensitive for reference resolution and must be unique ignoring case. Values are strings, numbers or booleans, not arbitrary objects. This metadata is not filesystem metadata.
- **Named parameters:** `{"kind":"parameter","domain":"sketch","parameter":"Width"}` or domain `spatial`. Values follow their existing solver parameter definitions, without additional inferred dimensional analysis.
- **Literal values:** `{"kind":"literal","value":12.5}` or a string/boolean.
- **Other fields:** `{"kind":"field","entity":"labelId","target":"text"}` or `cell:r:c`/`attribute:TAG`. A formula result, or the sole source of a simple field, is available as its raw numeric value. A multiple-source text template without a result is a string. Reading an object's text/cell/attribute instead returns its formatted display value.
- **Fixed-set aggregates:** `{"kind":"aggregate","entities":["a","b"],"property":"length","method":"sum"}`. Methods are `count`, `sum`, `min`, `max` and `average`; dimensional properties are `length` and `area`. Count requires all identities to exist but not to support a measurement. Other methods require every source to support the property: missing members are not silently skipped.

Every descriptor also needs a unique valid `name`. `Result` is reserved for the formula result. Unknown template variables, duplicate variables, invalid identities and cycles reject atomically. Formula domain errors introduced by later source edits become visible unresolved results.

Explicit `units` are supported for dimensional object/aggregate measurements; area uses the square of the conversion factor. Without them the value follows current drawing units. A physical-unit field in a unitless drawing is unresolved; no physical scale is invented. Default FIELDTABLE dimensional headers pin their output units so changing drawing units cannot leave a mislabeled column. Formulas have no currency, locale, date or implicit unit type system.

## Update, safety and history

Fields are evaluated when loading native drawings and after each successful document transaction, following constraint solving and existing native associations. Derived values update in the same undo/redo step as their sources. A converted DXF export refreshes a private drawing copy even if supplied serialized cache values are stale. It does not change the caller's drawing.

Deleted sources, unavailable properties, missing custom/named parameters and runtime arithmetic errors display **`####`**. `FIELDINFO` explains each unresolved target. Undoing the source change restores both its geometry and its field results. Automatic cache refresh can update a locked annotation's derived text; authoring or freezing a locked host is disallowed.

Freezing a field keeps its displayed text, not its numeric binding. Numeric field-to-field dependents therefore become unresolved if their referenced binding is removed. Source-object text references can still read the remaining static string. A selected linked table can be frozen into an ordinary fully editable table.

MTEXT templates may contain supported rich-text controls. Substituted values escape backslashes, braces and percent controls so source strings cannot inject formatting. Browser UI previews and reports use escaped/literal text. Existing non-MTEXT host conventions and native dynamic-attribute `${Parameter}` interpolation still apply; field output is not a universal escape layer for every text host.

The evaluator is bounded: 4,096 bindings per drawing, 2,048 per host, 32 variables per field, dependency depth 32, 1,000 aggregate source identities, 128 custom properties, two million total template/output characters and an evaluation-step budget. These are resource guards, not throughput claims.

## Clipboard and block boundaries

Same-document geometry COPY remaps references to copied sources and retains valid references to uncopied sources in that document. Cross-document clipboard transfer remaps a complete copied object/field dependency set. It freezes bindings that need uncopied sources or source-document metadata/parameters, with a visible operation warning; partial numeric chains freeze transitively. It never accidentally binds an external source ID to an unrelated object in the destination drawing.

This implementation resolves top-level entity IDs, not nested block member paths. INSERT attribute hosts are supported, including ordinary native dynamic-attribute source interpolation. Field-bearing objects cannot be placed into a shared block definition until their fields are frozen: definition-local IDs and instance-dependent field contexts are not falsely treated as global references. DWG dynamic-block field graphs are not supplied.

## Linked tables and interchange

FIELDTABLE creates a fixed selection schedule with one bound cell per source/column. It supports 1–250 distinct sources and 1–8 columns; source changes update in place without reordering rows or destroying row height, column width, text style or manually unbound headings. Missing/incompatible cells show `####`; new drawing objects are not appended automatically. Column JSON accepts `label`, `property`, optional `units`, `tag`, `row` and `column`. Formulas can be attached to any table cell via FIELD.

Native save/reopen keeps definitions, metadata and stable links. Normal ASCII/binary DXF contains the evaluated static TEXT, MTEXT, INSERT/ATTRIB and table graphics, not native fields or proprietary ACAD FIELD objects. Kestrel tables flatten to ordinary graphics in this exporter rather than pretending to be fully linked external TABLE records. Reimported standard DXF is static. Keep `.kcad` as the associative master. Source-preserving export retains its existing compatibility guards; this feature does not establish unrestricted DWG editing or original-field-graph regeneration.

This is not DXE/DXEX file compatibility, external spreadsheet/database DATALINK, automatic model-set extraction, Date/Sheet Set fields, FIELDEVAL event-bitmask compatibility, or an interpreter for imported `%<...>%` codes. Those imported codes remain literal and are never executed as native formulas.

## Reproducible verification

```sh
node tests/fields.test.js
python3 tools/build.py
python3 tests/fields.browser.py
python3 tests/fields_interop.py
python3 tools/verify.py --previews
```

The core suite checks analytic geometry, units, formulas, dependency graphs, validation, history, persistence and static output. The browser suite uses real controls, renderer composition, clipboard, save/download and exchange worker paths. The independent ezdxf suite requires zero audit errors and zero repairs for both ASCII and binary field output, including the actual browser-worker fixture. All conventionally named suites are included automatically by the full verifier. Hardware WebGPU and native DWG-codec verification remain distinct paths.

Primary workflow references: [FIELD](https://help.autodesk.com/cloudhelp/2022/ENU/AutoCAD-Core/files/GUID-742C92C3-1284-4722-B650-C46F9191C701.htm), [UPDATEFIELD](https://help.autodesk.com/cloudhelp/2026/ENU/AutoCAD-Core/files/GUID-2B47D62E-19D0-4CA5-9AAC-1946132D2F62.htm), and [attribute extraction](https://help.autodesk.com/cloudhelp/2026/ENU/AutoCAD-Core/files/GUID-BA68DD22-A3CD-4538-90A9-6101C33BC963.htm). Command names identify familiar workflows; the schema, automatic update policy and supported behavior described here are Kestrel-native, not a claim of binary or semantic parity.
