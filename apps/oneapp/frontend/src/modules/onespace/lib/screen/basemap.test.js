import { beforeEach, describe, expect, it, vi } from 'vitest'

// The boot payload is a module-level read, so it is mocked rather than set:
// `window.basemap` is written by the page before the bundle loads, and a test
// that assigned it afterwards would be testing the mock.
const boot = { style: '', tiles: '', dark: '', attribution: '', instance: '', styles: {} }
vi.mock('@/shared/lib/runtime/boot', () => ({
  get basemap() {
    return boot
  },
}))
vi.mock('@/modules/onespace/lib/screen/ink', () => ({
  paintable: (value) => value,
  tokenInk: () => surface,
}))

let surface = '#ffffff'

const { attribution, isDark, quietTiles, restyle, styleFor, whenLoaded } = await import(
  '@/modules/onespace/lib/screen/basemap'
)

beforeEach(() => {
  Object.assign(boot, {
    style: '', tiles: '', dark: '', attribution: '', instance: '', styles: {},
  })
  surface = '#ffffff'
})

describe('styleFor', () => {
  it('is a flat ground when no tiles are configured', () => {
    const style = styleFor('#eeeeee')
    expect(style.layers).toHaveLength(1)
    expect(style.layers[0].paint['background-color']).toBe('#eeeeee')
    expect(style.sources).toEqual({})
  })

  it('adds a raster source when tiles are configured', () => {
    boot.tiles = 'https://tiles.example/{z}/{x}/{y}.png'
    const style = styleFor('#eeeeee')
    expect(style.sources.basemap.tiles).toEqual([boot.tiles])
    // Under everything: a surface that appends its own layers must land on top
    // without having to say so.
    expect(style.layers.map((one) => one.id)).toEqual(['ground', 'basemap'])
  })

  it('hands back a configured style URL untouched', () => {
    boot.style = 'https://tiles.example/style.json'
    expect(styleFor('#eeeeee')).toBe(boot.style)
  })

  it('lets a caller override the instance style', () => {
    boot.style = 'https://tiles.example/style.json'
    expect(styleFor('#eeeeee', 'https://other.example/s.json')).toBe(
      'https://other.example/s.json'
    )
  })

  it('takes the dark tiles on a dark board', () => {
    surface = '#111111'
    boot.tiles = 'https://tiles.example/light/{z}/{x}/{y}.png'
    boot.dark = 'https://tiles.example/dark/{z}/{x}/{y}.png'
    expect(styleFor('#111111').sources.basemap.tiles).toEqual([boot.dark])
  })
})

describe('isDark', () => {
  it('reads the surface rather than the system', () => {
    expect(isDark()).toBe(false)
    surface = '#101014'
    expect(isDark()).toBe(true)
  })

  it('says light when the token is not a colour it can read', () => {
    surface = 'not-a-colour'
    expect(isDark()).toBe(false)
  })
})

describe('attribution', () => {
  it('is whatever the instance says, and empty rather than invented', () => {
    expect(attribution()).toBe('')
    boot.attribution = '© Someone'
    expect(attribution()).toBe('© Someone')
  })
})

describe('whenLoaded', () => {
  const fake = (loaded) => {
    const handlers = {}
    return {
      styleLoaded: loaded,
      isStyleLoaded: () => handlers.self.styleLoaded,
      on: (event, fn) => {
        handlers[event] = fn
      },
      setStyle: vi.fn(() => {
        handlers.self.styleLoaded = true
        handlers.load?.()
      }),
      fire: (event) => handlers[event]?.(),
      handlers,
    }
  }

  it('resolves at once when the style is already in', async () => {
    const map = fake(true)
    map.handlers.self = map
    await expect(whenLoaded(map, '#fff', 50)).resolves.toBeUndefined()
    expect(map.setStyle).not.toHaveBeenCalled()
  })

  it('falls back to a flat ground when the style never arrives', async () => {
    const map = fake(false)
    map.handlers.self = map
    await whenLoaded(map, '#fff', 10)
    expect(map.setStyle).toHaveBeenCalledOnce()
    // The recovery style is ours, so `addSource` afterwards has a style to
    // add to — which is the whole reason this is not a bare timeout.
    expect(map.setStyle.mock.calls[0][0].layers[0].id).toBe('ground')
  })
})

