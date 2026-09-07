# Kestrel CAD — verification record

This record accompanies the shipped source and standalone bundle. The individual JSON reports are in `tests/results/` and the executable tests are in `tests/`.

| Suite | Passed | Failed | What ran |
|---|---:|---:|---|
| Core geometry and model | 59 | 0 | Node.js: geometry, curves, cameras, native validation, history, mesh volumes and DXF exchange. |
| Browser interaction | 51 | 0 | Installed Chromium: real UI/mouse/keyboard interactions plus scripted fixtures; Canvas backend; actual downloads. |
| Local HTTP server / codec protocol | 13 | 0 | Real loopback HTTP server. Three named codec checks use explicit subprocess test doubles, not native DWG conversion. |
| Independent DXF compatibility | 10 | 0 | Independent ezdxf producer/auditor, including the actual browser-exported DXF. |

The browser run reported **zero uncaught JavaScript errors**. All independently audited DXF fixtures reported **zero errors and zero automatic fixes**. The two supplied projects are editable examples, not screenshots masquerading as geometry.

## Explicitly not verified

**WebGPU:** the production renderer is implemented, but GPU execution and performance were not verified in the build environment. Browser navigation is administratively restricted, and the allowed offline document-loading context does not expose WebGPU. The included `gpu-environment.json` records UNAVAILABLE, zero GPU passes, and no adapter. No administrator policy was modified. `tests/webgpu.html` contains real production-shader/pipeline and GPU-pixel-readback checks for a suitable local machine; unavailable/fallback operation is not considered a pass.

**DWG:** native LibreDWG executables were absent. Real DWG decoding/encoding was not run. Server tests establish bridge behavior and missing-codec/error reporting, not external codec fidelity. There are no fake DWG example files.

**Engineering equivalence:** no Autodesk certification, full AutoCAD equivalence, lossless arbitrary DWG/DXF round trip, exact B-rep Boolean kernel, production manufacturing qualification, or GPU throughput benchmark is claimed.

## Preview provenance

`previews/` contains actual screenshots of the running standalone application, in dark/light 2D and dark 3D. They use the Canvas compatibility renderer. The backend badge and storage warning are retained accurately. `previews/capture-info.json` records the capture diagnostics. The warning about storage is expected in this offline test context; save `.kcad` files to preserve edits.

## Reproduce

See `README.md` for launchers, command examples, format coverage, tests, optional DWG codec setup, and GPU validation instructions.
