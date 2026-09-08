import { beforeEach, describe, expect, it, vi } from 'vitest'

// The boot payload is a module-level read, so it is mocked rather than set:
// `window.basemap` is written by the page before the bundle loads, and a test
// that assigned it afterwards would be testing the mock.
const boot = { style: '', tiles: '', dark: '', attribution: '' }
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

const { attribution, isDark, styleFor, whenLoaded } = await import(
  '@/modules/onespace/lib/screen/basemap'
)

beforeEach(() => {
  Object.assign(boot, { style: '', tiles: '', dark: '', attribution: '' })
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
