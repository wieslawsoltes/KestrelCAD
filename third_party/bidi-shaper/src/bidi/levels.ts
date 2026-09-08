/**
 * UAX #9 level resolution for a single paragraph:
 *   - P2/P3   base direction of a (sub)range
 *   - X1–X10  explicit embeddings, overrides, isolates, isolating run sequences
 *   - W1–W7   weak type resolution
 *   - N0–N2   neutral & bracket-pair resolution (BD16)
 *   - I1–I2   implicit level resolution
 *
 * L1/L2/L4 (line-level resets, reordering, mirroring) live in reorder.ts.
 */
import { BC, MAX_DEPTH, type ParagraphLevels } from './types';
import { canonicalBracket, getBracketPair, getBracketType } from '../data/lookup';

/** Least odd level strictly greater than `level`. */
function leastGreaterOdd(level: number): number {
  return (level & 1) === 0 ? level + 1 : level + 2;
}

/** Least even level strictly greater than `level`. */
function leastGreaterEven(level: number): number {
  return (level & 1) === 0 ? level + 2 : level + 1;
}

/**
 * P2/P3 — the base embedding level of types[start, end), found from the first
 * strong character, skipping any text between an isolate initiator and its
 * matching PDI. Returns 0 (LTR) when no strong character is present.
 */
export function computeBaseLevel(types: Uint8Array, start: number, end: number): 0 | 1 {
  let isolateDepth = 0;
  for (let i = start; i < end; i++) {
    const t = types[i]!;
    if (t === BC.LRI || t === BC.RLI || t === BC.FSI) {
      isolateDepth++;
    } else if (t === BC.PDI) {
      if (isolateDepth > 0) isolateDepth--;
    } else if (isolateDepth === 0) {
      if (t === BC.L) return 0;
      if (t === BC.R || t === BC.AL) return 1;
    }
  }
  return 0;
}

/** BD9 — match each isolate initiator with its PDI (purely structural). */
function computeMatching(types: Uint8Array): { matchPDI: Int32Array; matchInit: Int32Array } {
  const n = types.length;
  const matchPDI = new Int32Array(n).fill(-1);
  const matchInit = new Int32Array(n).fill(-1);
  const stack: number[] = [];
  for (let i = 0; i < n; i++) {
    const t = types[i]!;
    if (t === BC.LRI || t === BC.RLI || t === BC.FSI) {
      stack.push(i);
    } else if (t === BC.PDI && stack.length > 0) {
      const open = stack.pop()!;
      matchPDI[open] = i;
      matchInit[i] = open;
    }
  }
  return { matchPDI, matchInit };
}

/** Sentinel for "no directional override" (cannot be 0, since BC.L === 0). */
const NEUTRAL = -1;
/** Sentinel for "no strong direction" returned by {@link dirOf}. */
const NO_DIR = -1;

interface StatusEntry {
  level: number;
  override: number; // NEUTRAL, BC.L, or BC.R
  isolate: boolean;
}

/** Map a resolved type to its strong direction for N0/N1 (EN, AN count as R). */
function dirOf(t: number): number {
  if (t === BC.L) return BC.L;
  if (t === BC.R || t === BC.EN || t === BC.AN) return BC.R;
  return NO_DIR;
}

/** NI = neutral or isolate-formatting character (the set resolved by N1/N2). */
function isNI(t: number): boolean {
  return (
    t === BC.B ||
    t === BC.S ||
    t === BC.WS ||
    t === BC.ON ||
    t === BC.FSI ||
    t === BC.LRI ||
    t === BC.RLI ||
    t === BC.PDI
  );
}

/**
 * Resolve embedding levels for one paragraph.
 *
 * @param origTypes  Bidi_Class per character (paragraph-local).
 * @param codePoints Code points (for N0 bracket pairing), or null to skip N0
 *                   — used by the BidiTest conformance harness which has no brackets.
 * @param paraLevel  Resolved paragraph embedding level (0 or 1).
 */
