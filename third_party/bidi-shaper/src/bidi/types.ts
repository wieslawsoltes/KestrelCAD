/**
 * Core BiDi types and the numeric Bidi_Class enumeration.
 *
 * The numeric order of {@link BC} MUST match BIDI_CLASS_NAMES in the generated
 * table (src/data/generated/bidi-classes.ts). A unit test asserts this.
 */

/** Numeric Bidi_Class codes (index into BIDI_CLASS_NAMES). */
export const BC = {
  L: 0,
  R: 1,
  AL: 2,
  EN: 3,
  ES: 4,
  ET: 5,
  AN: 6,
  CS: 7,
  NSM: 8,
  BN: 9,
  B: 10,
  S: 11,
  WS: 12,
  ON: 13,
  LRE: 14,
  LRO: 15,
  RLE: 16,
  RLO: 17,
  PDF: 18,
  LRI: 19,
  RLI: 20,
  FSI: 21,
  PDI: 22,
} as const;

/** A numeric Bidi_Class value, as found in {@link BC}. */
export type BidiClass = (typeof BC)[keyof typeof BC];

/** Numeric Joining_Type codes (index into JOINING_TYPE_NAMES). */
export const JT = {
  U: 0, // Non_Joining
  C: 1, // Join_Causing
  D: 2, // Dual_Joining
  L: 3, // Left_Joining
  R: 4, // Right_Joining
  T: 5, // Transparent
} as const;

/** A numeric Joining_Type value, as found in {@link JT}. */
export type JoiningType = (typeof JT)[keyof typeof JT];

/** Requested base paragraph direction. */
export type BaseDirection = 'auto' | 'ltr' | 'rtl';

/** A resolved, concrete direction. */
export type Direction = 'ltr' | 'rtl';

/** Maximum explicit embedding depth (UAX #9 BD2). */
export const MAX_DEPTH = 125;

/** Result of resolving a single paragraph's embedding levels. */
export interface ParagraphLevels {
  /** Resolved embedding level per character (before L1 line-level resets). */
  levels: Uint8Array;
  /** 1 where the character was removed by X9 (explicit formatting / BN). */
  removed: Uint8Array;
}
