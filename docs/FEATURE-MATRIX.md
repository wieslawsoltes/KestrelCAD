# CAD feature boundaries

This matrix describes implementation boundaries, not certification of AutoCAD equivalence. A passing regression suite demonstrates the exercised cases, not arbitrary-file compatibility.

| Area | Integrated implementation | Remaining compatibility work |
| --- | --- | --- |
| Drafting | Editable analytic curves, layers, blocks, annotations, layouts, precision input and undo | Additional commercial command variants and paper-space interaction |
| Productivity | Quick selection, counts, analytic DIVIDE/MEASURE, LENGTHEN/REVERSE, extraction and validated layer states | Associative extraction and additional curve station types |
| Native solids | Optional local OpenCascade B-rep worker; primitives, profiles, Booleans, edges, slicing, single-face thickening, mass properties and STEP/BREP | ACIS/SAT/SAB translation, persistent topological naming and additional surface operations |
| Constraints | Native planar geometric/dimensional solver with named parameters and rollback | Spatial sketch and assembly constraints |
| Configurable blocks | Native typed parameters, expressions, lookup, visibility, flip, move/stretch/rotate/scale and rectangular arrays | Autodesk proprietary action-graph evaluation and native DWG dynamic-block compatibility |
| Text | Local SHX/SHP and browser outline fonts; native rich MTEXT with scopes, fractions, paragraphs, Unicode bidi runs, masks and native columns | Linked-column DXF, general fields, vertical MTEXT, Big Fonts and complete font/layout equivalence |
| Source files | Original ASCII/binary DXF archives, byte-identical original recovery, guarded compatible record edits and optional local DWG conversion | Unrestricted DWG editing, opaque-object regeneration and complete application-specific data fidelity |

## Runtime boundaries

Core drafting, constraints, configurable blocks and text run in plain JavaScript. Native solid operations require the local Python bridge. GitHub Pages displays saved native bodies but does not execute the Python kernel. Font files are supplied by the user and are not redistributed. Actual DWG codec and hardware-WebGPU verification must be reported separately from mocked bridge or Canvas tests.

## PR #11 integration repair

The prior branch contained productivity source but did not load it. The repaired source loads the core and UI modules directly in the application, includes core validation in the exchange worker, installs the UI synchronously, and validates untrusted saved layer states. Redundant self-modifying completion scripts are removed. Current main's DXF precision, significant-space and Unicode-block fixes are retained. The complete CI suite must pass on this final readable source before merge.
