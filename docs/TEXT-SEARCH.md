# Find and replace annotation text

Use **Text → Find / replace text**, `FIND`, `REPLACE`, `FINDTEXT`, or Ctrl/Cmd+F while the drawing viewport has focus. Text-input controls keep their normal shortcut behavior.

Find scans visible TEXT, MTEXT, leader text, explicit dimension text overrides, TABLE cells and top-level INSERT attributes. Optional settings restrict results to the original selection, a specific annotation type, exact case or whole Unicode words. Locked and hidden content can be included for discovery but is never made editable by the search command. Search does not modify shared block definitions, nested block/xref content, names, URLs, dimension-generated measurement labels or drawing metadata.

The query is literal text, not a regular expression or wildcard program. Punctuation and replacement strings such as `$&` have no special expansion. Case-insensitive matching follows JavaScript Unicode case folding; whole-word boundaries include letters, numbers, combining marks and underscores. Searching follows stored logical text order, including right-to-left text, rather than screen glyph order. Normalization-equivalent spellings and locale-specific linguistic matching are not inferred.

## Results and transactions

Find all lists contextual previews with highlighted matches, object identifiers, target addresses, layers and read-only reasons. The result table is paginated in groups of 100. Click a result or use Previous/Next to select and zoom to its source object. Select results selects the distinct matching objects. Navigation does not alter the original selection used for a selection-only search.

Replace current changes one occurrence. Replace all editable changes all eligible occurrences in one native transaction, reports skipped read-only targets and refreshes the result list. Undo/redo includes dependent field regeneration. Editing an attribute creates or changes its instance override without altering the shared default.

Search previews are immutable and tied to their actual document, revision and source text. Changing a search option invalidates the preview. Changing the drawing or source text before replacement requires another search. Field-bound text, table cells and attributes are protected; use FIELD or FIELDREMOVE first. Configurable block attributes are also read-only because their parameter template is authoritative.

## MTEXT fidelity

MTEXT queries match visible content, not hidden font names or formatting instructions. Matching may cross formatting runs. Replacements modify mapped source glyph ranges while retaining surrounding color, font, size, decoration and scope commands. New content inherits the formatting at its first replaced glyph. Inserted braces, backslashes and percent sequences are escaped; replacement text cannot become formatting, HTML or a field program. A newline in replacement content becomes a paragraph break.

Unicode escapes, normal paragraphs, explicit column breaks, tabs and nonbreaking spaces participate in matching. A full stacked fraction can be replaced as one unit; partial fraction matches are searchable but read-only. Unknown control fragments and literal proprietary field-code expressions are treated as indivisible tokens. Operations that would reinterpret formerly separate characters as a new MTEXT command reject atomically, rather than silently change unrelated visible text. Plain TEXT and plain table/attribute values are matched as their stored native display strings.

This preserves supported source formatting; it does not supply vertical MTEXT, missing fonts, glyph-level replacement in shaped ligatures, proprietary field evaluation or complete application-specific text equivalence. The MTEXT module also corrects an escaping bug: percent signs decoded from Unicode literals are no longer reinterpreted as `%%d`, `%%p` or `%%c` controls.

## Limits and testing

Queries are limited to 256 characters, replacement input to 10,000, scanned text to 5,000,000 and results to 10,000. Truncated result sets cannot use Replace all: narrow the scope first. Token spans use binary search; replacement assembles source chunks once instead of repeatedly rewriting the entire string per glyph. Result sizes are checked before assembling an oversized annotation. Original geometry, native BREP data and field definitions are not rewritten by search.

```sh
node tests/text-search.test.js
python3 tools/build.py
python3 tests/text-search.browser.py
python3 tests/text_search_interop.py
```

The runner discovers the suites automatically. They cover Unicode matching, source mapping, real dialog/navigation/editing workflows, protected targets, undo/redo, native downloads and independent ASCII/binary DXF audits with zero repairs. Standard DXF stores the replaced annotation content; it does not gain new behavior metadata from this operation.

Primary workflow reference: [FIND](https://help.autodesk.com/cloudhelp/2020/ENU/AutoCAD-Core/files/GUID-03A48719-9C75-4BBB-BFE9-4692BE5A591F.htm). This module implements Kestrel's native annotation semantics and documented supported scope.

For a restricted offline diagnostic, set `KESTREL_TEST_MODE=dom` before the new browser suite. This loads the built editor into an empty browser DOM and records that mode; it does not verify file navigation or HTTP hosting. Default CI behavior still uses real file navigation. `KESTREL_TEST_URL` takes precedence to test a served application.
