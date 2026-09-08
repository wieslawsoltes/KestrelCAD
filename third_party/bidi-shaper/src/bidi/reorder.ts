/**
 * UAX #9 line-level rules:
 *   - L1  reset separators and trailing whitespace/isolates to the paragraph level
 *   - L2  reverse contiguous runs from the highest level down to the lowest odd level
 *
 * (L4 mirroring is applied during visual emission in algorithm.ts.)
 * We treat each paragraph as a single line (no line breaking), which is the
 * correct behaviour for a string-in/string-out shaper.
 */
import { BC } from './types';

/** True for characters reset by L1's trailing-sequence clause (original types). */
function isResettable(origTypes: Uint8Array, removed: Uint8Array, i: number): boolean {
  if (removed[i]) return true; // BN / explicit formatting — transparent to the scan
  const t = origTypes[i]!;
  return t === BC.WS || t === BC.LRI || t === BC.RLI || t === BC.FSI || t === BC.PDI;
}

/**
 * L1 — reset embedding levels in place. Uses ORIGINAL types (per the rule's note),
 * not the W/N-resolved ones.
 */
export function applyL1(
  origTypes: Uint8Array,
  levels: Uint8Array,
  removed: Uint8Array,
  paraLevel: number,
): void {
  const n = origTypes.length;

  // Trailing whitespace / isolate formatting at the end of the line.
  let i = n - 1;
  while (i >= 0 && isResettable(origTypes, removed, i)) {
    levels[i] = paraLevel;
    i--;
  }

  // Segment and paragraph separators, plus any whitespace/isolate run before them.
  for (let j = 0; j < n; j++) {
    const t = origTypes[j]!;
    if (t === BC.B || t === BC.S) {
      levels[j] = paraLevel;
      let k = j - 1;
      while (k >= 0 && isResettable(origTypes, removed, k)) {
        levels[k] = paraLevel;
        k--;
      }
    }
  }
}

/** Reverse `arr[from..to]` in place (inclusive). */
function reverseRange(arr: number[], from: number, to: number): void {
  while (from < to) {
    const tmp = arr[from]!;
    arr[from] = arr[to]!;
    arr[to] = tmp;
    from++;
    to--;
  }
}

/**
 * L2 — return the visual order of non-removed character indices.
 * Removed (X9) characters are dropped from the output entirely.
 */
export function reorderIndices(levels: Uint8Array, removed: Uint8Array): number[] {
  const order: number[] = [];
  for (let i = 0; i < levels.length; i++) {
    if (!removed[i]) order.push(i);
  }
  if (order.length === 0) return order;

  let maxLevel = 0;
  let minOdd = Number.MAX_SAFE_INTEGER;
  for (const i of order) {
    const l = levels[i]!;
    if (l > maxLevel) maxLevel = l;
    if ((l & 1) === 1 && l < minOdd) minOdd = l;
  }
  if (minOdd === Number.MAX_SAFE_INTEGER) return order; // all even -> no reversal

  for (let level = maxLevel; level >= minOdd; level--) {
    let s = 0;
    while (s < order.length) {
      if (levels[order[s]!]! >= level) {
        let eIdx = s;
        while (eIdx < order.length && levels[order[eIdx]!]! >= level) eIdx++;
        reverseRange(order, s, eIdx - 1);
        s = eIdx;
      } else {
        s++;
      }
    }
  }
  return order;
}