export function resolveParagraph(
  origTypes: Uint8Array,
  codePoints: Int32Array | null,
  paraLevel: number,
): ParagraphLevels {
  const n = origTypes.length;
  const levels = new Uint8Array(n);
  const types = Uint8Array.from(origTypes); // working types (mutated by X/W/N)
  const removed = new Uint8Array(n);

  if (n === 0) return { levels, removed };

  const { matchPDI } = computeMatching(origTypes);

  // ----- X1–X8: explicit levels, overrides, isolates -----
  const stack: StatusEntry[] = [{ level: paraLevel, override: NEUTRAL, isolate: false }];
  let overflowIsolate = 0;
  let overflowEmbedding = 0;
  let validIsolate = 0;
  const top = (): StatusEntry => stack[stack.length - 1]!;

  for (let i = 0; i < n; i++) {
    const t = origTypes[i]!;
    switch (t) {
      case BC.RLE:
      case BC.LRE:
      case BC.RLO:
      case BC.LRO: {
        levels[i] = top().level;
        removed[i] = 1;
        const isRTL = t === BC.RLE || t === BC.RLO;
        const newLevel = isRTL ? leastGreaterOdd(top().level) : leastGreaterEven(top().level);
        const override = t === BC.RLO ? BC.R : t === BC.LRO ? BC.L : NEUTRAL;
        if (newLevel <= MAX_DEPTH && overflowIsolate === 0 && overflowEmbedding === 0) {
          stack.push({ level: newLevel, override, isolate: false });
        } else if (overflowIsolate === 0) {
          overflowEmbedding++;
        }
        break;
      }
      case BC.RLI:
      case BC.LRI:
      case BC.FSI: {
        levels[i] = top().level;
        if (top().override !== NEUTRAL) types[i] = top().override;
        let isRTL: boolean;
        if (t === BC.FSI) {
          const innerEnd = matchPDI[i] === -1 ? n : matchPDI[i]!;
          isRTL = computeBaseLevel(origTypes, i + 1, innerEnd) === 1;
        } else {
          isRTL = t === BC.RLI;
        }
        const newLevel = isRTL ? leastGreaterOdd(top().level) : leastGreaterEven(top().level);
        if (newLevel <= MAX_DEPTH && overflowIsolate === 0 && overflowEmbedding === 0) {
          validIsolate++;
          stack.push({ level: newLevel, override: NEUTRAL, isolate: true });
        } else {
          overflowIsolate++;
        }
        break;
      }
      case BC.PDI: {
        if (overflowIsolate > 0) {
          overflowIsolate--;
        } else if (validIsolate > 0) {
          overflowEmbedding = 0;
          while (!top().isolate) stack.pop();
          stack.pop();
          validIsolate--;
        }
        levels[i] = top().level;
        if (top().override !== NEUTRAL) types[i] = top().override;
        break;
      }
      case BC.PDF: {
        levels[i] = top().level;
        removed[i] = 1;
        if (overflowIsolate > 0) {
          // ignore
        } else if (overflowEmbedding > 0) {
          overflowEmbedding--;
        } else if (!top().isolate && stack.length >= 2) {
          stack.pop();
        }
        levels[i] = top().level;
        break;
      }
      case BC.B: {
        // X8 — paragraph separator: terminates all embeddings, gets paragraph level.
        levels[i] = paraLevel;
        break;
      }
      case BC.BN: {
        levels[i] = top().level;
        removed[i] = 1;
        break;
      }
      default: {
        levels[i] = top().level;
        if (top().override !== NEUTRAL) types[i] = top().override;
        break;
      }
    }
  }

  // ----- X10: build isolating run sequences (BD13) -----
  const sequences = buildIsolatingRunSequences(origTypes, levels, removed, matchPDI);

  // Snapshot the X embedding levels. sos/eos and the I rules must read these
  // pristine levels, not the implicit levels we write back during the loop.
  const embLevels = Uint8Array.from(levels);

  // ----- per-sequence W / N / I -----
  for (const seq of sequences) {
    resolveSequence(seq, origTypes, types, levels, embLevels, removed, paraLevel, matchPDI, codePoints);
  }

  return { levels, removed };
}

/** BD13 — group non-removed level runs into isolating run sequences. */
function buildIsolatingRunSequences(
  origTypes: Uint8Array,
  levels: Uint8Array,
  removed: Uint8Array,
  matchPDI: Int32Array,
): number[][] {
  const n = origTypes.length;

  // Level runs over the non-removed characters.
  const runs: number[][] = [];
  let cur: number[] = [];
  for (let i = 0; i < n; i++) {
    if (removed[i]) continue;
    if (cur.length === 0 || levels[i] === levels[cur[cur.length - 1]!]) {
      cur.push(i);
    } else {
      runs.push(cur);
      cur = [i];
    }
  }
  if (cur.length) runs.push(cur);

  const runStartingAt = new Map<number, number>();
  runs.forEach((r, ri) => runStartingAt.set(r[0]!, ri));

  const sequences: number[][] = [];
  for (let ri = 0; ri < runs.length; ri++) {
    const first = runs[ri]![0]!;
    // A run that begins with a PDI matching some initiator is a continuation.
    if (origTypes[first] === BC.PDI && matchedInitiatorExists(origTypes, levels, removed, first)) {
      continue;
    }
    let seq: number[] = [];
    let curRi: number | undefined = ri;
    while (curRi !== undefined) {
      const run = runs[curRi]!;
      seq = seq.concat(run);
      const last = run[run.length - 1]!;
      const lt = origTypes[last]!;
      if ((lt === BC.LRI || lt === BC.RLI || lt === BC.FSI) && matchPDI[last]! >= 0) {
        curRi = runStartingAt.get(matchPDI[last]!);
      } else {
        curRi = undefined;
      }
    }
    sequences.push(seq);
  }
  return sequences;
}

