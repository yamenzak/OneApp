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
 * **Vector, and that is what makes the map customisable at all.** A raster tile
 * is a picture somebody else already drew: the only thing a reader can change
 * about it is what goes on top. A vector style is JSON the browser executes, so
 * whether places are named and how much of the world is drawn under the records
 * are properties on layers — `restyle` below sets them on the running map, with
 * no reload and no second tile store.
 *
 * The old note, kept because the trade it describes is still real:
 * raster and not a vector style URL, by default. A raster source is a URL
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

/**
 * What this workspace has said about its ground: whether to name places, and
 * how much to draw. Read from the boot payload, so a surface that has no picker
 * still honours the choice made on one that has.
 */
export function preferred() {
  return {
    pick: configured?.pick || 'Follow the instance',
    labels: configured?.labels !== false,
    detail: configured?.detail || 'Quiet',
  }
}

/**
 * Who to credit, for the attribution control — and usually nobody, now.
 *
 * A vector style names a TileJSON, and that document carries the full linked
 * attribution the licence wants. MapLibre reads it and draws it, so anything we
 * add sits *beside* it: the first version of this stacked two credits into one
 * line that said the same thing twice, once less completely. So the server
 * sends one only where there is no document to read it out of — a raster
 * template — or where an operator has named their own.
 */
export function attribution() {
  return (configured?.attribution || '').trim()
}

/** A style with nothing in it but a colour. Ours, so it always parses. */
export function flatGround(background) {
  return {
    version: 8,
    sources: {},
    layers: [{ id: 'ground', type: 'background', paint: { 'background-color': background } }],
  }
}

/**
 * A MapLibre style: the configured one, or ours over the configured tiles, or
 * a flat ground when there are none.
 *
 * @param {string} background a paintable colour for the ground
 * @param {string} override a style URL that wins over everything, or one of two
 *   words. An empty string is "I have no opinion", so a caller that has decided
 *   something cannot say it that way: `'none'` is a flat ground on purpose, and
 *   `'instance'` is what the *instance* configured, ignoring the workspace pick
 *   that `style` on the payload already has baked into it. A picker needs both,
 *   because after it has been used the payload describes the morning.
 */
export function styleFor(background, override = '') {
  if (override === 'none') return flatGround(background)
  const url = String(
    override === 'instance' ? configured?.instance || '' : override || configured?.style || '',
  ).trim()
  if (url) return url

  const tiles = String((isDark() ? configured?.dark : configured?.tiles) || '').trim()
  const style = flatGround(background)
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
    map.setStyle(flatGround(background))
    return once(3000)
  })
}

/** Every host the ground could come from, for `quietTiles`. */
function grounds() {
  const froms = [
    configured?.style,
    configured?.instance,
    configured?.tiles,
    configured?.dark,
    ...Object.values(configured?.styles || {}),
  ]
  const hosts = new Set()
  for (const one of froms) {
    // Absolute only, deliberately. A relative one is a ground we serve
    // ourselves, and a 404 on that is our own bug rather than somebody else's
    // afternoon — it should print.
    try {
      if (one) hosts.add(new URL(one).host)
    } catch {
      // Not an absolute URL. Nothing to match against, which is the safe
      // direction: an error nobody recognised is one that still gets printed.
    }
  }
  return hosts
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
 * **Matched on the host, not only on the source id.** With a raster ground the
 * failure is a tile in a source we named `basemap`, so the id was enough. A
 * vector style fails one step earlier — the style *document* cannot be fetched,
 * before there is a source to blame — and that error carries no `sourceId` at
 * all, so switching to vector quietly put a red line under every map screen on
 * every bench with no route out.
 *
 * Only the ground is quietened. An error about a source or a layer we added is
 * ours and still surfaces, because that one means the screen is wrong.
 */
export function quietTiles(map) {
  const hosts = grounds()
  map.on('error', (event) => {
    const source = event?.sourceId
    if (source === 'basemap' || event?.error?.status === 404) return
    const url = event?.error?.url
    if (url) {
      try {
        if (hosts.has(new URL(url).host)) return
      } catch {
        // An error about something that is not a URL is not a ground failure.
      }
    }
    console.error(event?.error || event)
  })
}


/**
 * How much of the world a workspace wants under its records.
 *
 * Matched on layer id prefixes, which is safe in a way it looks like it is not:
 * every style here is built by planetiler against the OpenMapTiles schema, and
 * that schema names its layers. A style that does not follow it simply matches
 * nothing and draws in full, which is the right way for this to fail.
 */
const DECORATION = ['building', 'landcover', 'landuse', 'park', 'poi', 'housenumber', 'aeroway']

/** What a minimal ground keeps. Everything a route needs to be placed, and no more. */
const ESSENTIAL = ['background', 'water', 'waterway', 'road', 'bridge', 'tunnel', 'boundary']

function starts(id, prefixes) {
  const name = String(id || '').toLowerCase()
  return prefixes.some((one) => name.startsWith(one))
}

/**
 * Apply a workspace's basemap preferences to a map that has already loaded.
 *
 * On the running style rather than by fetching and patching the JSON first,
 * which matters twice: it is instant, so a switch in the picker is a switch on
 * the screen, and it cannot fail differently from the style that is actually
 * drawn — there is only one copy.
 *
 * Only the basemap's own layers are touched. Ours are added after the style
 * loads and are passed over by name, because a legend that hides itself when
 * somebody turns off place names would be a surprising way to learn what this
 * setting does.
 */
export function restyle(map, prefer = {}, ours = []) {
  if (!map || !map.getStyle) return
  const style = map.getStyle()
  if (!style?.layers) return

  const labels = prefer.labels !== false
  const detail = prefer.detail || 'Full'
  const mine = new Set(ours)

  for (const layer of style.layers) {
    if (mine.has(layer.id)) continue
    let show = true
    // A label is a symbol layer, in every style built this way.
    if (!labels && layer.type === 'symbol') show = false
    if (detail === 'Quiet' && starts(layer.id, DECORATION)) show = false
    if (detail === 'Minimal' && !starts(layer.id, ESSENTIAL)) show = false
    try {
      map.setLayoutProperty(layer.id, 'visibility', show ? 'visible' : 'none')
    } catch {
      // A layer that has gone while we were walking the list. The next call
      // rebuilds from the style as it is then.
    }
  }
}
