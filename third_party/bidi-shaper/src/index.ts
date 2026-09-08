/**
 * bidi-shaper — logical→visual Unicode BiDi (UAX #9) reordering and Arabic
 * contextual shaping for renderers that draw text naively left-to-right
 * (PDF generators, canvas rasterizers, WebGL/three.js, terminals, games).
 *
 * Quick start:
 *   import { render } from 'bidi-shaper';
 *   doc.text(render('مرحبا بالعالم'), x, y);
 */
export {
  render,
  analyze,
  shape,
  reorder,
  getEmbeddingLevels,
  detectDirection,
  type AnalyzeResult,
  type RenderOptions,
  type ShapeOptions,
  type BaseDirection,
  type Direction,
} from './api/render';

export { UNICODE_VERSION } from './data/generated/version';