/** Whether a PDI at `pos` is matched by an initiator (used to detect continuations). */
function matchedInitiatorExists(
  types: Uint8Array,
  _levels: Uint8Array,
  _removed: Uint8Array,
  pos: number,
): boolean {
  // Re-derive via structural matching scan up to pos.
  let depth = 0;
  let lastInitiator = -1;
  for (let i = 0; i < pos; i++) {
    const t = types[i]!;
    if (t === BC.LRI || t === BC.RLI || t === BC.FSI) {
      depth++;
      lastInitiator = i;
    } else if (t === BC.PDI && depth > 0) {
      depth--;
    }
  }
  return depth > 0 && lastInitiator >= 0;
}

/** Run W1–W7, N0–N2, I1–I2 over one isolating run sequence. */
function resolveSequence(
  seq: number[],
  origTypes: Uint8Array,
  types: Uint8Array,
  levels: Uint8Array,
  embLevels: Uint8Array,
  removed: Uint8Array,
  paraLevel: number,
  matchPDI: Int32Array,
  codePoints: Int32Array | null,
): void {
  const len = seq.length;
  if (len === 0) return;
  const n = origTypes.length;
  const seqLevel = embLevels[seq[0]!]!;
  const e = (seqLevel & 1) === 1 ? BC.R : BC.L; // embedding direction
  const o = e === BC.L ? BC.R : BC.L; // opposite direction

  // sos: higher of seqLevel and the level of the preceding non-removed char.
  let prevLevel = paraLevel;
  for (let i = seq[0]! - 1; i >= 0; i--) {
    if (!removed[i]) {
      prevLevel = embLevels[i]!;
      break;
    }
  }
  const sos: number = (Math.max(seqLevel, prevLevel) & 1) === 1 ? BC.R : BC.L;

  // eos: higher of seqLevel and the following non-removed char (or paragraph
  // level if none, or if the sequence ends in an unmatched isolate initiator).
  const lastIdx = seq[len - 1]!;
  const lastType = origTypes[lastIdx]!;
  let eos: number;
  if ((lastType === BC.LRI || lastType === BC.RLI || lastType === BC.FSI) && matchPDI[lastIdx] === -1) {
    eos = (Math.max(seqLevel, paraLevel) & 1) === 1 ? BC.R : BC.L;
  } else {
    let nextLevel = paraLevel;
    for (let i = lastIdx + 1; i < n; i++) {
      if (!removed[i]) {
        nextLevel = embLevels[i]!;
        break;
      }
    }
    eos = (Math.max(seqLevel, nextLevel) & 1) === 1 ? BC.R : BC.L;
  }

  const at = (k: number): number => types[seq[k]!]!;
  const set = (k: number, v: number): void => {
    types[seq[k]!] = v;
  };

  // ----- W1: NSM -> type of previous char (ON after isolate initiator/PDI) -----
  let prevType: number = sos;
  for (let k = 0; k < len; k++) {
    const t = at(k);
    if (t === BC.NSM) {
      const resolved =
        prevType === BC.LRI || prevType === BC.RLI || prevType === BC.FSI || prevType === BC.PDI
          ? BC.ON
          : prevType;
      set(k, resolved);
      prevType = resolved;
    } else {
      prevType = t;
    }
  }

  // ----- W2: EN -> AN when the last strong type is AL -----
  let strong: number = sos;
  for (let k = 0; k < len; k++) {
    const t = at(k);
    if (t === BC.EN && strong === BC.AL) set(k, BC.AN);
    if (t === BC.L || t === BC.R || t === BC.AL) strong = t;
  }

  // ----- W3: AL -> R -----
  for (let k = 0; k < len; k++) {
    if (at(k) === BC.AL) set(k, BC.R);
  }

  // ----- W4: single ES between EN, single CS between matching numbers -----
  const snapshot = new Int32Array(len);
  for (let k = 0; k < len; k++) snapshot[k] = at(k);
  for (let k = 1; k < len - 1; k++) {
    const t = snapshot[k]!;
    const prev = snapshot[k - 1]!;
    const next = snapshot[k + 1]!;
    if (t === BC.ES && prev === BC.EN && next === BC.EN) set(k, BC.EN);
    else if (t === BC.CS && prev === BC.EN && next === BC.EN) set(k, BC.EN);
    else if (t === BC.CS && prev === BC.AN && next === BC.AN) set(k, BC.AN);
  }

  // ----- W5: ET runs adjacent to EN -> EN -----
  for (let k = 0; k < len; ) {
    if (at(k) === BC.ET) {
      let j = k;
      while (j < len && at(j) === BC.ET) j++;
      const before = k > 0 ? at(k - 1) : sos;
      const after = j < len ? at(j) : eos;
      if (before === BC.EN || after === BC.EN) {
        for (let m = k; m < j; m++) set(m, BC.EN);
      }
      k = j;
    } else {
      k++;
    }
  }

  // ----- W6: remaining separators/terminators -> ON -----
  for (let k = 0; k < len; k++) {
    const t = at(k);
    if (t === BC.ES || t === BC.ET || t === BC.CS) set(k, BC.ON);
  }

  // ----- W7: EN -> L when the last strong type is L -----
  strong = sos;
  for (let k = 0; k < len; k++) {
    const t = at(k);
    if (t === BC.EN && strong === BC.L) set(k, BC.L);
    if (t === BC.L || t === BC.R) strong = t;
  }

  // ----- N0: paired brackets (needs code points) -----
  if (codePoints) {
    resolveBrackets(seq, origTypes, types, codePoints, e, o, sos);
  }

  // ----- N1: NI between strongs of the same direction -> that direction -----
  for (let k = 0; k < len; ) {
    if (isNI(at(k))) {
      let j = k;
      while (j < len && isNI(at(j))) j++;
      const before = k > 0 ? dirOf(at(k - 1)) : sos;
      const after = j < len ? dirOf(at(j)) : eos;
      if (before === after && (before === BC.L || before === BC.R)) {
        for (let m = k; m < j; m++) set(m, before);
      }
      k = j;
    } else {
      k++;
    }
  }

  // ----- N2: remaining NI -> embedding direction -----
  for (let k = 0; k < len; k++) {
    if (isNI(at(k))) set(k, e);
  }

  // ----- I1/I2: implicit levels (base = pristine X embedding level) -----
  for (let k = 0; k < len; k++) {
    const idx = seq[k]!;
    const lvl = embLevels[idx]!;
    const t = types[idx]!;
    if ((lvl & 1) === 0) {
      if (t === BC.R) levels[idx] = lvl + 1;
      else if (t === BC.AN || t === BC.EN) levels[idx] = lvl + 2;
    } else if (t === BC.L || t === BC.EN || t === BC.AN) {
      levels[idx] = lvl + 1;
    }
  }
}

