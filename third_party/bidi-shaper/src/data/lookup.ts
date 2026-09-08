/**
 * Binary-search lookups over the committed, range-compressed Unicode tables.
 * These are the only functions that read the generated data; everything else
 * goes through here.
 */
import { BIDI_CLASS_RANGES } from './generated/bidi-classes';
import { MIRROR_PAIRS } from './generated/mirroring';
import {
  BRACKET_CANONICAL,
  BRACKET_CPS,
  BRACKET_PAIRS,
  BRACKET_TYPES,
} from './generated/brackets';
import { JOINING_GROUP_RANGES, JOINING_TYPE_RANGES } from './generated/joining-types';
import { LAM_ALEF, SHAPING_FORMS } from './generated/shaping-forms';

/** Binary search over flat [start, end, value] triples. Returns `def` if no range matches. */
function searchTriples(ranges: readonly number[], cp: number, def: number): number {
  let lo = 0;
  let hi = ranges.length / 3 - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const i = mid * 3;
    if (cp < ranges[i]!) hi = mid - 1;
    else if (cp > ranges[i + 1]!) lo = mid + 1;
    else return ranges[i + 2]!;
  }
  return def;
}

/** Binary search over flat [key, value] pairs. Returns 0 if absent. */
function searchPairs(pairs: readonly number[], cp: number): number {
  let lo = 0;
  let hi = pairs.length / 2 - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const key = pairs[mid * 2]!;
    if (cp < key) hi = mid - 1;
    else if (cp > key) lo = mid + 1;
    else return pairs[mid * 2 + 1]!;
  }
  return 0;
}

/** Resolved Bidi_Class index for a code point (default L = 0). */
export function getBidiClass(cp: number): number {
  return searchTriples(BIDI_CLASS_RANGES, cp, 0);
}

/** Joining_Type index for a code point (default U = 0). */
export function getJoiningType(cp: number): number {
  return searchTriples(JOINING_TYPE_RANGES, cp, 0);
}

/** Joining_Group index for a code point (default No_Joining_Group = 0). */
export function getJoiningGroup(cp: number): number {
  return searchTriples(JOINING_GROUP_RANGES, cp, 0);
}

/** Mirror code point for L4, or 0 if the character is not mirrored. */
export function getMirror(cp: number): number {
  return searchPairs(MIRROR_PAIRS, cp);
}

/** Index of `cp` within the bracket table, or -1 if it is not a paired bracket. */
function bracketIndex(cp: number): number {
  let lo = 0;
  let hi = BRACKET_CPS.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const v = BRACKET_CPS[mid]!;
    if (cp < v) hi = mid - 1;
    else if (cp > v) lo = mid + 1;
    else return mid;
  }
  return -1;
}

/** Bracket type: 0 = opening, 1 = closing, -1 = not a paired bracket. */
export function getBracketType(cp: number): number {
  const i = bracketIndex(cp);
  return i < 0 ? -1 : BRACKET_TYPES[i]!;
}

/** The paired (opposite) bracket for a paired-bracket code point, or 0 if none. */
export function getBracketPair(cp: number): number {
  const i = bracketIndex(cp);
  return i < 0 ? 0 : BRACKET_PAIRS[i]!;
}

/** Canonical representative of a bracket for BD16 equivalence matching. */
export function canonicalBracket(cp: number): number {
  for (let i = 0; i < BRACKET_CANONICAL.length; i += 2) {
    if (BRACKET_CANONICAL[i] === cp) return BRACKET_CANONICAL[i + 1]!;
  }
  return cp;
}

/** [isolated, initial, medial, final] presentation forms for a base letter (0 = none). */
export function getShapingForms(cp: number): readonly [number, number, number, number] | undefined {
  return SHAPING_FORMS[cp];
}

/** [isolated, final] lam-alef ligature for an alef variant, or undefined. */
export function getLamAlef(cp: number): readonly [number, number] | undefined {
  return LAM_ALEF[cp];
}
