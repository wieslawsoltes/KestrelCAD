/**
 * Arabic contextual shaping (Unicode core spec §9.2 joining model):
 * substitute each Arabic letter with its isolated/initial/medial/final
 * presentation form (U+FB50–U+FEFF) based on its joining context, and form
 * the mandatory lam-alef ligatures.
 *
 * Operates on LOGICAL-order code points — shaping context is defined in
 * logical order, so this runs before BiDi reordering. Output glyphs keep the
 * AL bidi class of their base letters, so resolved levels are unaffected.
 */
import { JT } from '../bidi/types';
import { getJoiningType, getLamAlef, getShapingForms } from '../data/lookup';

const LAM = 0x0644;

export interface ShapeOptions {
  /** Form lam-alef ligatures (U+FEF5–U+FEFC). Default true. */
  ligatures?: boolean;
  /** 'strip' removes Arabic diacritics (harakat, tanwīn, Quranic signs). Default 'keep'. */
  tashkeel?: 'keep' | 'strip';
}

/** Result of shaping: output code points plus a map back to input indices. */
export interface ShapedText {
  codePoints: number[];
  /** src[i] = index in the INPUT array that produced output code point i. */
  src: number[];
}

/** Arabic combining marks removed by `tashkeel: 'strip'`. */
export function isTashkeel(cp: number): boolean {
  return (
    (cp >= 0x0610 && cp <= 0x061a) ||
    (cp >= 0x064b && cp <= 0x065f) ||
    cp === 0x0670 ||
    (cp >= 0x06d6 && cp <= 0x06dc) ||
    (cp >= 0x06df && cp <= 0x06e4) ||
    cp === 0x06e7 ||
    cp === 0x06e8 ||
    (cp >= 0x06ea && cp <= 0x06ed)
  );
}

/** Whether a joining type joins toward the FOLLOWING character (its left side). */
function joinsAhead(jt: number): boolean {
  return jt === JT.D || jt === JT.L || jt === JT.C;
}

/** Whether a joining type joins toward the PRECEDING character (its right side). */
function joinsBack(jt: number): boolean {
  return jt === JT.D || jt === JT.R || jt === JT.C;
}

/** Form indices into the SHAPING_FORMS tuples. */
const ISOLATED = 0;
const INITIAL = 1;
const MEDIAL = 2;
const FINAL = 3;

/** Pick a presentation form, degrading gracefully when a form is absent. */
function pickForm(forms: readonly [number, number, number, number], form: number): number {
  if (forms[form]! !== 0) return forms[form]!;
  if (form === MEDIAL && forms[FINAL] !== 0) return forms[FINAL];
  if (form === INITIAL || form === MEDIAL || form === FINAL) {
    if (forms[ISOLATED] !== 0) return forms[ISOLATED];
  }
  return 0;
}

/**
 * Shape an array of logical-order code points.
 *
 * The joining context of each letter is computed over the ORIGINAL sequence
 * (transparent marks skipped), then letters are replaced by presentation
 * forms and adjacent lam + alef collapse into a single ligature code point.
 */
export function shapeCodePoints(input: ArrayLike<number>, options?: ShapeOptions): ShapedText {
  const ligatures = options?.ligatures !== false;
  const strip = options?.tashkeel === 'strip';

  // Working copy, with src map back to the caller's indices.
  const cps: number[] = [];
  const src: number[] = [];
  for (let i = 0; i < input.length; i++) {
    const cp = input[i]!;
    if (strip && isTashkeel(cp)) continue;
    cps.push(cp);
    src.push(i);
  }

  const n = cps.length;
  const jts = new Uint8Array(n);
  let hasArabic = false;
  for (let i = 0; i < n; i++) {
    jts[i] = getJoiningType(cps[i]!);
    if (!hasArabic && getShapingForms(cps[i]!) !== undefined) hasArabic = true;
  }
  if (!hasArabic) return { codePoints: cps, src };

  const out: number[] = [];
  const outSrc: number[] = [];

  // Joining type of the nearest non-transparent character before the cursor.
  let prevJt: number = JT.U;

  for (let i = 0; i < n; i++) {
    const cp = cps[i]!;
    const jt = jts[i]!;

    if (jt === JT.T) {
      // Transparent: marks pass through and never affect the running context.
      out.push(cp);
      outSrc.push(src[i]!);
      continue;
    }

    // Nearest non-transparent neighbour ahead.
    let next = i + 1;
    while (next < n && jts[next] === JT.T) next++;
    const nextJt = next < n ? jts[next]! : JT.U;

    const linksBack = joinsAhead(prevJt) && (jt === JT.D || jt === JT.R);
    const linksAhead = joinsBack(nextJt) && (jt === JT.D || jt === JT.L);

    // Mandatory lam-alef ligature: lam + (marks) + alef variant.
    if (ligatures && cp === LAM && next < n) {
      const lig = getLamAlef(cps[next]!);
      if (lig !== undefined) {
        out.push(linksBack ? lig[1] : lig[0]);
        outSrc.push(src[i]!);
        // Marks between lam and alef re-attach to the ligature.
        for (let m = i + 1; m < next; m++) {
          out.push(cps[m]!);
          outSrc.push(src[m]!);
        }
        i = next; // consume through the alef
        prevJt = JT.R; // the ligature joins like an alef: backward only
        continue;
      }
    }

    const forms = getShapingForms(cp);
    if (forms !== undefined) {
      const form = linksBack ? (linksAhead ? MEDIAL : FINAL) : linksAhead ? INITIAL : ISOLATED;
      const sub = pickForm(forms, form);
      out.push(sub !== 0 ? sub : cp);
    } else {
      out.push(cp);
    }
    outSrc.push(src[i]!);
    prevJt = jt;
  }

  return { codePoints: out, src: outSrc };
}

/** Shape a string (logical order in, logical order out). Surrogate-safe. */
export function shapeString(text: string, options?: ShapeOptions): string {
  const cps: number[] = [];
  for (const ch of text) cps.push(ch.codePointAt(0)!);
  const { codePoints } = shapeCodePoints(cps, options);
  let outStr = '';
  for (const cp of codePoints) outStr += String.fromCodePoint(cp);
  return outStr;
}
