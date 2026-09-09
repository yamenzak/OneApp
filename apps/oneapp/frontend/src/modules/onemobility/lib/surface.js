/**
 * The analytical surface, drawn as a field rather than as tiles.
 *
 * `geo.py` groups readings into a grid and averages inside each cell, and the
 * argument for that is about *what is measured*: MapLibre's own `heatmap` layer
 * renders kernel density, so a cell with two hundred readings averaging thirty
 * seconds late glows brighter than one with ten averaging ten minutes. Binning
 * first and averaging inside the bin is what makes the colour mean the measure.
 *
 * **That argument says nothing about the rendering, and the first version acted
 * as though it did.** Each cell went down as its own polygon, so an answer that
 * was correct about lateness looked like a spreadsheet laid over a city — and
 * the blockiness was reading as precision the data does not have. A cell
 * boundary is an artefact of where the grid happened to fall, not a place where
 * the network changes.
 *
 * So the bins stay and the edges go. The field is drawn into a small canvas at
 * one pixel per cell, smoothed, and handed to MapLibre as a canvas source with
 * linear resampling — the GPU interpolates it up to whatever the screen is,
 * which is exactly the soft falloff a heatmap is expected to have, off numbers
 * that still mean the mean.
 *
 * **Normalised convolution**, which is the part worth getting right. A plain
 * blur over a grid with holes in it drags every cell beside a hole towards
 * zero, so a genuinely late junction next to unsurveyed ground reads as less
 * late than it is. Blurring the weighted values and the weights separately and
 * dividing one by the other is Knutsson's method: a hole contributes nothing to
 * either sum, so the result is the mean of the neighbours that *are* there, and
 * the blurred weight becomes the alpha — a place nothing has been seen is
 * transparent rather than cool.
 */

/** How many readings a cell needs before it is drawn at full strength. */
const SOLID = 0.72

/** The faintest a cell with the fewest readings is drawn. */
const FAINTEST = 0.22

/**
 * The most cells across the canvas. A field wider than this is drawn at a
 * coarser step rather than allocating a bitmap nobody can see the detail in —
 * it is upscaled onto the screen either way.
 */
const MAX_SIDE = 480

/** One channel, blurred with a [1,2,1] kernel in each direction. */
function blur(values, cols, rows) {
  const wide = new Float32Array(values.length)
  for (let row = 0; row < rows; row += 1) {
    for (let col = 0; col < cols; col += 1) {
      const at = row * cols + col
      const left = col > 0 ? values[at - 1] : values[at]
      const right = col < cols - 1 ? values[at + 1] : values[at]
      wide[at] = (left + 2 * values[at] + right) / 4
    }
  }
  const tall = new Float32Array(values.length)
  for (let row = 0; row < rows; row += 1) {
    for (let col = 0; col < cols; col += 1) {
      const at = row * cols + col
      const up = row > 0 ? wide[at - cols] : wide[at]
      const down = row < rows - 1 ? wide[at + cols] : wide[at]
      tall[at] = (up + 2 * wide[at] + down) / 4
    }
  }
  return tall
}

/** `#rrggbb` to three numbers. Only ever fed the theme's own resolved inks. */
function channels(ink) {
  const hex = String(ink || '').trim()
  if (hex.startsWith('#') && hex.length === 7) {
    return [
      parseInt(hex.slice(1, 3), 16),
      parseInt(hex.slice(3, 5), 16),
      parseInt(hex.slice(5, 7), 16),
    ]
  }
  // `rgb(r, g, b)`, which is what `getComputedStyle` hands back for some tokens.
  const found = hex.match(/\d+/g)
  return found ? found.slice(0, 3).map(Number) : [128, 128, 128]
}

/**
 * A ramp evaluated at one point between 0 and 1.
 *
 * Interpolated in plain sRGB. Not because that is the right colour space — it
 * is not — but because the ramps here are already stepped through a perceptual
 * space by `palette.js`, and this only smooths *between* two steps that are
 * a fifth of the scale apart. The error over that distance is invisible, and
 * doing it properly would mean carrying a colour library into a per-pixel loop.
 */
function sample(ramp, at) {
  if (!ramp.length) return [128, 128, 128]
  if (ramp.length === 1) return ramp[0]
  const span = (ramp.length - 1) * Math.max(0, Math.min(1, at))
  const first = Math.min(ramp.length - 2, Math.floor(span))
  const k = span - first
  const from = ramp[first]
  const to = ramp[first + 1]
  return [
    from[0] + (to[0] - from[0]) * k,
    from[1] + (to[1] - from[1]) * k,
    from[2] + (to[2] - from[2]) * k,
  ]
}

