# Pinned Unicode bidirectional algorithms

MIT-licensed source from https://github.com/cc1a2b/bidi-shaper, recovered by content-addressed GitHub blobs. `manifest.json` records exact upstream Git blob IDs and SHA-256 values, including full conformance fixtures not bundled here. The implementation uses Unicode 17.0.0 tables. Original sources are unchanged.

`src/unicode-bidi.js` is built by `node tools/build_unicode.cjs` (TypeScript compiler required only for regeneration). The normal application and Python standalone build require no npm package.

`tests/unicode.test.js` verifies a deterministically selected official conformance corpus. Set `KESTREL_BIDI_FIXTURES` to a directory containing the two exact pinned `.gz` fixtures to run the complete corpus. Tests validate the algorithm independently of CAD layout.

See `LICENSE` for the library and `UNICODE-LICENSE.txt` for the Unicode data/corpus. No font files are included.
