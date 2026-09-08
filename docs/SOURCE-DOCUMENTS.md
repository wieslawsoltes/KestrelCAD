# Original drawings and source-preserving DXF

The **Exchange** ribbon separates three different operations: restore the unedited
original, save supported edits into retained DXF records, and explicitly regenerate
a compatibility drawing. These operations must not be confused with unrestricted
lossless editing of arbitrary CAD files.

## Commands

| Command | Behavior |
|---|---|
| `SOURCEINFO` | Show retained file, byte count, DXF version/encoding, record count and native editing state. |
| `SOURCEORIGINAL` | Download the exact original bytes, **without subsequent edits**. |
| `DXFSAVE` | Patch supported edits into the retained ASCII or binary DXF. Refuse unsupported changes. |
| `DXFOUT` | Use `DXFSAVE` for an imported drawing; normal compatibility export for a new native drawing. |
| `DXFEXPORT` | Regenerate supported content as ASCII DXF. Imported drawings require an explicit loss-of-content acknowledgement. |
| `DXFBINARY` | Regenerate supported content as actual binary DXF, with the same acknowledgement for imported drawings. |

Opening DXF as a separate drawing retains the entire file: sections, objects,
application metadata, proxy content, paper-space records, handles, line endings,
encoding and uninterpreted data. These records do not automatically become editable
or visible native objects. Inserting a drawing into another document transfers
supported editable content, **not** the original-source container; the UI reports
that distinction.

The immutable original and semantic import baseline are stored once in `.kcad`,
outside undo snapshots. Undo/redo retains this archive. Reopening a saved native
project restores it. `SOURCEORIGINAL` returns byte-identical source data even after
native edits. When a parser caller supplies a JavaScript string instead of a byte
buffer, the original *file* encoding is not recoverable; UTF-8 bytes of that supplied
string are retained and this provenance is recorded.

## Guarded editing

Supported one-to-one model-space edits cover LINE, POINT, CIRCLE, ARC, ELLIPSE,
straight/bulged LWPOLYLINE, control-point SPLINE and single-line TEXT. Existing entity
handles and owner references are retained. Unknown groups and protected 102 control
blocks/XDATA are copied, not interpreted as ordinary geometry. Geometry fields are
patched within their correct subclass sections. Supported object appearance,
existing-layer properties, and an existing insertion-unit header can also change.

New simple entities receive unique handles and the original model-space owner.
Deletion checks retained handle references before removing a record. All output is
prepared before download; a failed export changes neither the source archive nor
the native drawing. Native editing and DXF exporting have separate validity checks.

The exporter deliberately refuses block-definition/style/layout/constraint changes,
new or renamed layers, ambiguous or compound record mappings, unsupported native
fields, type-changing edits, unsafe referenced deletions, width/vertex-ID polylines,
source-thickness geometry, and fit-point/tangent-constrained spline regeneration.
Legacy version limits are checked rather than inserting unsupported modern fields.
A native project can still save such edits together with the untouched original;
explicit compatibility export can regenerate the supported subset.

**Unchanged opaque metadata is not recomputed.** Proprietary reactors, proxy caches
and application-specific relationships may require the originating application to
reevaluate them. Byte retention does not prove semantic equivalence of arbitrary
modified files. This is a guarded record editor, not a certified Autodesk database.

## Binary DXF and encodings

The browser/worker reads current two-byte group codes and pre-R13 one-byte codes
with extended escapes, little-endian numeric fields, 64-bit integers via BigInt,
booleans, NUL-terminated strings and length-prefixed binary chunks. It writes real
binary DXF, not text with a changed extension. Original 64-bit values outside the
JavaScript safe-integer range and embedded zero bytes are retained.

ASCII and binary archives remain in their input container when edited. Modern UTF-8
strings and supported legacy code pages are decoded for viewing; regenerated legacy
strings use DXF Unicode escapes. Unsupported encodings, truncated/invalid binary
values and malformed record streams are rejected. Limits: 64 MiB source input,
2 million pairs, 128 MiB generated output. Native archived projects allow 256 MiB;
source size plus baseline geometry can still exceed that limit and should be split.

## DWG

When the optional installed LibreDWG bridge opens a DWG, `.kcad` retains the original
DWG bytes **and** the converter's DXF output separately. `SOURCEORIGINAL` restores
the original DWG. `DXFSAVE` patches the converted DXF, not the original DWG database.
Real native DWG conversion remains unverified without an installed codec; mocked
bridge tests and synthetic signature fixtures are not codec certification. Arbitrary
lossless modified DWG export, ACIS/SAT/SAB evaluation and proxy-object editing are
not established by this feature.

## Verification and format references

`node tests/source-document.test.js` tests record preservation, edits, refusals,
encodings, memory/history provenance and binary typing. `python3 tests/source_interop.py`
uses independently produced ezdxf ASCII/binary/R12 files, tests changed geometry,
XRECORD/XDATA and handle ownership, and requires zero audit errors or repairs.
`python3 tests/source-document.browser.py` exercises actual file input, workers,
commands, downloads, acknowledgement forms and native-project reopening. The test
paces UI exports to avoid flooding the browser's automatic-download queue; file
content and exact-byte assertions remain mandatory.

Primary format references:
- [Autodesk binary DXF description](https://help.autodesk.com/cloudhelp/2023/ENU/AutoCAD-DXF/files/GUID-FC1C3C69-DBC2-49E4-893A-000D6538C0FE.htm)
- [Autodesk group-code value types](https://help.autodesk.com/cloudhelp/2019/ENU/AutoCAD-DXF/files/GUID-2553CF98-44F6-4828-82DD-FE3BC7448113.htm)
- [Autodesk numerical group-code reference](https://help.autodesk.com/cloudhelp/2024/ENU/AutoCAD-DXF/files/GUID-3F0380A5-1C15-464D-BC66-2C5F094BCFB9.htm)
