# Configurable blocks

The **Blocks** ribbon and `DYNAMICDEMO` expose native, browser-only configurable blocks. Each INSERT retains a shared definition, independent typed parameter values, its placement transform and attribute values. Changing parameters evaluates real geometry from the original definition; it does not repeatedly transform a previously generated mesh. Undo/redo and `.kcad` save/load retain the behavior.

## Use

Run `DYNAMICDEMO` for two editable fabrication plates. Select either plate and change Width, Height, Fastener, Count, visibility or flip using the inspector or **Block parameters** (`BPROPERTIES`, `DYNBLOCK`). The second instance remains independent. The fastener lookup sets the hole radius; the derived Area field is read-only. `BRESET` resets selected references to their definition defaults. `EXPLODE` creates the current evaluated geometry and removes that instance's behavior; undo restores it.

`BDEFINE` edits the selected reference's shared dynamic definition, or attaches a starter definition to a normal block. The dialog lists stable local entity and `attribute:TAG` identifiers. `BACTION` offers forms for move, stretch, rotate, scale, flip, rectangular/polar array and polar-stretch actions. Advanced visibility, lookup tables and parameter definitions use the validated JSON editor. `BEDIT`/`BCLOSE` still edit shared base geometry. Definition changes update all references; references with incompatible overrides cause validation failure rather than a partial update.

## Parameters

A definition stores `dynamic: {version: 1, parameters: [...], actions: [...], lookups: [...]}`. Parameters use `number`, positive `length`, degree-valued `angle`, `integer`, `boolean` or `enum` types. Numeric parameters support minimum, maximum, increment and discrete allowed values. A numeric expression can depend on other parameters; the existing arithmetic expression parser rejects cycles, unknown symbols and executable input. Boolean values can enter numeric expressions as 0/1; enum strings cannot. Derived values and lookup outputs are not editable overrides.

Lookup tables select an enum input and provide a complete row for each enum value. Each row must drive the same output names with compatible typed values. Conflicting drivers are rejected. `${Parameter}` in visible attribute text interpolates the evaluated value; the stored template and per-instance attribute source are not overwritten.

## Actions

Actions execute in listed order in **definition-local coordinates**. All targets are stable base-entity IDs or `attribute:TAG` identifiers.

| Action | Geometry behavior |
|---|---|
| move | Translate targets with X/Y/Z numeric expressions. |
| stretch | Move the vertices of straight lines/polylines inside a specified local crossing box. Fully enclosed other objects translate; unsupported partial curved-object stretches reject. |
| rotate | Rotate by a degree expression around a specified local center and axis. |
| scale | Uniform positive scale about a local center. |
| flip | Reflect across a local plane when its boolean parameter is true. |
| array | Generate positive integer rows/columns using local X/Y spacing. Downstream actions also affect the copies of their source targets. |
| polar-array | Replicate a target group around an arbitrary 3D axis with expression count/fill angle; optionally keep orientation about a shared base. |
| polar-stretch | Change reach and rotation together with a local stretch frame and explicit rigid/rotate-only member modes. |
| visibility | Choose a complete enum state. Objects outside the visibility action's target scope remain visible. |

Example stretching the far endpoint of a line:

```json
{
  "version": 1,
  "parameters": [{"name": "Width", "type": "length", "default": 100, "min": 10, "max": 1000}],
  "actions": [{"type": "stretch", "targets": ["line-id"], "min": [90, -1, -1], "max": [110, 1, 1], "x": "Width - 100"}]
}
```

Copy/paste brings referenced definitions and behavior to the destination drawing. Unit conversion occurs in the INSERT transform exactly once; parameter values remain in the definition's original local units. Native-solid members may undergo valid whole-object transformations; a dynamic stretch does not directly modify native solid topology.

## Rendering and interchange

Visible members use their own layers, colors, line styles and mesh classification. Layer 0 and ByBlock inheritance are resolved through nested references. Hidden member and nested-reference layers are respected. Selecting a reference highlights its visible members as one object. SVG uses distinct member IDs and member appearance.

**DXF exports evaluated static variants**, using standard BLOCK/INSERT records for each configured instance and evaluated attribute text. Independent ezdxf tests verify positions, colors, standard references and zero audit repairs. The native master is not changed. The exporter does **not** encode this schema as Autodesk dynamic-block evaluation objects, and importing an arbitrary AutoCAD dynamic block does not recover its actions. Retain `.kcad` as the configurable master. Normal persistent block attributes retain their existing standard interchange behavior.

## Boundaries

This is a Kestrel-native ordered action system, not full AutoCAD dynamic-block compatibility. There is no dedicated graphical action-chain editor, custom drag parameter grip, alignment parameter, associative path array or proprietary DWG action-graph evaluator. Partial curved-entity stretch is rejected. A definition is bounded to 64 parameters and 128 actions; each evaluation is bounded to 20,000 generated objects, with the existing nested-block depth and drawing limits still enforced. These are resource guards, not performance guarantees. Invalid or oversized evaluations roll back atomically.

## Reproducible checks

```sh
node tests/dynamic-blocks.test.js
python3 tools/build.py
python3 tests/dynamic-blocks.browser.py
python3 tests/dynamic_interop.py
```

The browser suite mixes actual ribbon, dialog, inspector, clipboard and download operations with scripted fixture selection. The complete release verification discovers these suites automatically. Hardware WebGPU execution remains a separate validation path.

## Polar arrays and inverse table matching

`BACTION` now authors `polar-array` actions, and `BLOOKUPMATCH` selects a uniquely matching lookup row from numeric/boolean output properties. See [exact action schema, matching semantics and test commands](POLAR-BLOCKS.md). This inverse discrete-row match is not a proprietary action-graph decoder.

## Polar stretching

`BACTION` also authors coordinated reach/rotation actions. See [polar-stretch geometry, member modes and boundaries](POLAR-STRETCH.md).
