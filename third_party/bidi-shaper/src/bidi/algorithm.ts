/**
 * Top-level UAX #9 orchestration over code-point arrays:
 *   P1 paragraph splitting, P2/P3 base direction, then per-paragraph
 *   level resolution (levels.ts) and reordering/mirroring (reorder.ts).
 *
 * Works purely in code points (surrogate pairs already decoded), so the public
 * string API just decodes in and encodes out.
 */
import { BC, type BaseDirection, type Direction } from './types';
import { computeBaseLevel, resolveParagraph } from './levels';
import { applyL1, reorderIndices } from './reorder';
import { getBidiClass, getMirror } from '../data/lookup';

/** Classify each code point into its numeric Bidi_Class. */
export function classify(codePoints: ArrayLike<number>): Uint8Array {
  const types = new Uint8Array(codePoints.length);
  for (let i = 0; i < codePoints.length; i++) types[i] = getBidiClass(codePoints[i]!);
  return types;
}

/** Decode a string into an array of code points (handles surrogate pairs). */
export function toCodePoints(text: string): number[] {
  const out: number[] = [];
  for (const ch of text) out.push(ch.codePointAt(0)!);
  return out;
}

/** P1 — split a paragraph's type array into [start, end) ranges, each ending after a B. */
function splitParagraphs(types: Uint8Array): Array<[number, number]> {
  const segs: Array<[number, number]> = [];
  let start = 0;
  for (let i = 0; i < types.length; i++) {
    if (types[i] === BC.B) {
      segs.push([start, i + 1]);
      start = i + 1;
    }
  }
  if (start < types.length || segs.length === 0) segs.push([start, types.length]);
  return segs;
}

/** Resolve the paragraph embedding level for a (sub)range under a requested base. */
function paragraphLevelFor(types: Uint8Array, start: number, end: number, base: BaseDirection): number {
  if (base === 'ltr') return 0;
  if (base === 'rtl') return 1;
  return computeBaseLevel(types, start, end);
}

/** Options for {@link runBidi}. */
export interface BidiOptions {
  /** Treat the whole input as one paragraph even across B separators. Default false. */
  singleParagraph?: boolean;
  /** Apply L4 character mirroring on odd levels. Default true. */
  mirror?: boolean;
}

/** Detailed result of a full BiDi pass over logical-order code points. */
export interface BidiResult {
  /** Visual-order code points (X9-removed formatting characters dropped). */
  codePoints: number[];
  /** map[v] = logical index (into the input) of visual code point v. */
  map: number[];
  /** Resolved embedding level per logical code point, after L1. */
  levels: Uint8Array;
  /** Resolved base direction of the first paragraph. */
  direction: Direction;
}

/**
 * Full BiDi: logical-order code points -> visual-order code points with the
 * visual-to-logical map and resolved levels (L1 applied, L4 mirroring
 * optional). Explicit formatting characters removed by X9 are dropped from
 * the visual output but keep their level in `levels`.
 */
export function runBidi(
  codePoints: ArrayLike<number>,
  base: BaseDirection,
  options?: BidiOptions,
): BidiResult {
  const mirror = options?.mirror !== false;
  const types = classify(codePoints);
  const all = Int32Array.from(codePoints as ArrayLike<number>);
  const n = all.length;
  const segments = options?.singleParagraph ? [[0, n] as [number, number]] : splitParagraphs(types);

  const visual: number[] = [];
  const map: number[] = [];
  const allLevels = new Uint8Array(n);
  let direction: Direction | null = null;

  for (const [s, e] of segments) {
    if (s === e) continue;
    // Keep the trailing paragraph separator (\n etc.) at its logical position
    // instead of letting L2 reverse it to the front of an RTL line — a string
    // API must preserve line structure for downstream consumers.
    const hasSep = !options?.singleParagraph && types[e - 1] === BC.B;
    const contentEnd = hasSep ? e - 1 : e;
    const paraLevel = paragraphLevelFor(types, s, e, base);
    if (direction === null) direction = paraLevel === 1 ? 'rtl' : 'ltr';

    if (s < contentEnd) {
      const segTypes = types.subarray(s, contentEnd);
      const segCps = all.subarray(s, contentEnd);
      const { levels, removed } = resolveParagraph(segTypes, segCps, paraLevel);
      applyL1(segTypes, levels, removed, paraLevel);
      allLevels.set(levels, s);
      for (const idx of reorderIndices(levels, removed)) {
        let cp = segCps[idx]!;
        if (mirror && (levels[idx]! & 1) === 1) {
          const m = getMirror(cp);
          if (m !== 0) cp = m;
        }
        visual.push(cp);
        map.push(s + idx);
      }
    }
    if (hasSep) {
      allLevels[e - 1] = paraLevel;
      visual.push(all[e - 1]!);
      map.push(e - 1);
    }
  }

  return {
    codePoints: visual,
    map,
    levels: allLevels,
    direction: direction ?? (base === 'rtl' ? 'rtl' : 'ltr'),
  };
}

/** First-strong base direction over the whole text (P2/P3), or 'neutral' if none. */
export function detectBaseDirection(codePoints: number[]): 'ltr' | 'rtl' | 'neutral' {
  const types = classify(codePoints);
  let isolateDepth = 0;
  for (let i = 0; i < types.length; i++) {
    const t = types[i]!;
    if (t === BC.LRI || t === BC.RLI || t === BC.FSI) {
      isolateDepth++;
    } else if (t === BC.PDI) {
      if (isolateDepth > 0) isolateDepth--;
    } else if (isolateDepth === 0) {
      if (t === BC.L) return 'ltr';
      if (t === BC.R || t === BC.AL) return 'rtl';
    }
  }
  return 'neutral';
}

/**
 * Conformance-only entry point for BidiTest.txt, which provides Bidi_Class
 * tokens directly (no code points, no brackets). Returns resolved levels with
 * `removed` flags and the L2 visual order of non-removed indices.
 */
export function resolveByTypes(
  types: Uint8Array,
  paraLevel: number,
): { levels: Uint8Array; removed: Uint8Array; order: number[] } {
  const { levels, removed } = resolveParagraph(types, null, paraLevel);
  applyL1(types, levels, removed, paraLevel);
  const order = reorderIndices(levels, removed);
  return { levels, removed, order };
}

/** P2/P3 base level for a full type array (used by the conformance harness for auto). */
export function baseLevelForTypes(types: Uint8Array): 0 | 1 {
  return computeBaseLevel(types, 0, types.length);
}
