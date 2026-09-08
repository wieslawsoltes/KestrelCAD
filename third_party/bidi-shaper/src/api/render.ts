/**
 * Public string-level API: the full logical→visual pipeline
 * (Arabic shaping → UAX #9 reordering → mirroring) plus the individual
 * stages for callers that need only one of them.
 *
 * All index-based results (levels, maps) are in CODE POINT space, not UTF-16
 * code unit space — astral characters count as one position.
 */
import { runBidi, toCodePoints, detectBaseDirection } from '../bidi/algorithm';
import type { BaseDirection, Direction } from '../bidi/types';
import { shapeCodePoints, shapeString, type ShapeOptions } from '../shape/shape';

export type { ShapeOptions };
export type { BaseDirection, Direction };

export interface RenderOptions extends ShapeOptions {
  /** Base paragraph direction. Default 'auto' (first-strong detection, P2/P3). */
  direction?: BaseDirection;
  /** Substitute Arabic presentation forms before reordering. Default true. */
  shape?: boolean;
  /** Replace mirrored characters (brackets etc.) on RTL runs (L4). Default true. */
  mirror?: boolean;
  /** 'split' reorders each \n / paragraph-separator chunk separately. Default 'split'. */
  paragraphs?: 'split' | 'single';
}

/** Detailed result of {@link analyze}. */
export interface AnalyzeResult {
  /** Shaped, visual-order string — what you pass to a renderer that draws left-to-right. */
  text: string;
  /** Resolved base direction of the first paragraph. */
  direction: Direction;
  /**
   * Resolved embedding level per input code point (odd = RTL). Code points
   * that do not survive to the output (stripped tashkeel, the alef of a
   * lam-alef ligature, explicit formatting characters) inherit the level of
   * the code point they attach to.
   */
  levels: Uint8Array;
  /** visualToLogical[v] = input code point index shown at visual position v. */
  visualToLogical: number[];
  /** logicalToVisual[i] = visual position of input code point i, or -1 if it was removed/merged. */
  logicalToVisual: Int32Array;
}

/** True when the text cannot need reordering, shaping, or mirroring. */
function isPlainLtr(cps: number[], direction: BaseDirection): boolean {
  if (direction === 'rtl') return false;
  for (let i = 0; i < cps.length; i++) {
    // 0x0590 is the first RTL code point; every RTL script, Arabic-shaped letter,
    // and explicit BiDi control lives at or above it.
    if (cps[i]! >= 0x0590) return false;
  }
  return true;
}

/**
 * One-call pipeline: shape Arabic letters, run the UBA, mirror brackets.
 * Returns the visual-order string ready for a naive left-to-right renderer.
 */
export function render(text: string, options?: RenderOptions): string {
  const direction = options?.direction ?? 'auto';
  const cps = toCodePoints(text);
  if (isPlainLtr(cps, direction)) return text;

  const logical = options?.shape !== false ? shapeCodePoints(cps, options).codePoints : cps;
  const { codePoints } = runBidi(logical, direction, {
    mirror: options?.mirror !== false,
    singleParagraph: options?.paragraphs === 'single',
  });
  let out = '';
  for (const cp of codePoints) out += String.fromCodePoint(cp);
  return out;
}

/**
 * Like {@link render}, but also returns the resolved direction, per-code-point
 * embedding levels, and visual↔logical index maps (for hit testing, cursor
 * placement, and selection mapping).
 */
export function analyze(text: string, options?: RenderOptions): AnalyzeResult {
  const direction = options?.direction ?? 'auto';
  const cps = toCodePoints(text);

  if (isPlainLtr(cps, direction)) {
    // All-ASCII text under an LTR/auto base provably resolves to level 0
    // everywhere (no R/AL/AN exists below 0x0590, and W7 turns EN into L),
    // so the output is the identity.
    const n = cps.length;
    const visualToLogical = new Array<number>(n);
    const logicalToVisual = new Int32Array(n);
    for (let i = 0; i < n; i++) {
      visualToLogical[i] = i;
      logicalToVisual[i] = i;
    }
    return { text, direction: 'ltr', levels: new Uint8Array(n), visualToLogical, logicalToVisual };
  }

  const shaped =
    options?.shape !== false
      ? shapeCodePoints(cps, options)
      : { codePoints: cps, src: cps.map((_, i) => i) };

  const bidi = runBidi(shaped.codePoints, direction, {
    mirror: options?.mirror !== false,
    singleParagraph: options?.paragraphs === 'single',
  });

  let out = '';
  for (const cp of bidi.codePoints) out += String.fromCodePoint(cp);

  // Map levels back onto the ORIGINAL code points; positions that were
  // stripped or merged inherit the level of their nearest preceding survivor.
  const levels = new Uint8Array(cps.length);
  const written = new Uint8Array(cps.length);
  for (let j = 0; j < shaped.codePoints.length; j++) {
    levels[shaped.src[j]!] = bidi.levels[j]!;
    written[shaped.src[j]!] = 1;
  }
  let lastLevel = 0;
  for (let i = 0; i < cps.length; i++) {
    if (written[i]) lastLevel = levels[i]!;
    else levels[i] = lastLevel;
  }

  const visualToLogical = bidi.map.map((j) => shaped.src[j]!);
  const logicalToVisual = new Int32Array(cps.length).fill(-1);
  for (let v = 0; v < visualToLogical.length; v++) logicalToVisual[visualToLogical[v]!] = v;

  return { text: out, direction: bidi.direction, levels, visualToLogical, logicalToVisual };
}

/** Arabic contextual shaping only (logical order in, logical order out). */
export function shape(text: string, options?: ShapeOptions): string {
  return shapeString(text, options);
}

/** UAX #9 reordering + mirroring only — no Arabic shaping. */
export function reorder(text: string, options?: Omit<RenderOptions, keyof ShapeOptions | 'shape'>): string {
  return render(text, { ...options, shape: false });
}

/**
 * Resolved embedding level per code point (after L1). Odd levels render RTL.
 */
export function getEmbeddingLevels(
  text: string,
  options?: Pick<RenderOptions, 'direction' | 'paragraphs'>,
): Uint8Array {
  const cps = toCodePoints(text);
  if (isPlainLtr(cps, options?.direction ?? 'auto')) return new Uint8Array(cps.length);
  return runBidi(cps, options?.direction ?? 'auto', {
    singleParagraph: options?.paragraphs === 'single',
  }).levels;
}

/** First-strong direction of the text (P2/P3), or 'neutral' if no strong character. */
export function detectDirection(text: string): Direction | 'neutral' {
  return detectBaseDirection(toCodePoints(text));
}
