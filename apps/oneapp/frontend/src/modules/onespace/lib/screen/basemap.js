/**
 * The ground a map is drawn on.
 *
 * Two surfaces draw maps — the engine's map view type and OneMobility's live
 * network — and both need the same three answers: what is under the records,
 * who to credit for it, and what to do when there is no tile host at all. One
 * module rather than two copies, because the day an instance is pointed at its
 * own tile store is the day both have to agree.
 *
 * Where the answer comes from: `onespace/basemap.py`, on the boot payload.
 * Which tile store a bench uses is a deployment fact, not a workspace's choice.
 *
 * Raster and not a vector style URL, by default. A raster source is a URL
 * inside a style we own, so the style always parses and the map always fires
 * `load`; a style *URL* that 404s leaves MapLibre with no style, no `load`
 * event and a screen awaiting a promise that will never settle. A tile that
 * fails is one grey square. Given `style` in site config the operator has
 * chosen the other trade deliberately, and gets it.
 */

import { basemap as configured } from '@/shared/lib/runtime/boot'
import { paintable, tokenInk } from '@/modules/onespace/lib/screen/ink'

/** Is the board dark? Read off a token rather than a media query, because the
 *  workspace's own theme can say dark on a light system and the tiles should
 *  follow what is actually painted. */
export function isDark() {
  const ground = paintable(tokenInk('--surface-base', '#ffffff'), '#ffffff')
  const hex = ground.startsWith('#') ? ground.slice(1) : ''
  if (hex.length !== 6) return false
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16))
  // Rec. 709 luma. Anything below the midpoint is a dark surface.
  return 0.2126 * r + 0.7152 * g + 0.0722 * b < 128
}

/** Who to credit, for the attribution control. */
export function attribution() {
  return (configured?.attribution || '').trim()
}

/**
 * A MapLibre style: the configured one, or ours over the configured tiles, or
 * a flat ground when there are none.
 *
 * @param {string} background a paintable colour for the ground
 * @param {string} override a style URL that wins over everything, if given
 */
export function styleFor(background, override = '') {
  const url = String(override || configured?.style || '').trim()
  if (url) return url

  const tiles = String((isDark() ? configured?.dark : configured?.tiles) || '').trim()
  const style = {
    version: 8,
    sources: {},
    layers: [{ id: 'ground', type: 'background', paint: { 'background-color': background } }],
  }
  if (!tiles) return style

  style.sources.basemap = {
    type: 'raster',
    tiles: [tiles],
    tileSize: 256,
    attribution: attribution(),
  }
  // Under everything: `addLayer` without a `before` appends, so every layer a
  // surface adds afterwards lands on top of this without having to say so.
  style.layers.push({ id: 'basemap', type: 'raster', source: 'basemap' })
  return style
}

/**
 * Resolve when the map is ready, or when it plainly is not.
 *
 * `map.on('load')` fires once the style and its first tiles are in. It does
 * not fire at all if the style could not be fetched — a configured style URL
 * behind a firewall, an offline bench — and a screen awaiting it then shows
 * nothing for ever with no error anywhere. Worse, `addSource` on a map with no
 * style throws, so simply carrying on is not enough.
 *
 * So: wait, and if the style never arrived, put the flat ground on instead and
 * wait for that. Whatever else is wrong, the records get drawn.
 */
export function whenLoaded(map, background, within = 8000) {
  const once = (span) =>
    new Promise((resolve) => {
      let done = false
      const settle = () => {
        if (done) return
        done = true
        resolve()
      }
      if (map.isStyleLoaded?.()) return settle()
      map.on('load', settle)
      map.on('idle', settle)
      setTimeout(settle, span)
    })

  return once(within).then(() => {
    if (map.isStyleLoaded?.()) return undefined
    map.setStyle({
      version: 8,
      sources: {},
      layers: [{ id: 'ground', type: 'background', paint: { 'background-color': background } }],
    })
    return once(3000)
  })
}

/**
 * Stop a basemap that cannot be reached from shouting about it.
 *
 * MapLibre reports every failed tile to the console as an error, one per tile,
 * a fresh dozen on every pan. On a workspace behind a firewall, on a bench with
 * no route out, or on the day the tile host is having a bad afternoon, that is
 * a console full of red for something the map already handles: the ground is
 * blank and every record is still drawn on it.
 *
 * Only the ground is quietened. An error about a source or a layer we added is
 * ours and still surfaces, because that one means the screen is wrong.
 */
export function quietTiles(map) {
  map.on('error', (event) => {
    const source = event?.sourceId
    if (source === 'basemap' || event?.error?.status === 404) return
    // eslint-disable-next-line no-console
    console.error(event?.error || event)
  })
}
