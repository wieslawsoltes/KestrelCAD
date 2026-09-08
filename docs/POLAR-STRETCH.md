# Polar stretch actions

A native configurable block can change its reach and rotation together using a `polar-stretch` action. This extends Kestrel's ordered block evaluator; it does not decode or write proprietary DWG dynamic-block action records.

## Authoring and editing

Select a configurable INSERT, run `BACTION` (Blocks → Add block action), and choose `polar-stretch`. Set the final-length expression, baseline length, rotation-angle expression, reference direction, center, rotation axis, and stretch-frame minimum/maximum. The existing `BPROPERTIES` form and inspector edit the driving parameters for each instance.

Expand **Polar stretch member modes** to choose how each target responds:

- **Use stretch frame:** stretch eligible line/polyline vertices; move insertion anchors or fully enclosed conics. The frame is in definition-local XYZ at this action stage, before this action's rotation.
- **Move whole:** apply the full reach displacement to the entire target, independent of the frame. Use this for a rigid native solid, spline, or other member that should move without changing its shape.
- **Rotate only:** rotate the member but never apply the reach displacement.

Every selected target rotates. Untargeted objects are unchanged. `moveOnly` and `rotateOnly` must be disjoint subsets of `targets`.

```json
{
  "type": "polar-stretch",
  "targets": ["arm", "tip", "pivot"],
  "length": "Reach",
  "baseLength": 100,
  "angle": "Angle",
  "multiplier": 1,
  "center": [0, 0, 0],
  "axis": [0, 0, 1],
  "direction": [1, 0, 0],
  "min": [90, -20, -1],
  "max": [120, 20, 1],
  "rotateOnly": ["pivot"],
  "moveOnly": ["tip"]
}
```

Here `Reach` is a positive length parameter, with default 100, and `Angle` is a degree-valued angle parameter, with default 0. The baseline is the original definition's reach. Angle is the change from the definition orientation, not an angle relative to the last regeneration.

The direction and rotation axis must be nonzero and perpendicular. They are normalized independently, so an axis of `[0, 2, 0]` is valid. Center and axes are independent of the camera and active UCS. The optional multiplier defaults to 1 and can be an expression, zero, or negative.

## Geometry semantics

The displacement before rotation is:

```text
delta = normalize(direction) * (evaluatedLength - baseLength) * multiplier
```

Apply the appropriate displacement to frame-selected geometry, then rotate all target geometry about the supplied center and axis. This rotates the displacement into the new ray direction. For a line from `(0,0,0)` to `(100,0,0)`, with just the far endpoint in the frame, `Reach=150` and `Angle=90` produce a line ending at `(0,150,0)`.

Each evaluation starts from the unchanged definition. Earlier actions affect the geometry presented to the stretch frame; later actions affect its result. Array descendants retain the source target identity. Per-instance INSERT transformations apply after local regeneration, including unit scaling and affine reflection.

Lines and straight polylines use vertex membership. A bulged polyline segment retains its analytic arc when both endpoints move together or both remain fixed. Moving just one endpoint of a bulged segment rejects rather than retaining an incorrect bulge. Whole conics move without changing their radii/axes. Conic/frame classification uses analytic extrema and coordinate-boundary intersections, not display tessellation; a conic surrounding the frame without entering it is not incorrectly translated.

POINT, TEXT, MTEXT and nested INSERT use their insertion anchors for frame membership. Plain meshes move when all vertices are enclosed; overlapping mesh bounds reject partial deformation conservatively. Native B-rep bodies require an explicit rigid mode when the reach changes: their display mesh is never used as proof of native-solid enclosure. Native BREP bytes and shape remain unchanged while the authoritative placement follows the action. Other entity types require Move whole or Rotate only.

The frame is a fixed axis-aligned local box, not an associative polygon or an automatic parameter grip. Changing only the angle, or a zero distance multiplier, performs rigid rotation and needs no stretch classification. Partial conic deformation, automatic native-face deformation, graphical parameter grips, and proprietary action-graph serialization are not supplied by this action.

## Persistence and interchange

Native `.kcad` retains the action, reference frame, member modes and independent instance parameters. Definition-aware clipboard transfer preserves behavior. Successful changes form one undoable transaction. Invalid expressions, impossible modes, stale dialogs and unsupported deformations reject atomically.

Standard DXF contains evaluated static BLOCK/INSERT variants and evaluated attribute text, not a recoverable dynamic evaluator. The exchange worker and editor use the same evaluator. Retain the native project as the configurable master. Source-preserving DXF export retains its existing compatibility guards.

## Verification

```sh
node tests/polar-stretch.test.js
python3 tools/build.py
python3 tests/polar-stretch.browser.py
python3 tests/polar-stretch-native.test.py
python3 tests/polar_stretch_interop.py
```

The suites include numerical geometry and rollback checks, real UI authoring/property/clipboard/download/worker workflows, actual OCCT centroid and STEP checks, and independent ezdxf audits requiring zero errors and zero repairs. All suites are discovered automatically by `tools/verify.py`. Hardware WebGPU execution and native DWG codecs remain separate validation paths.

Primary workflow references: [Autodesk polar-stretch actions](https://help.autodesk.com/cloudhelp/2023/ENU/AutoCAD-Core/files/GUID-D48A291E-3085-4B16-B969-20CBD000501B.htm) and [BACTION member selection](https://help.autodesk.com/cloudhelp/2022/ENG/AutoCAD-Core/files/GUID-98CCB318-60F6-46C9-8F90-C2B8614553C4.htm). The schema, explicit rigid-member mode, validation, and geometry algorithms here are original Kestrel implementations.
