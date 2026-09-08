# Planar SAT/SAB and native solid DXF exchange

The **Exchange** ribbon now offers `ACISIN`, `ACISOUT` and `SOLIDDXF`.
These are geometry-only translators for **SAT format 700** and **SAB format 21800**,
not an ACIS kernel or unrestricted ACIS compatibility.

## Supported geometry

Native OCCT planar faces with straight edges map directly to ACIS bodies, lumps,
shells, faces, loops, shared coedges, edges and vertices. Export does not sample
curves, triangulate faces or round/weld nearby vertices. Closed solids, disconnected
lumps, multiple bodies, planar through-holes, internal void shells and bounded
planar surface sheets are supported. Open sheets use double-sided ACIS faces and
DXF `BODY` records rather than falsely claiming to be `3DSOLID` entities.

Import builds planar trimmed OCCT faces, sews each declared shell and constructs
valid native solids with their void shells. These bodies work with subsequent
native fillets, Boolean operations, sections, STEP export and normal project
persistence. Their display mesh is separate from their authoritative topology.

The translator uses floating-point geometry and a 1e-7 source-coordinate sewing
and boundary tolerance. This is not exact real-number arithmetic, preservation of
topological names, or a guarantee for arbitrary near-degenerate models.

## Commands and units

- `ACISIN`: choose a SAT/SAB file and acknowledge geometry-only import. Positive
  source-header millimetres-per-unit are converted to the current drawing units.
  Unitless files require an explicit source-unit override. Body transforms apply
  once before unit conversion. All decoded bodies are prepared before one atomic
  drawing transaction. Invalid input or stale dialogs do not partially modify it.
- `ACISOUT`: select 1–32 native B-rep bodies and choose SAT or SAB. The file header
  records current drawing units. Ordinary meshes are rejected, not silently
  converted to purportedly exact solids.
- `SOLIDDXF`: export selected native planar bodies as actual ACIS `3DSOLID` or
  `BODY` records. R2000/R2010 contain SAT payloads; R2013/R2018 contain SAB payloads
  in the appropriate DXF structures. This is an ASCII DXF container, even when
  the embedded body payload is binary. It is not a whole-drawing/source-preserving
  export; layers, text, block definitions and application records are not included.

Only file contents are sent to the same-origin local worker. There are no client
file-path parameters, remote conversion services, shell commands or downloaded
codecs. Install `requirements-kernel.txt` and run `python3 tools/serve.py --open`.
GitHub Pages can display saved native bodies but cannot run this Python codec.

## Deliberate rejection and fidelity limits

Curved faces, curved edges, B-splines, parametric trim curves, wire bodies,
subshells, patterns, non-manifold links, missing partners, invalid face loops,
unsupported format versions and mixed loose-edge/solid compounds reject instead
of losing geometry. A general OCCT affine transform can promote an otherwise
planar surface to B-spline representation; this adapter rejects that representation
rather than assuming equivalence. STEP remains the existing curved B-rep exchange
route. The native geometry, not a tessellation, determines export eligibility.

Import does **not** retain ACIS application attributes, modeling history or the
original file bytes. Keep the original SAT/SAB separately. The UI explicitly
requires acknowledgment of this boundary; the worker report marks
`geometryOnly: true`, and successful import logs the source SHA-256. Original DXF
and DWG archive workflows are unchanged. No claim is made about lossless modified
DWG, arbitrary SAT/SAB, proprietary dynamic blocks or commercial-kernel identity.

Input/output is bounded to 16 MiB, 32 bodies, 20,000 faces and 160,000 parsed records,
with the existing local subprocess memory/CPU/wall-clock limits. Linked-list
traversal detects cycles instead of relying on unbounded third-party iterators.

## Adapter and verification

`tools/acis_exchange.py` isolates the pinned ezdxf 1.4.4 record interfaces. Its
local loader corrects that version's `next_shell` type check; its local SAT writer
uses round-trippable doubles rather than the dependency's six-significant-digit
`:g` default. Neither fix modifies global dependency classes or registries.

`tests/acis.test.py` checks native topology, holes, cavities, source transforms,
units, real post-import fillets/STEP, corruption and unsupported-input rejection.
`tests/acis_interop.py` independently decodes the output and audits supported DXF
versions with ezdxf. `tests/acis.browser.py` exercises actual HTTP-to-local-worker
file dialogs, uploads, downloads, persistence, undo and rejection paths in CI.
Local standalone UI diagnostics using a direct Python-kernel binding do not count
as validation of HTTP transport. Hardware WebGPU and real DWG codecs remain
separately unverified. These tests are not an Autodesk/Spatial compatibility
certification; the ezdxf decoder itself is a deliberately limited implementation.

Primary references: [ezdxf ACIS tools and entity topology](https://ezdxf.readthedocs.io/en/stable/acis.html),
[ACIS-based DXF entities](https://ezdxf.readthedocs.io/en/stable/dxfentities/body.html),
and [published SAT units guidance](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Controlling-the-drawing-units-when-exporting-to-an-ACIS-SAT-file.html).
