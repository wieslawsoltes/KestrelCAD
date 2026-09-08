# Native interference and clearance

`INTERFERE` and `CLEARANCE` open **Solids → Material checks**. Select 2–32 visible top-level native solids first. With no selection, the dialog lists all visible top-level native bodies. Mesh-only entities, open sheets and mixed solid/surface compounds are not silently converted or omitted. Locked sources may be analyzed; output geometry requires an unlocked visible current layer.

Choose every unordered pair, or first-set versus second-set comparison. An object included in both sets belongs only to the first. Click **Analyze** to compute a read-only report. Changing settings invalidates the report. Up to 128 distinct pairs are accepted per query; split larger assemblies into explicit sets.

The result distinguishes:

| Status | Meaning |
|---|---|
| Interference | Native Boolean common contains positive solid volume. |
| Contact / within tolerance | No computed positive overlap and minimum distance is at or below the entered contact tolerance. This includes small positive gaps. |
| Clearance | No overlap/contact and the gap is below required clearance. |
| Separated | No overlap/contact and the gap is at least the required clearance. |

Distances and contact tolerance use current drawing units; overlap volume uses their cube. Values describe numerical OCCT B-rep geometry, not exact rational arithmetic or manufacturing certification. Minimum material distance is zero for intersecting/contained material and is **not penetration depth**. A body in a hollow solid's cavity is not overlapping its material. Contact tolerance affects classification only; it is never a fuzzy Boolean enlargement.

**Focus pair** selects the two source bodies and fits them in the viewport. **Download report** exports labeled entity IDs, units, source revision, all pair classifications, overlap volumes and minimum-distance witness coordinates. It excludes embedded BREP payloads. Multiple witnesses can exist; at most eight are returned per pair. The reported total witness count is preserved. An inner-solution witness may lie inside a solid rather than on its boundary.

With overlap generation enabled, **Retain overlap solids** adds each pair's common material as an independent native B-rep body on the current layer. Originals are untouched. The retained results support native saving, STEP exchange and subsequent native editing. **Retain gap line** adds a line between the first witness pair for a positive gap greater than contact tolerance. Both actions are single undoable transactions; neither creates a persistent measurement association. A report closed without retention adds nothing to the drawing.

## Implementation

`tools/native_analysis.py` is the stateless material-query library. `kernel.execute()` dispatches `interference` through the existing restricted, size-limited, 60-second local subprocess bridge. Sources are decoded and transformed from authoritative BREP streams. Compounds must contain only closed positive-volume solids; their material is unioned before comparison to prevent internal double-counting. An aggregate 20,000 face/edge limit and at most 64 solids per operand bound requests.

Geometry-based, tolerance-expanded `BRepBndLib.AddOptimal` boxes use `useTriangulation=False`. Separated boxes skip only the Boolean common operation. Every reported minimum gap still comes from `BRepExtrema_DistShapeShape`. `BRepAlgoAPI_Common` operates non-destructively without using contact tolerance as its fuzzy value. A failed pair aborts the complete query rather than misreporting an unknown result as separated. Display triangulation is generated only when packing explicitly requested overlap bodies (maximum 64 pairwise result bodies).

`src/native-analysis.js` validates pair plans, captures source revisions and authoritative inputs, checks complete response indices/counts/volumes/witnesses, and handles transactional output. `src/native-analysis-ui.js` supplies the ribbon and working dialogs. Switching documents, editing sources, or closing a dialog prevents an asynchronous result from mutating or repainting a newer document/dialog. All output bodies validate before the first write.

Reports are snapshots. Pairwise overlap volumes can double-count material shared by three or more inputs; do not sum them as the unique assembly interference volume. This implementation does not provide nested block/xref solid selection, surface interference, automatic collision response, contact constraints, continuous motion collision detection or ACIS/DWG compatibility. The hosted Pages editor displays saved results, but native analysis requires `requirements-kernel.txt` and `python3 tools/serve.py` locally.

## Verification

```sh
node tests/native-analysis.test.js
python3 tests/native-analysis.test.py
python3 tools/build.py
python3 tests/native-analysis.browser.py
python3 tools/verify.py --previews
```

Client tests use explicitly synthetic transport fixtures for contract/rollback testing. Python tests use actual OCCT shapes, including spheres, cylinders, cavities, compound material, reflected/nonuniform placements, retained BREP and STEP round trips. The committed browser suite uses the actual served editor and real HTTP kernel bridge. These test classes are separate; a standalone diagnostic binding is not HTTP transport verification. All conventionally named suites are discovered by the full verification runner.

Primary references: [INTERFERE workflow](https://help.autodesk.com/cloudhelp/2022/ENU/AutoCAD-Core/files/GUID-FF1ED01E-9AB5-455F-8E84-2F01C2EA3B62.htm), [OCCT distance API](https://dev.opencascade.org/doc/refman/html/class_b_rep_extrema___dist_shape_shape.html), and [CadQuery shape algorithms](https://cadquery.readthedocs.io/en/stable/_modules/cadquery/occ_impl/shapes.html). Kestrel's UI, protocol, result handling and scope are its own implementation.
