# Joint travel limits and position drivers

`JOINTLIMITS`, `DRIVEJOINT`, or `JOINTS` opens **Assembly → Joint limits / drive**.
Create a hinge or slider mate first. The form edits all such mates in one transaction.
Minimum and maximum accept safe named expressions from `3DPARAMETERS`; either end
may be blank. Disable a limit or driver to retain its expression without enforcing it.

## Coordinate convention

A slider measures **A minus B along B's axis**, in the spatial system's saved
parameter units. A hinge measures the signed rotation of A's transverse X direction
relative to B's, around B's positive axis. Axis alignment and coincident hinge origins
remain enforced by the underlying mate. The two frame axes must be independent.
Limits/drivers require rigid body or world datums; points and flexible line segments
are not substituted for rigid mating frames.

Hinge intervals and drives must be strictly inside **(-180, 180) degrees**, with
minimum no greater than maximum. Wrapped intervals and multi-turn tracking are
explicitly rejected. This avoids silently confusing an angle across the principal
branch seam. Nonlinear solving remains local and may fail for singular or conflicting
configurations; failure is not a proof of global impossibility.

## Behavior

Without a driver, a joint inside its interval stays free. Crossing a bound solves
back into the interval; the rigid body is not deformed. A driver adds a position
equation; an out-of-range driven value rejects the complete edit. Equal bounds lock
one coordinate. Independent disabled settings survive native save/load and undo.
Changing parameters, normal transformations, and complete-selection clipboard
transfers use the same solver and validation. A reflected clipboard reverses signed
hinge rotation and exchanges/negates its stops. Slider expressions follow physical
unit conversion; hinge degrees do not rescale.

Native BREP bytes remain unchanged during movement, with the pose composed through
the existing native integrity path. STEP export uses the solved native pose. This
feature is browser-only JavaScript; native BREP operations still require the optional
local kernel.

## Diagnostics and algorithm

The damped least-squares solver uses a fixed inequality active set while computing
finite-difference derivatives, then evaluates actual inequalities for trial steps.
An interior joint is not pulled to a rest position. `3DDOF` reports **bilateral**
equation rank and degrees of freedom, separately from unilateral bounds. A stop may
block outward velocity but permit inward velocity; it does not count as a permanent
bilateral lock. Equal bounds are represented as an equality. Reports list joint
coordinates, units, enabled/driven state, and whether each stop is active.

No collision/contact solver, dynamics, joint friction, gear coupling, continuous
rotation unwinding, or proprietary DWG constraint graph is claimed. Compatibility
DXF exports evaluated geometry, not the native joint settings. Guarded source export
continues to reject nonrepresentable graph changes.

## Native schema

Optional fields on a version-1 `production.spatial.constraints` hinge/slider:

```json
{
  "limits": {"enabled": true, "min": "0", "max": "Travel"},
  "drive": {"enabled": true, "value": "Travel / 2"}
}
```

Legacy joints without these fields keep their existing behavior. Untrusted fields,
nonfinite expressions, invalid bounds, incorrect types, and conflicting drivers
reject before mutation. Stale editor dialogs reject after another drawing edit.

## Verification

`node tests/joint-limits.test.js` checks signed coordinates, stops, drivers,
local freedoms, conflicts, named expressions, persistence, physical units, copying,
reflections and invalid input. `python3 tests/joint-limits.browser.py` exercises real
ribbon/forms, native downloads, history, expressions and stale editing.

Primary background: [assembly limits](https://help.autodesk.com/cloudhelp/2023/ENU/Inventor-Help/files/GUID-2DFEAF48-DCBF-4781-9AC7-76D91DC2D896.htm)
and [constraint-based assembly](https://cadquery.readthedocs.io/en/stable/assy.html).
These describe concepts only; the solver is an original JavaScript implementation.

`python3 tests/joint-limits-native.test.py` additionally verifies actual native body
centroids, unchanged BREP payloads, STEP round trips and failed-edit placement.
