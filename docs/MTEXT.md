# Native rich multiline text

MTEXT is an editable native entity, not a collection of display-only TEXT objects. Its raw formatting string is authoritative and persists with paragraph width, attachment, line spacing, masks, columns and its text-local plane. Layout caches are not serialized. The editor, exchange worker and standalone build load the same parser and validation code.

## Commands and editing

The **Text** ribbon contains **MTEXT**, **MTEXTEDIT**, **MTEXTEXPLODE**, **MTEXTINFO** and **MTEXTDEMO**. Create text with the rich-source dialog, then pick its exact insertion point. Double-click an existing annotation to edit it. The dialog provides safe live vector preview, selection-wrapping format buttons, text styles, paragraph width, attachment, direction, line spacing, columns and a background mask. The property inspector also exposes position, height, width and the rich editor.

Edits are atomic and undoable. Stale dialogs reject rather than overwrite newer drawing changes. Copy/paste brings the relevant text styles, including style-name collision remapping. Block definitions retain rich entities and per-instance affine transformations. Explicit explosion produces independently editable evaluated TEXT/LINE objects and is undoable; it is not a reversible rich-text representation, and background masks are not carried into that explosion.

## Composition

Implemented formatting controls: nested brace scopes; escaped braces and backslashes; Unicode escapes; paragraph/column breaks; nonbreaking spaces; indexed and RGB colors; height/width/tracking/slant; inline font, bold and italic; underline, overline and strike-through; three fraction-stack separators; inline baseline alignment; paragraph indents, tab stops, spacing, left/center/right/justified/distributed alignment. Unknown controls and imported field codes remain in the saved raw source. Unsupported controls are reported, and proprietary field codes are displayed literally, never executed. Separately authored [Kestrel-native fields](FIELDS.md) can drive the MTEXT text through declarative references and safe formulas.

Layout uses actual loaded font measurements in the browser, word wrapping with grapheme-safe emergency breaks, CJK grapheme breaks, at-least/exact line spacing, nine attachment positions, balanced or fixed-height columns and reverse column flow. Fixed-height overflow stays visible and is reported, not discarded. Native transformations retain independent text-plane axes; nonuniform/sheared native text remains editable.

The vendored, MIT-licensed bidi-shaper level resolver implements Unicode 17.0.0 bidirectional ordering. Directional runs retain logical strings for browser outline-font shaping; stroke runs use the library's Arabic presentation-form shaping. Invisible bidi format controls are excluded from visible runs without deleting them from the source. ZWJ/ZWNJ are not indiscriminately removed. No font binaries or remotely fetched fonts are bundled. Loaded font resources remain tab-local.

Annotations are drawn in the editor's existing Canvas annotation overlay, over the WebGPU or Canvas scene. This change does not introduce a WebGPU glyph rasterizer or claim hardware GPU validation. SVG uses the same composition and transforms, with vector fraction/decoration/mask geometry. Outline SVG requires the referenced font at viewing time; SHX strokes are self-contained vector geometry.

## Interchange and preservation

Single-column conversion emits genuine **AcDbMText** records, rather than flattened TEXT. It preserves supported content, font/style references, width/height, WCS placement/direction, attachment, line spacing and mask settings. Non-ASCII content is escaped for the existing R2000 ASCII exporter; full 250-character group-3 chunks precede the terminal group-1 string. The binary DXF path uses the existing typed serializer. Foreground true color is distinct from the MTEXT background true-color group (421).

For an imported compatible single-record MTEXT, source-preserving saving can patch supported text and geometric fields while retaining unrelated records, original handles, unknown XDATA and unrelated foreground color groups. It refuses linked/embedded columns and fields that cannot safely be regenerated. Original source recovery remains byte-identical. Source extents and opaque application caches are not recomputed or certified.

**Current boundaries:** native columns are composed and saved, but linked multi-column DXF authoring is not yet implemented. Converted DXF therefore rejects multi-column or sheared/nonuniform MTEXT, requiring an explicit evaluated explosion or native project save. Top-to-bottom MTEXT is explicitly unsupported. Paragraph options outside the documented subset, proprietary/Date/Sheet Set field evaluation, full UAX #14 line breaking, advanced Asian typography, Big Fonts, font-file-specific shaping equivalence and pixel-identical Autodesk composition are not certified. A Unicode algorithm conformance pass does not prove full CAD composition equivalence. Inline outline font names still require a supplied matching resource; missing resources are reported.

## Tests and provenance

- `node tests/mtext.test.js`: parser, layout, validation, persistence, transforms, source preservation and genuine MTEXT round trips.
- `python3 tests/mtext.browser.py`: actual dialog/ribbon/editing/preview, hit testing, columns, downloads, worker import, clipboard, rollback, rendering and command contract.
- `python3 tests/mtext_interop.py`: independent ezdxf producers and consumers, with ASCII/binary audits, long Unicode strings, masks, opaque XDATA, placement and scaling.
- `node tests/unicode.test.js`: 4,811 level/order checks from a deterministic pinned corpus, recorded as one aggregate test rather than thousands of CAD-feature tests. Full local corpus mode tested 861,948 cases with zero failures; see the third-party README for reproduction.

The normal full verification runner discovers all these suites and fingerprints the bundled source, Unicode dependency and sampled conformance data. Primary specifications and dependency provenance:

- [Autodesk MTEXT DXF reference](https://help.autodesk.com/cloudhelp/2023/ENU/AutoCAD-DXF/files/GUID-5E5DB93B-F8D3-4433-ADF7-E92E250D2BAB.htm)
- [Unicode Bidirectional Algorithm](https://www.unicode.org/reports/tr9/)
- [Pinned bidi-shaper sources and licenses](../third_party/bidi-shaper/README.md)
- [ezdxf MTEXT reference](https://ezdxf.readthedocs.io/en/stable/dxfentities/mtext.html)