/**
 * Paint one answer from `geo.surface` into `canvas`, and say where it goes.
 *
 * Returns the four corner coordinates a MapLibre canvas source wants, in its
 * order — top-left, top-right, bottom-right, bottom-left — or `null` when there
 * is nothing to draw.
 */
export function paintSurface(canvas, answer, inks) {
  const cells = answer?.cells || []
  if (!cells.length || !answer.size) return null

  const ramp = inks.map(channels)
  const span = (answer.high - answer.low) || 1
  const seen = (answer.busy - answer.quiet) || 1

  // Two cells of margin all round. One is not enough: the kernel reaches a
  // single cell, so with one the outermost row still carries weight when the
  // canvas ends and the whole field gets a rectangular edge — the hard boundary
  // back again, one cell further out. Two lets the falloff finish inside.
  let step = answer.size
  const margin = 2 * step
  const west = Math.min(...cells.map((one) => one.lon)) - margin
  const east = Math.max(...cells.map((one) => one.lon)) + margin
  const south = Math.min(...cells.map((one) => one.lat)) - margin
  const north = Math.max(...cells.map((one) => one.lat)) + margin

  const widest = Math.max((east - west) / step, (north - south) / step)
  if (widest > MAX_SIDE) step *= widest / MAX_SIDE

  const cols = Math.max(1, Math.ceil((east - west) / step))
  const rows = Math.max(1, Math.ceil((north - south) / step))

  const total = new Float32Array(cols * rows)
  const weight = new Float32Array(cols * rows)
  for (const one of cells) {
    const col = Math.min(cols - 1, Math.floor((one.lon - west) / step))
    // The canvas runs top to bottom and latitude runs the other way.
    const row = Math.min(rows - 1, Math.floor((north - one.lat) / step))
    const at = row * cols + col
    // How much has been seen here is how much this cell is worth, and it is the
    // same number twice: it weights the average against its neighbours and it
    // becomes the alpha. A mean over eight readings and a mean over eight
    // hundred are both averages and only one of them is worth acting on.
    const w = FAINTEST + (SOLID - FAINTEST)
      * Math.max(0, Math.min(1, (one.readings - answer.quiet) / seen))
    total[at] += one.value * w
    weight[at] += w
  }

  // Two passes, which is a kernel reaching two cells — the same distance as the
  // margin, so the field is fully faded by the time the canvas ends. The GPU's
  // linear resampling does the rest of the smoothing on the way to the screen.
  const smoothTotal = blur(blur(total, cols, rows), cols, rows)
  const smoothWeight = blur(blur(weight, cols, rows), cols, rows)

  // Alpha is relative to the busiest place in this answer, not absolute.
  //
  // The first version read it straight off the blurred weight and the whole
  // field came out a wash: a kernel spreads an isolated cell over nine, so
  // sparse coverage — which is most of a city — never got near solid. Scaling
  // to the peak is what a heatmap does and is honest for a *where* question:
  // the claim is that this place is worse than that one, and the range is on
  // the key.
  let peak = 0
  for (let at = 0; at < smoothWeight.length; at += 1) {
    if (smoothWeight[at] > peak) peak = smoothWeight[at]
  }
  peak = peak || 1

  canvas.width = cols
  canvas.height = rows
  const context = canvas.getContext('2d')
  const image = context.createImageData(cols, rows)
  for (let at = 0; at < cols * rows; at += 1) {
    const w = smoothWeight[at]
    if (w <= 0.0005) continue
    // Knutsson: the mean of the neighbours that are actually there, rather than
    // of the neighbourhood including the parts nobody has driven through.
    const mean = smoothTotal[at] / w
    const [red, green, blue] = sample(ramp, (mean - answer.low) / span)
    const out = at * 4
    image.data[out] = red
    image.data[out + 1] = green
    image.data[out + 2] = blue
    // The 0.65 lifts the middle of the range: linear alpha over a kernel-spread
    // weight leaves everything but the very busiest place looking like nothing.
    image.data[out + 3] = Math.round(255 * SOLID * Math.min(1, (w / peak) ** 0.65))
  }
  context.putImageData(image, 0, 0)

  return [
    [west, north],
    [east, north],
    [east, south],
    [west, south],
  ]
}