describe('restyle', () => {
  const fake = (ids) => {
    const seen = {}
    return {
      seen,
      getStyle: () => ({ layers: ids.map(([id, type]) => ({ id, type })) }),
      setLayoutProperty: (id, _prop, value) => {
        seen[id] = value
      },
    }
  }

  const ground = [
    ['background', 'background'],
    ['water', 'fill'],
    ['landuse_park', 'fill'],
    ['building', 'fill'],
    ['road_major', 'line'],
    ['poi_z14', 'symbol'],
    ['place_label', 'symbol'],
  ]

  it('draws everything when nothing is asked for', () => {
    const map = fake(ground)
    restyle(map, { labels: true, detail: 'Full' })
    expect(Object.values(map.seen).every((one) => one === 'visible')).toBe(true)
  })

  it('hides the symbol layers when places are not named', () => {
    const map = fake(ground)
    restyle(map, { labels: false, detail: 'Full' })
    expect(map.seen.place_label).toBe('none')
    expect(map.seen.poi_z14).toBe('none')
    expect(map.seen.road_major).toBe('visible')
  })

  it('takes the decoration out on Quiet and keeps the roads', () => {
    const map = fake(ground)
    restyle(map, { labels: true, detail: 'Quiet' })
    expect(map.seen.building).toBe('none')
    expect(map.seen.landuse_park).toBe('none')
    expect(map.seen.road_major).toBe('visible')
    expect(map.seen.place_label).toBe('visible')
  })

  it('keeps only what places a route on Minimal', () => {
    const map = fake(ground)
    restyle(map, { labels: true, detail: 'Minimal' })
    expect(map.seen.road_major).toBe('visible')
    expect(map.seen.water).toBe('visible')
    expect(map.seen.background).toBe('visible')
    expect(map.seen.place_label).toBe('none')
  })

  // Two spellings of the same thing, and Minimal has to keep both: our own
  // style comes from Positron and calls a road `highway_*`, where the three
  // from OpenFreeMap call it `road_*`.
  it('knows a road by either name the schema is written in', () => {
    const map = fake([
      ['background', 'background'],
      ['highway_motorway_inner', 'line'],
      ['railway', 'line'],
      ['building', 'fill'],
    ])
    restyle(map, { labels: true, detail: 'Minimal' })
    expect(map.seen.highway_motorway_inner).toBe('visible')
    expect(map.seen.railway).toBe('visible')
    expect(map.seen.building).toBe('none')
  })

  // The legend does not disappear because somebody turned off place names.
  it('never touches a layer the surface added itself', () => {
    const map = fake([...ground, ['vehicles', 'symbol'], ['routes', 'line']])
    restyle(map, { labels: false, detail: 'Minimal' }, ['vehicles', 'routes'])
    expect(map.seen.vehicles).toBeUndefined()
    expect(map.seen.routes).toBeUndefined()
  })

  it('survives a map with no style yet', () => {
    expect(() => restyle(null)).not.toThrow()
    expect(() => restyle({ getStyle: () => null })).not.toThrow()
  })
})

describe('styleFor, the two words that are not URLs', () => {
  it("takes the instance's own answer rather than the resolved one", () => {
    // The payload was written when the page loaded, so `style` has whatever
    // this workspace had picked then baked into it.
    boot.style = 'https://tiles.example/bright.json'
    boot.instance = 'https://tiles.example/positron.json'
    expect(styleFor('#eee', 'instance')).toBe(boot.instance)
  })

  it('falls back to the raster path when the instance named no style', () => {
    boot.style = 'https://tiles.example/bright.json'
    boot.tiles = 'https://tiles.example/{z}/{x}/{y}.png'
    expect(styleFor('#eee', 'instance').sources.basemap.tiles).toEqual([boot.tiles])
  })

  it('draws a flat ground on purpose, which an empty string cannot say', () => {
    boot.style = 'https://tiles.example/bright.json'
    const style = styleFor('#eeeeee', 'none')
    expect(style.sources).toEqual({})
    expect(style.layers[0].paint['background-color']).toBe('#eeeeee')
  })
})

describe('quietTiles', () => {
  const fake = () => {
    let handler = null
    return {
      on: (event, fn) => {
        if (event === 'error') handler = fn
      },
      raise: (event) => handler?.(event),
    }
  }

  it('says nothing about a ground that could not be reached', () => {
    // A vector style fails one step before there is a source to blame, so the
    // event carries no sourceId at all — which is how switching to vector put
    // a red line under every map screen on a bench with no route out.
    boot.styles = { Positron: 'https://tiles.example/positron' }
    boot.instance = 'https://tiles.example/positron'
    const map = fake()
    const said = vi.spyOn(console, 'error').mockImplementation(() => {})
    quietTiles(map)
    map.raise({ error: { status: 0, url: 'https://tiles.example/positron' } })
    expect(said).not.toHaveBeenCalled()
    said.mockRestore()
  })

  it('still says everything about a layer of ours', () => {
    boot.styles = { Positron: 'https://tiles.example/positron' }
    const map = fake()
    const said = vi.spyOn(console, 'error').mockImplementation(() => {})
    quietTiles(map)
    map.raise({ sourceId: 'vehicles', error: { status: 400 } })
    expect(said).toHaveBeenCalledOnce()
    said.mockRestore()
  })
})
