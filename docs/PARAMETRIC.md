# Planar parametric sketching

## Use the editor

Open the Parametric ribbon. `PARAMDEMO` creates a rectangle with fixed origin, horizontal/vertical segments, Width and dependent Height dimensions. Use `PARAMETERS` to change Width from 100 to 160; the rectangle becomes 160 × 96. Undo restores the parameter and geometry together.

`GEOMCONSTRAINT` creates a relation using actual entity IDs and named point anchors. A segment index selects the segment of a straight polyline; its last index can select the closing segment. Point anchors are `start`, `end`, `mid`, `center`, `position`, or a zero-based vertex index. `mid` on an arc uses the midpoint of its positive sweep. Circle and arc tangency operates on the underlying full circles/infinite supporting line, not on a trimmed-domain contact constraint.

`CONSTRAINTS` edits dimensional expressions, suppresses or deletes individual constraints. `CONSTRAINTMODE` temporarily disables solving while retaining the equations; re-enabling solves or rejects atomically. `DELCONSTRAINT` confirms removal of the complete constraint/parameter set, retaining geometry; undo restores it. Constraint bars are a canvas overlay and can be hidden with `SHOWCONSTRAINTS`.

The supported relations are horizontal, vertical, coincident, distance, signed distance-x/y, fixed point, fixed entity, parallel, perpendicular, collinear, equal line length/circle radius, concentric, radius, diameter, signed angle, line-circle and circle-circle tangency (external/internal), point on line/circle, midpoint and point symmetry about a segment axis.

## Expressions

Names contain letters, digits and underscores, start with a letter and are case sensitive. Reserved built-ins and prototype-related names reject. Expressions support numbers/scientific notation, parentheses, unary signs, `+ - * / ^`, constants `pi`, `e`, `deg`, and whitelisted math functions. `^` is right associative and binds more strongly than unary minus. Trigonometric functions use radians (`sin(30*deg)`); angular constraint values use degrees. Expressions never use JavaScript `eval` or execute arbitrary code.

Parameters form a dependency graph. Unknown names, duplicate names, cycles, excessive depth, nonfinite values and expression-size limits reject. Deleting a parameter that a live dimensional expression still needs is rejected. Numeric results are limited to ±1e12. Up to 128 named parameters are supported.

## Solving and history

A damped nonlinear least-squares iteration uses a central-difference Jacobian in normalized local sketch coordinates. Full fixed entities and locked-layer entities are eliminated from unknowns. A small deterministic branch seed handles a distance norm whose initial points coincide. Only converged finite positive-radius solutions are applied. There is no claim of a globally optimal or unique solution, guaranteed convergence, or exact symbolic arithmetic.

Each normal drawing transaction solves before updating dependent annotations and validating the document. Nonconvergence rolls back coordinates, parameter definitions, equations and undo history. Layers marked locked remain constant. Removing an entity prunes constraints referencing it; undo restores both. Unsupported geometry conversions fail rather than retaining dangling constraint references. Explicitly remove/suppress constraints before incompatible modifications.

`SOLVE` reports participating unknowns/equations, local numerical rank, remaining degrees of freedom, redundant equations, normalized residual and iteration count. Unreferenced drawing entities are outside those counts. Redundancy and rank are numerical/local. Failure to converge does not prove inconsistency. The normalized convergence threshold is 1e-8; absolute length accuracy depends on sketch extent. There is a 160-free-variable, 512-referenced-scalar, 256-constraint, 512-equation, 200-iteration upper bound and a normal 1.5-second iteration budget. These are safeguards, not performance promises.

## Coordinate systems, units and copying

The first constraint captures the current UCS as its saved sketch plane. All constrained geometry must lie on that plane; changing the current drawing UCS does not silently relocate existing constraints. One sketch plane is supported per drawing. Skewed/noncircular conics and bulged polylines reject; explode a bulged polyline into supported pieces first. Splines, 3D assembly mates and NURBS surface constraints are outside this module.

Physical drawing-unit conversion rescales geometry, plane origin and fixed targets. Named length expressions retain their original explicit parameter units, converted into the current drawing units during solving. Metadata-only changes reinterpret parameter units without rescaling coordinates. Angular values are not length-scaled.

The ordinary clipboard copies fully contained constraints, fixed targets and dependent parameters. Parameter name collisions receive deterministic copy suffixes and expression references are rewritten. Uniform transformations preserve length relations with the appropriate factor; different units preserve physical size. Combining sketches requires compatible axes and coplanarity. Constraints to objects outside the copied selection, incompatible destination planes, and nonuniform/skewed copies are omitted **with an explicit clipboard warning**; the geometry is still copied. A drawing with more free variables than the solver limit must have solving disabled or be split before combining sketches.

## Files and validation

Native `.kcad` projects retain the full parameter/constraint graph and solved coordinates. Standard DXF export writes supported evaluated geometry and does not promise interchange of these native constraints with AutoCAD. Keep `.kcad` for continued parametric editing.

Run `node tests/constraints.test.js`, `python3 tools/build.py`, and `python3 tests/constraints.browser.py`. The latter uses real forms, parameter changes, downloads, undo, unit conversion and clipboard operations. CI runs these alongside the native solid and original/production regression suites.

Design references: Autodesk's geometric-constraint workflows (https://help.autodesk.com/cloudhelp/2023/ENU/AutoCAD-Core/files/GUID-668B1B7D-9991-44CA-8607-83665A82FF7F.htm) and the general damped nonlinear least-squares approach represented by MINPACK (https://netlib.org/minpack/). This is an original JavaScript implementation, not copied MINPACK code or Autodesk's solver.
