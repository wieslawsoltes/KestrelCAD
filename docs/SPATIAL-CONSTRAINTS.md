# Spatial constraints and rigid assembly mates

The **Assembly** ribbon operates in true world XYZ. These equations are not projected onto the active drafting plane. The browser-only numerical library is `Kestrel.SpatialConstraints` in `src/spatial-constraints.js` and has no additional runtime dependency.

## Working geometry and relationships

POINT coordinates and LINE / straight POLYLINE vertices are free 3D variables. MESH entities (including retained native OpenCascade bodies) and INSERT references have six rigid pose variables: three translations and three rotation-vector components. An INSERT's shared definition is not rewritten. Moving a native body composes its authoritative BREP transform and its display mesh together; native integrity validation remains enabled.

Relationships include coincidence; Euclidean distance; signed X/Y/Z distances; fixed points and entities; parallel, same/opposite direction, perpendicular and 0–180 degree angles; equal lengths and length ratios; point-on-line; signed point-to-plane distance; midpoint; and symmetry through a plane. Assembly relations compose these equations:

| Relation | Equation meaning | Remaining DOF for one free rigid body against a fixed nondegenerate datum |
|---|---|---|
| Plane mate | Opposed normals and signed plane offset | Two translations and one spin |
| Coaxial | Collinear axes, parallel or antiparallel | Axial translation and rotation |
| Hinge | Coincident datum origins and same axis direction | One rotation |
| Slider | Aligned full frames and origin on datum axis | One translation |
| Fastened | Aligned full frames and coincident origins | Zero |

Those DOF counts describe the stated isolated configuration, not every possible assembly. Conflicting, repeated or degenerate geometry can change numerical rank. A `parallel` relation does not choose between parallel and antiparallel; choose `same-direction` or `opposed` when orientation matters.

## Authoring

`3DCONSTRAINT`, `3DMATE`, and `3DDIM` open a relationship form. Select drawing entities or fixed world datums. Flexible geometry accepts start/end/mid/numeric point anchors and a polyline segment index. Rigid bodies accept a local XYZ datum or a `vertex:index` mesh vertex. Local axes follow the body's retained frame. World datums remain independent of the current UCS. Mating frames require two independent axes.

`3DFIX` fixes selected supported objects in one history transaction. `3DPARAMETERS` edits named arithmetic expressions using the same safe expression parser as planar sketches, with an independent parameter namespace. Length expressions have saved physical units; angular expressions are degrees and length ratios are dimensionless. `3DCONSTRAINTS` edits values, suppresses/deletes relationships, or disables solving without losing the graph. `3DSOLVE` explicitly solves; normal document transactions enforce active relationships automatically. `3DDOF` reports actual rank, residuals and local freedoms without modifying geometry.

`3DASSEMBLY` creates an editable lift example: a fixed base, a rigid slider and a named `Lift` driving distance. Change the expression from 25 to 40 to move the carrier without deforming either mesh. This example deliberately uses meshes; it does not impersonate native BREP data.

## Native library example

```js
const d = new Kestrel.Drawing('Space frame');
const p = d.add('POINT', {position: [10, 20, 30]});
Kestrel.SpatialConstraints.add(d, {
  type: 'distance-z',
  a: {world: [0, 0, 0]},
  b: {entity: p.id, point: 'position'},
  value: 50
});
// p has been replaced in the drawing database; read the current entity by ID.
console.log(d.byId.get(p.id).position); // [10, 20, 50], within numerical tolerance
```

Rigid references use `{entity: id, local: [x,y,z], axis: [0,0,1], xaxis: [1,0,0]}`. World datums use `{world: [x,y,z], axis: [nx,ny,nz]}`. A rigid entity's `constraintFrame` maps local datums to world space. It is initialized when the entity participates and composed through ordinary transforms. Mesh vertex anchors refer to current vertex indices, not persistent topological names. Native topology-changing operations normally replace entity IDs; deletion removes the corresponding equations and undo restores them.

## Persistence, editing and failure behavior

The graph is stored in `production.spatial`, schema version 1, with parameters, constraints, units and enable state. Native save/load and undo/redo retain frames and solved geometry. An unsatisfied/invalid edit rolls back both equations and geometry; a diagnostic-only solve never applies a candidate. Stale UI dialogs reject after another edit or document switch. Locked layer geometry is constant during solving.

Unit conversion updates fixed targets, world datums and rigid frames while preserving the physical meaning of saved driving parameters. Copying a complete constrained selection retains the graph, remaps IDs, renames colliding parameters and transforms world/rigid datums and signed measurement axes. References to uncopied entities are omitted with a warning. Nonuniform/skewed clipboard transforms explicitly omit equations; they retain the transformed geometry. Ordinary compatibility DXF contains evaluated geometry, **not this native graph**. Imported source-preserving export rejects changed production definitions rather than claiming equivalent DWG constraint records.

The planar and spatial solvers may coexist on disjoint free geometry. Sharing a free entity between active independent systems is rejected instead of allowing one solver to silently overwrite the other. Suppress/disable one system or separate the drawings. Shared locked references remain constant.

## Numerical scope and limits

Damped least squares uses central-difference Jacobians, normalized world coordinates, fixed-entity elimination, pivoted dense solves and numerical rank diagnostics. Deterministic small seeds handle stationary distance/angle configurations. A solution is applied only after all active residuals converge. Failure to converge is **not proof** that an arrangement is globally impossible.

Default budgets: 192 free scalars, 768 referenced scalar/residual components, 256 constraints, 128 parameters, 100 iterations and 1.5 seconds. Residual threshold is 1e-9 in normalized length/direction coordinates; rank threshold is 1e-7. DOF is local and tolerance-dependent. Vector equations have inherently redundant components, so `redundantEquations` is not a count of unnecessary user constraints.

This is not a general deformable-solid, NURBS-surface, spline or flexible-conic solver. Arbitrary shell contacts, collision avoidance, dynamics, kinematic animation, inferred face mates, persistent topological naming and proprietary DWG constraint graph compatibility are not implemented. It is a numerical solver, not exact arithmetic or a manufacturing certification.

## Verification

- `node tests/spatial.test.js`: numerical geometry, dimensional expressions, mates/DOF, rigid poses, conflicting edits, locked/suppressed/disabled states, units, clipboard, native persistence and invalid-input budgets.
- `python3 tests/spatial-native.test.py`: **actual OCCT** native bodies transformed by the JS solver, measured by the native engine, genuine STEP round trips, subsequent native fillets, undo and native mesh integrity.
- `python3 tests/spatial.browser.py`: real editor ribbon/dialog/clipboard/units/download/history workflows, not mocked DOM controls.

Primary background references: [SolveSpace reference](https://solvespace.com/ref.pl) and [CadQuery assembly constraint documentation](https://cadquery.readthedocs.io/en/latest/assy.html). This library is an original implementation; those packages are not invoked by its solver.

## Joint travel

Hinge and slider mates now accept bounded travel and expression-driven positions.
See [joint limits, coordinate conventions and diagnostics](JOINT-LIMITS.md).
