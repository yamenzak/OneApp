/**
 * The drawn vehicle artwork, and how it becomes a map marker.
 *
 * Thirty-three top-view silhouettes, one SVG each, in `../art/`. They are
 * *source assets* rather than generated files: nothing in this repo produces
 * them, and the constraints they were drawn to are the contract this module
 * relies on —
 *
 *   `viewBox="0 0 40 40"`, nose towards -Y, symmetric about the vertical
 *   the body is exactly one path filled `#00FF00`
 *   every other part in a fixed neutral grey
 *   flat fills only: no gradients, filters, masks, text or external references
 *
 * `tests/test_marker_shapes.py` holds those rules, because every one of them is
 * something a well-meaning edit breaks silently: a second `#00FF00` and half
 * the vehicle stops carrying occupancy, a `<text>` element and the icon renders
 * differently on a machine without that font, a side elevation and the symbol
 * layer lays the bus on its side the moment it rotates.
 *
 * **Why the placeholder green.** MapLibre needs a raster image, and a raster
 * cannot be recoloured after the fact. So the fill is a token substituted in
 * the SVG *source* before it is rasterised, once per shape per occupancy band
 * at load — the same thing `markers.js` does by drawing on a canvas, with the
 * drawing done by somebody who can draw.
 *
 * **And why the drawn shapes are still here.** These read beautifully from
 * about thirty pixels up and are too narrow below it: at city zoom a marker is
 * twenty-two pixels on its long axis and eight across, and a detailed drawing
 * at that size is a tick. So the layer steps — `markers.js`'s squat silhouettes
 * hold the wide view, this takes over once a district fills the screen. That
 * was settled by rendering every shape at every size the map actually draws.
 */

import { bodyFor } from './markers'

/**
 * Every file in `../art/`, inlined at build time.
 *
 * Eager and raw rather than fetched: thirty-three files is thirty-three
 * requests on a screen that already makes four, and a `public/` path is one
 * more thing to get wrong behind a subpath. Together they are about 130 kB of
 * text, which gzips to very little.
 */
const FILES = import.meta.glob('../art/*.svg', { query: '?raw', import: 'default', eager: true })

/** `{ 'bus': '<svg…>' }`, keyed by the file's own name. */
export const ART = Object.fromEntries(
  Object.entries(FILES).map(([path, svg]) => [path.split('/').pop().replace('.svg', ''), svg]),
)

/**
 * The drawing for anything we cannot place: a plain van, unmistakably a vehicle
 * and unmistakably not a claim about which kind. The same one `markers.py`
 * falls to, and the two have to agree or a line renders as one thing on the map
 * and another in the key.
 */
export const FALLBACK = 'minibus'

/** Every shape there is, in the order the picker should read them. */
export const SHAPES = Object.keys(ART).sort()

/** The placeholder the artist leaves for us, and which we never draw. */
const BODY = /#00FF00/i

/**
 * Which of `markers.js`'s seven squat silhouettes stands in for each of these
 * at city zoom.
 *
 * Not a fallback for a missing drawing — every shape here has one — but a
 * *coarser* reading of it. Thirty-three outlines cannot be told apart at
 * twenty-two pixels, and pretending otherwise is how a map comes to look
 * detailed and say nothing.
 */
const COARSE = {
  metro: 'metro', 'light-rail': 'metro', monorail: 'metro',
  tram: 'tram', 'tram-old': 'tram', funicular: 'tram',
  train: 'rail', 'high-speed': 'rail', locomotive: 'rail',
  bus: 'bus', 'bus-articulated': 'bus', trolleybus: 'bus', coach: 'bus', shuttle: 'bus',
  ferry: 'ferry', ship: 'ferry', boat: 'ferry', sailing: 'ferry',
  'cable-car': 'cable', gondola: 'cable',
}

/** The squat silhouette a shape reads as when it is too small to draw properly. */
export function coarseFor(shape) {
  return bodyFor(COARSE[shape] || 'other')
}

/** Whether we have artwork for this name at all. */
export function drawn(shape) {
  return Object.prototype.hasOwnProperty.call(ART, shape)
}

/** One shape in one colour, as an `<img>`-ready data URL. */
export function artUrl(shape, fill) {
  const svg = ART[shape]
  if (!svg) return ''
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg.replace(BODY, fill))}`
}

/**
 * One shape in one colour, as pixels MapLibre will take.
 *
 * Async because rasterising an SVG means letting the browser lay it out, which
 * only an `Image` can do — `OffscreenCanvas` cannot parse SVG and neither can
 * `Path2D`. The whole set is thirty-three shapes across five occupancy bands,
 * so this runs once per (shape, band) actually on screen rather than for the
 * catalogue: registering all 165 up front is a second of main thread for
 * images a network of buses will never use.
 */
export function rasterise(shape, fill, size, ratio) {
  return new Promise((resolve, reject) => {
    const url = artUrl(shape, fill)
    if (!url) {
      reject(new Error(`no artwork for ${shape}`))
      return
    }
    const image = new Image()
    image.onload = () => {
      const side = Math.round(size * ratio)
      const pad = document.createElement('canvas')
      pad.width = side
      pad.height = side
      const context = pad.getContext('2d')
      context.drawImage(image, 0, 0, side, side)
      resolve({ width: side, height: side, data: context.getImageData(0, 0, side, side).data })
    }
    image.onerror = reject
    image.src = url
  })
}