/** N0 + BD16 — resolve paired brackets within an isolating run sequence. */
function resolveBrackets(
  seq: number[],
  origTypes: Uint8Array,
  types: Uint8Array,
  codePoints: Int32Array,
  e: number,
  o: number,
  sos: number,
): void {
  const len = seq.length;
  const at = (k: number): number => types[seq[k]!]!;

  // BD16: identify bracket pairs (stack of up to 63 opening brackets).
  const openStack: Array<{ canon: number; k: number }> = [];
  const pairs: Array<[number, number]> = [];
  for (let k = 0; k < len; k++) {
    const idx = seq[k]!;
    if (types[idx] !== BC.ON) continue;
    const cp = codePoints[idx]!;
    const bt = getBracketType(cp);
    if (bt === 0) {
      if (openStack.length === 63) break;
      openStack.push({ canon: canonicalBracket(getBracketPair(cp)), k });
    } else if (bt === 1) {
      const cc = canonicalBracket(cp);
      for (let s = openStack.length - 1; s >= 0; s--) {
        if (openStack[s]!.canon === cc) {
          pairs.push([openStack[s]!.k, k]);
          openStack.length = s;
          break;
        }
      }
    }
  }
  pairs.sort((a, b) => a[0] - b[0]);

  const setBracketNSM = (k: number, dir: number): void => {
    // N0 trailing note: characters that were originally NSM and immediately
    // follow a resolved bracket take the bracket's direction.
    for (let m = k + 1; m < len && origTypes[seq[m]!] === BC.NSM; m++) {
      types[seq[m]!] = dir;
    }
  };

  for (const [openK, closeK] of pairs) {
    let foundE = false;
    let foundO = false;
    for (let m = openK + 1; m < closeK; m++) {
      const d = dirOf(at(m));
      if (d === e) {
        foundE = true;
        break;
      }
      if (d === o) foundO = true;
    }

    let dir = NO_DIR;
    if (foundE) {
      dir = e;
    } else if (foundO) {
      // Establish context from the strong type preceding the opening bracket.
      let ctx = sos;
      for (let m = openK - 1; m >= 0; m--) {
        const d = dirOf(at(m));
        if (d !== NO_DIR) {
          ctx = d;
          break;
        }
      }
      dir = ctx === o ? o : e;
    }

    if (dir !== NO_DIR) {
      types[seq[openK]!] = dir;
      types[seq[closeK]!] = dir;
      setBracketNSM(openK, dir);
      setBracketNSM(closeK, dir);
    }
  }
}
