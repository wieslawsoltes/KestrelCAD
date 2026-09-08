# Text styles and local font resources

Open the **Text** ribbon, or run `STYLE`, `FONTLOAD`, `FONTREPORT`, and `TEXTSTYLE`.

`STYLE` creates and edits named drawing styles: font filename, fixed or per-text height,
width factor, oblique angle, backwards, upside-down and vertical writing. The normal
text editor exposes text content and per-entity overrides. `TEXTSTYLE` applies a style
to selected editable text and clears width/slant/writing overrides. All drawing edits
are transactional and participate in native persistence, undo and redo. Clipboard
transfer copies and remaps style definitions instead of silently choosing a different
style with the same name.

## Supply your own font

`FONTLOAD` accepts SHX, SHP and browser-supported TTF/OTF/WOFF/WOFF2 files through a
local file chooser. Files are processed only in the browser. No font file is bundled,
automatically fetched, uploaded, or embedded in native project downloads. Resources
remain in memory for the current tab; reload the required fonts after restarting it.
A maximum of 32 resources / 64 MiB of original data and 16 MiB per file is accepted.
These are input guards, not peak-memory guarantees.

Filename matching is case-insensitive and ignores directories. A style referring to
`txt` also resolves a supplied `txt.shx`. A later load under the same filename replaces
the resource and invalidates cached text geometry. Keep the exact original font files
and honor their licenses. The font loader does not search the operating system.

`FONTREPORT` shows unresolved resources and glyphs in visible annotations. Missing
stroke fonts/glyphs use visible crossed-box placeholders, not invented lookalike
characters. Missing outline fonts use the explicitly reported browser fallback.
Big Font dependencies are retained as references but are not implemented.

## Stroke fonts

The original JavaScript implementation reads **AutoCAD-86 shapes 1.0/1.1** and
**unifont 1.0** SHX records and documented SHP source descriptions. It handles short
vectors and instructions 1–14: pen controls, vector scale, location stack, subshapes,
signed displacement lists, octant and fractional arcs, bulge/polybulge arcs, and
vertical-only instructions. Font cap height and pen advances determine layout.
Legacy degree, plus/minus and diameter glyph numbers are mapped explicitly.

SHX glyphs become world-space line geometry consumed by the existing WebGPU or
Canvas renderer. Width, oblique, alignment, rotation, reflection and drawing-plane
orientation are applied to that geometry. SVG exports these strokes as self-contained
paths. Curved glyph strokes are tessellated at a maximum two-degree angular step;
this is not bit-identical font rasterization or exact curve output. Repeated glyphs
are cached with a bounded segment budget. Invalid indexes, missing subshapes, cycles,
truncated streams, malformed instructions and excessive expansion reject explicitly.

Horizontal glyph advances are placed on the baseline. Vertical SHX writing requires
a dual-orientation font. Multi-column vertical text uses the configured line spacing.
Big Font / extended Big Font encodings, nonstandard SHX variants, complex script
shaping and perfect agreement with every historical CAD font are **not** claimed.

## Outline fonts

Loaded outline fonts use the browser's FontFace and Canvas text implementation.
Cap-height and advance metrics are measured from the loaded font. Unicode shaping is
whatever the browser/font combination actually supports; it is not an independent
AutoCAD text-layout engine. Oblique and width transforms are applied in the text's
local plane. Vertical outline text uses stacked characters, not a SHX vertical font
program. For sfnt TTF/OTF files, the family name used by standalone SVG is read from
the font's name table. WOFF-family naming may fall back to the supplied filename.
Outline SVG does not embed fonts: its appearance depends on matching fonts in the
viewing environment. PNG captures the displayed glyphs.

## File fidelity

Native projects preserve named style tables, current style and text overrides,
including font dependencies. The supported ASCII DXF path reads/writes STYLE records,
font/big-font names, width and oblique defaults, writing flags, and TEXT/attribute
style references and supported overrides. Multiline native text is written as
separate TEXT records, not a fully formatted MTEXT object. MTEXT inline formatting,
full attachment/alignment modes, SHX shapes embedded in linetypes, and proprietary
text/field objects are not round-tripped losslessly. Keep the original drawing.

## Evidence and sources

`node tests/fonts.test.js` checks parser instructions, layout, resources, affine
transforms, persistence, failures and exchange. `python3 tests/fonts.browser.py`
exercises real file selection, a synthetic stroke font and an original in-memory
synthetic TrueType font, text/style controls, clipboard and actual downloads.
`python3 tests/fonts_interop.py` compares synthetic SHX endpoints against ezdxf's
independent interpreter and audits the STYLE/TEXT DXF output. No font asset file is
included in the test package.

Primary references:
- Autodesk, Special Codes Reference: https://help.autodesk.com/cloudhelp/2022/ENU/AutoCAD-Customization/files/GUID-06832147-16BE-4A66-A6D0-3ADF98DC8228.htm
- Autodesk, Shape Descriptions: https://help.autodesk.com/cloudhelp/2021/ENU/AutoCAD-Customization/files/GUID-DE941DB5-7044-433C-AA68-2A9AE98A5713.htm
- ezdxf STYLE entity documentation: https://ezdxf.readthedocs.io/en/stable/tables/style_table_entry.html
- ezdxf independent SHX interpreter: https://github.com/mozman/ezdxf/blob/master/src/ezdxf/fonts/shapefile.py
