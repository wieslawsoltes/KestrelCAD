# Parametric sketches

Kestrel's parametric extension edits real drawing geometry and stores its driving relationships in native `.kcad` documents. It is implemented in plain JavaScript. It does not evaluate JavaScript from parameter input and does not require the native-solid service.

## Everyday workflow

Select a line and open **Parametric**, or find a constraint through **Ctrl+K**. Apply Horizontal or Vertical. Use **PARAMETERS** to define values such as:

```text
width = 100
height = width * 0.6
diagonal = sqrt(width^2 + height^2)
```

Apply a driving length with the expression `width`. Changing that parameter deforms the constrained sketch. Add an anchor or other relationships to remove remaining freedom. **Fix geometry** fixes every point of a selected line or straight polyline; for a circle it fixes the center and radius. A fully fixed entity cannot also change size until the relevant fixed relationship is removed or disabled.

**CONSTRAINTS** opens the manager. It displays IDs, types, driving values and enabled states, supports removal/disabling, and provides an advanced JSON editor for reference-level definitions. **CONSTRAINTSTATUS** displays the remaining degrees of freedom, estimated numerical rank, dependent equations and residual.

For point-based constraints, choose the endpoint indices in the dialog. Circle point references select its center. Point-on-line and point-on-circle use a point from the first selected entity and the second entity as the target. Midpoint uses three point-bearing entities in reference order. Symmetry uses two point-bearing entities followed by an axis line.

## Supported relationships

The solver implements coincidence, horizontal/vertical lines, line length, point distance, signed horizontal/vertical distance, parallelism, perpendicularity, signed line angle, equal lengths, radius, diameter, concentricity, equal radii, line-circle and circle-circle tangency, point-on-line, point-on-circle, midpoint, symmetry about a line, and fixed points.

Drawing integration supports **planar LINE, straight-vertex POLYLINE, and CIRCLE geometry**. Polyline segment references are available in advanced definitions. Bulged polylines, arcs, splines, surfaces, solids and 3D assemblies are not represented by this solver. Unsupported or non-coplanar geometry produces an error rather than being silently projected or converted.

Each sketch captures an orthonormal UCS plane when its parametric state is created. Changing the current drafting UCS does not silently redefine an existing constrained sketch's plane.

## Expressions

Numbers, named parameters, parentheses, unary signs, `+ - * / ^` and these functions are supported:

```text
abs sqrt sin cos tan asin acos atan atan2 min max floor ceil round deg rad
```

`pi` and `e` are constants. Powers associate right-to-left; `-2^2` is `-4`. Trigonometric functions use radians; driving angle values use degrees. `rad` and `deg` convert units. Parameters can reference other parameters in any definition order. Cycles, unknown names, reserved identifiers, division by zero and non-finite values are rejected.

## Transactions and failure behavior

Constraint enforcement executes inside the drawing's existing transaction boundary, before linked annotations and validation. Parameter changes, solved geometry and constraint edits participate in the same undo/redo operation. A non-convergent or contradictory edit throws a conflict error and restores the prior drawing. Indirect movement of geometry that was locked or hidden before an edit is rejected. Deleting an entity also removes its attached constraints within the same undoable transaction.

The pure solver API returns a proposed solution and diagnostics without mutating its input. A failed solve must never be interpreted as a successfully applied edit.

## Numerical and interchange limits

This is a local, finite-precision nonlinear solver, not a proof engine or an implementation of every AutoCAD constraint behavior. It uses coordinate rebasing, logarithmic circle-radius variables, damped least squares, bounded iteration, and a numerical Jacobian/rank estimate. Different initial configurations can converge to different valid solutions. Singular or degenerate arrangements can fail to converge even when a different starting arrangement would solve.

A sketch is bounded to 128 scalar variables and 128 active constraints; native files can retain up to 256 enabled/disabled definitions. These limits are deliberate browser resource guards, not performance guarantees for arbitrary systems. Diagnostics describe the local solution, not global uniqueness.

Native projects preserve the driving metadata. The existing DXF exporter exports evaluated geometry; it does **not** encode this solver as AutoCAD associative constraint objects. Keep `.kcad` as the editable parametric master. General 3D constraints and lossless arbitrary DWG/DXF constraint interchange are outside this implementation.

## Reproducible checks

```sh
python3 tools/install_parametrics.py
node tests/constraints.test.js
python3 tools/build.py
python3 tests/constraints.browser.py
```

The browser suite needs Playwright and Chromium and runs against the real local editor. It exercises constraint commands, driving expressions, geometry updates, conflict rollback, undo/redo and a native project download. Test reports contain the actually executed counts; this document does not substitute a promised count for a completed run.
