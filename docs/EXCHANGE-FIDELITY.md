# Precision and text fidelity corrections

This update extends the integrated source-document editor; it does not introduce
another archive format or replace the guardrails documented in SOURCE-DOCUMENTS.md.

- DXF numeric output uses the full round-trippable JavaScript double representation,
  rather than rounding every coordinate to ten decimal places. Editing one endpoint
  therefore does not round an unedited endpoint in the same source record.
- TEXT, ATTDEF and ATTRIB content retains significant leading/trailing whitespace.
- Unicode block names remain distinct, are escaped consistently in legacy DXF
  BLOCK_RECORD/BLOCK/INSERT names, and survive repeated compatibility exports.
  Model/paper-space containers are not manufactured into user-defined blocks.
- Source TEXT generation bits unrelated to backwards/upside-down flags are retained.
- Reassigning a source entity color removes an obsolete color-book name as well as
  obsolete indexed/true-color values.

`tests/exchange-fidelity.test.js` covers 14 numerical, record, text and block cases.
`tests/exchange_fidelity_interop.py` uses ezdxf and its Unicode escape decoder to
verify both edited and converted ASCII/binary files independently (four checks,
zero audit errors or automatic repairs). The established source/browser suites
remain required in full CI. This does not establish arbitrary lossless CAD editing,
ACIS compatibility, real DWG codec execution or hardware WebGPU verification.
