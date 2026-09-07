# Native solid and surface editing

These operations extend the already integrated **OpenCascade** engine. They operate on retained B-rep geometry, not triangle approximations. This is not ACIS or SAT/SAB support.

Run the local server after installing `requirements-kernel.txt`. GitHub Pages can display saved bodies but cannot execute the Python kernel. All new tools are available on the **Solids** ribbon and through the command palette.

## Commands

- **SLICE** (`solid-slice`): select one or more native bodies; enter plane origin and normal in the current UCS; retain the positive side, negative side or both. The cutter uses analytic infinite half-spaces. Each input produces at most two independently editable native bodies, preserving its layer, color and line properties. The plane must cross the interior, not merely touch it. Native single-face surfaces can also be sliced.
- **PLANESURF** (`solid-plane-surface`): select a closed circle, ellipse or polyline, followed by optional hole boundaries. It creates a planar native face, leaving source profiles intact. All loops must be coplanar and form valid topology. A surface has area and no solid volume.
- **SOLIDEXTRACT** (`solid-extract-faces`): select a native body and choose current face indices from the topology table. Extracted planar or curved faces retain the source's appearance. The original body remains.
- **THICKEN** (`solid-thicken`): thicken one native face with a positive or negative distance. Optionally retain the source surface. This uses the native offset/solid algorithm, including curved faces, and rejects invalid offsets. Arbitrary multi-face shells are not accepted by this command.
- **SOLIDSEPARATE** (`solid-separate`): turn a composite native body containing multiple solids into independent entities, in one undoable operation.
- **MASSPROP** (`solid-massprops`): download a JSON report with volume, surface area, uniform-density mass, world-space centroid, centroidal world-axis inertia tensor, principal moments/axes, and bounds. Values come from the transformed B-rep. Mass units follow the entered density; inertia has mass × drawing-unit² units. Multiple solids are additive, including overlaps; union overlapping solids first to measure their geometric union.

## Editing guarantees and limits

All outputs of a multi-body operation are validated before input deletion. Input deletion, new entities and selection are one atomic transaction. Undo restores native data; native project saving retains every resulting body. A drawing changed while the dialog or kernel operation was active causes the result to be rejected rather than overwriting newer edits. Native Boolean and edge operations now preserve the first input's appearance too.

Display tessellation is finite and independent of the B-rep. Native algorithms still use numerical tolerances; validity checks are not a manufacturing certification. Self-intersections, singular offset surfaces, excessive topology or native-library failures are reported without committing geometry. One request is limited to 32 inputs, 64 results, a combined display-vertex limit, and a 48 MiB multi-body response. Existing wall-clock and process resource guards still apply.

STEP import now collects **all transferred roots**, not only the first. It does not promise retention of source assembly names, colors or application metadata. IGES may contain disconnected surfaces rather than solids. DWG/DXF and ACIS compatibility are unchanged.

## Verification

`python3 tests/native-edit.test.py` executes actual OpenCascade geometry tests, including analytic volumes, inertia, curved-face thickening, inclined slicing, hole preservation, STEP multi-body round trips and invalid input rejection. `python3 tests/native-edit.browser.py` exercises the served editor and actual native bridge, UI dialogs, downloads, appearance, native persistence, stale-result rejection and undo/redo. The complete release runner discovers both suites automatically.
