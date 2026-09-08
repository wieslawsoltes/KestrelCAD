# CAD source preservation and binary DXF

The **Exchange** ribbon separates three different operations: download the untouched original, patch supported edits into source records, and convert the supported editable drawing. These are deliberately not described as equivalent.

## Commands

| Command | Result |
|---|---|
| `SOURCEREPORT` | Shows the original file, changed/added/removed records, and exact source-preservation blockers. |
| `SOURCEORIGINAL` | Downloads the original imported bytes. Subsequent edits are **not** included. |
| `SOURCESAVE` | Opens the fidelity chooser. Source-preserving DXF is offered only when the current changes can be represented conservatively. |
| `DXFBINARY` | Converts the supported editable geometry to a genuine binary DXF download. It does not export otherwise unsupported objects. |

Ordinary DXF export opens the same chooser for an imported drawing. New drawings retain the existing converted ASCII export workflow.

## What is retained

ASCII and binary DXF imports retain the complete original byte stream, together with a baseline of the editable view. This includes sections and records that the editor cannot display, paper-space content, dictionaries, extension data, original handles, whitespace, encoding and numeric spellings. An untouched source-preserving export is byte-identical to the input, including BOM and line endings.

Native `.kcad` saving includes the original archive and the current editable drawing. Undo and redo use private immutable archive references instead of copying a large source file into each history entry. Those internal references are rejected in externally loaded native files. Original file data is independent of changes to the editable view.

When a separately installed local DWG codec converts a DWG to a DXF view, the actual input DWG is also archived. `SOURCEORIGINAL` then downloads the DWG, while source-preserving DXF works on the converted DXF view. The codec itself is not bundled or certified by this feature. Merely retaining a DWG is not implementing a DWG database editor.

## Source-preserving changes

For a unique model-space source handle, supported single-record LINE, POINT, CIRCLE, ARC, ELLIPSE, LWPOLYLINE, SPLINE and single-line TEXT edits patch only changed ordinary group values. Unchanged source record bytes, unknown fields and XDATA remain intact. Coordinates use JavaScript double precision without the previous ten-decimal-place export rounding. Layer assignment uses existing layer names; linetype assignment must refer to an existing source definition. Color changes correctly replace ACI/true-color behavior rather than leaving a stale source color active.

Vertex/control-point counts and entity kinds must remain compatible. Unknown flag bits are retained while changing documented closed/rational/text-generation bits. Unreferenced simple records can be removed. New supported simple entities can be added to R2000-or-newer sources with a model-space BLOCK_RECORD, using unique handles and updating the handle seed. True-color changes/additions require R2004 or newer.

The following require a converted export or the originating application: entity-type conversion, compound/native-solid edits, changing curve topology, source-wide unit or layer-table changes, block/style/layout/constraint-definition changes, missing or duplicated source handles, persistent-reactor edits, and deleting a handle referenced by retained records. The source-preserving option is disabled and the reasons are shown; the original remains available.

**Preservation is not semantic regeneration.** Opaque application XDATA can depend on geometry even when it does not expose a standard reactor. Its bytes are retained, but its formulas, caches, proxy graphics or specialized behavior are not evaluated. Source header extents and application-specific caches are not recomputed. Reopen/regenerate in the originating application and inspect the result when these dependencies matter. This is not a guarantee of arbitrary lossless DWG/DXF editing.

## Binary decoding and bounds

The reader handles modern two-byte group codes and pre-R13 one-byte/extended group codes, little-endian double/int16/int32/int64 values, booleans, null-terminated strings and binary chunks. Codepage-aware strings are decoded for the editable view; source bytes remain unchanged. Converted binary output uses the same supported R2000 entity model as converted ASCII output. Unknown typed group codes, incomplete sections, malformed values and truncated binary data are rejected explicitly.

Source files are limited to 64 MiB and 3 million group tags; source-preserving output is capped at 128 MiB. Native project import allows 256 MiB to accommodate retained source archives. The existing entity, geometry and history limits still apply. Resource requirements grow with both source size and editable geometry; these limits are not large-drawing throughput benchmarks.

## Verification

`tests/source-archive.test.js` covers byte identity, record edits, flags/color/whitespace, original/native persistence, compact history, malformed input and rejected unsafe edits. `tests/source-archive.browser.py` uses the actual file chooser, worker import, fidelity dialogs and browser downloads. `tests/source_archive_interop.py` generates R12/R2000/R2018 ASCII and binary files with independent ezdxf, then audits untouched, edited and converted output. XDATA, XRECORD dictionaries, unsupported XLINE and paper-space fixtures verify retained source content. Synthetic DWG archive checks are labeled as such and are not codec tests.

The format implementation follows Autodesk's [binary DXF description](https://help.autodesk.com/cloudhelp/2023/ENU/AutoCAD-DXF/files/GUID-FC1C3C69-DBC2-49E4-893A-000D6538C0FE.htm) and [group value types](https://help.autodesk.com/cloudhelp/2019/ENU/AutoCAD-DXF/files/GUID-2553CF98-44F6-4828-82DD-FE3BC7448113.htm). The test scripts, fresh CI reports and source fingerprints define the verified scope; no hardware WebGPU or proprietary codec pass is inferred from these checks.
