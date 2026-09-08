# Polar configurable blocks and inverse lookup matching

These features extend the existing plain-JavaScript configurable-block evaluator. The original definition is never progressively deformed: each instance regenerates from its unchanged source geometry, then the INSERT placement is applied.

## Polar action authoring

Select an INSERT with a configurable definition and run `BACTION`, or choose **Blocks → Add block action**. Select `polar-array`, enter the item count and fill-angle expressions, specify the local center and axis, and choose the geometry/attribute targets. To retain the group's original orientation, turn off **Rotate polar items** and enter its explicit shared base point.

```json
{
  "type": "polar-array",
  "targets": ["hole", "label", "attribute:PART"],
  "count": "Count",
  "angle": "Sweep",
  "center": [0, 0, 0],
  "axis": [0, 0, 1],
  "rotateItems": false,
  "base": [50, 0, 0]
}
```

Count is an integer from 1 through 20,000, including the original item. Positive fill angles rotate by the right-hand rule around the supplied axis; negative angles reverse traversal. Magnitude must be at least 1e-9 degrees and no greater than 360. A full 360-degree turn divides by the count and omits the duplicate seam. A partial sweep divides by count minus one, including both angular endpoints. Count 1 retains only the original item. The default fill is 360 and the default axis is local +Z.

When items rotate, each source member uses the same rigid rotation around the center. When they do not, the **whole target group** translates by `rotation(base) - base`. The base is an explicit fixed coordinate at this action stage, not an inferred per-object center or a persistent geometric attachment. Its distance from the axis controls the orbit. The axis may be any nonzero 3D vector; view direction and UCS do not flatten it.

Actions remain ordered. Later moves, visibility states and other arrays act on every descendant of their targeted source IDs. Native solid members retain BREP data and transform their authoritative placement together with the display mesh. Interpolated attributes participate as visible geometry, not independent ATTDEF records in the evaluated DXF.

Array budgets are checked before allocation. Excess generated objects, nonfinite expressions, invalid axes and colliding/overlong output identifiers reject rather than produce partial geometry. Definition authoring validates input before JSON cloning, preventing NaN/Infinity from silently becoming omitted/default settings.

## Match lookup outputs to a selector

Select a configurable INSERT and run `BLOOKUPMATCH`, or choose **Blocks → Match lookup properties**. Pick the lookup table, enter its numeric/boolean output values, and apply. Exactly one row must match. Its enum selector is updated through the existing transactional parameter editor, recomputing all lookup outputs, dependent expressions, geometry and attribute templates together.

Unmatched rows and ambiguous duplicate output tuples produce explicit errors with no mutation. Forward selection of an enum label still works for such tables. This is discrete row matching, not interpolation, range evaluation or an automatic Custom state.

The browser-independent API supports partial criteria as long as they identify one row:

```js
const D = Kestrel.DynamicBlocks;
const matches = D.lookupMatches(block, 'Fastener', {HoleRadius: 4});
// Inspect all detached matching rows without mutating the block.
D.setLookupValues(drawing, insertId, 'Fastener', {HoleRadius: 4});
// Throws if there are zero or multiple matches; otherwise returns the chosen label.
```

Criteria must name declared lookup outputs with their exact numeric/boolean types. Strings are not converted into numbers. Numeric equality permits floating-point roundoff within `16 * Number.EPSILON * max(1, |a|, |b|)`; it does not use the much looser parameter value-set tolerance to collapse distinct table rows. Criteria are expressed in the definition's local units, just like the existing parameter editor.

The form uses all outputs in the selected table and replaces them when switching tables. It rejects application after a document switch or intervening edit. Locked instances cannot be changed. A successful match is one undoable parameter change and never stores overrides for read-only driven values.

## Persistence and exchange

Native `.kcad` keeps actions, definitions, lookup tables and independent overrides. Existing definition-aware clipboard transfer preserves the editable behavior; destination-unit scaling remains in the INSERT transform. Standard DXF output carries evaluated static BLOCK/INSERT geometry with interpolated text and correct circular OCS data. It does not encode the native behavior as proprietary evaluation records. Source-preserving export keeps its existing guards instead of claiming an equivalent edited action graph.

This is not complete AutoCAD dynamic-block or associative-array compatibility. It does not add native DWG evaluator records, automatic lookup grips, range/interpolated lookup values, per-item overrides, associative external path arrays or persistent geometric base-point references.

## Verification

```sh
node tests/polar-block.test.js
python3 tools/build.py
python3 tests/polar-block.browser.py
python3 tests/polar-block-native.test.py
python3 tests/polar_blocks_interop.py
```

Numerical checks cover exact positions, analytic curves, ordered actions, per-instance regeneration, identity safety, native persistence, inverse matching and rollback. Browser checks exercise the real ribbon, authoring and property forms, command alias, undo/redo, clipboard and worker/download paths. Native checks use actual OCCT BREP and STEP output, not synthetic kernel responses. Independent ezdxf audits require zero errors or automatic fixes. These suites are automatically included by `tools/verify.py`; hardware WebGPU remains a separately unverified path.

Primary workflow references: [polar arrays](https://help.autodesk.com/cloudhelp/2020/ENU/AutoCAD-Core/files/GUID-A6E74297-2CB3-4B1C-A07B-69CD08630052.htm) and [lookup actions](https://help.autodesk.com/cloudhelp/2022/ENU/AutoCAD-LT/files/GUID-AA47163A-9ECC-49FE-92DB-AB05D2691E1C.htm). The schema and evaluator here are Kestrel-native implementations, not a claim of identical proprietary serialization or UI behavior.

Polar-stretch actions are described separately in [POLAR-STRETCH.md](POLAR-STRETCH.md).
