# Inserting drawings with associative annotations

Insert drawing uses the same definition-aware transfer as the native clipboard. It builds the complete source-to-destination entity identity map before copying object, aggregate, and field-to-field descriptors. Existing destination objects with identical source IDs are never used as replacement dependencies.

The source project is validated and its annotation caches refreshed in its own drawing context before transfer. Source drawing properties and named-parameter fields that cannot keep their original context are frozen to those refreshed values. Dependent field-to-field links are frozen transitively, with a warning. The source project and caller's serialized data are not mutated.

Layers, block definitions, dimension and text styles, supported associations, and complete supported constraint groups follow the existing clipboard transfer semantics. Geometry and live measurements use destination units, while explicit physical field units stay stable. Original source-file archives are not copied into the destination.

The complete insertion is one transaction: undo restores the destination, and redo restores inserted identities and dependencies. Invalid projects fail before insertion; transfer failures roll back the transaction.

## Regression checks

```sh
python3 tools/build.py
python3 tests/fields-insert.browser.py
```

Eight real browser checks exercise App.insertData with colliding destination IDs, forward and aggregate dependencies, stale source caches, source-context freezing, unit conversion, block attributes, undo/redo, and malformed-input rollback. This suite is automatically discovered by tools/verify.py. Full CI remains required before merge; this fix does not expand proprietary DWG field compatibility.
