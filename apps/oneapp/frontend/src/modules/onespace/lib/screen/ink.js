/**
 * A frappe-ui colour name as something a canvas can paint with.
 *
 * The board draws its dots with Tailwind classes — `text-ink-blue-3` and its
 * eight siblings — and a map draws into WebGL, which wants `#2a6bd8`. Rather
 * than keep a second palette in hex, which would be a second thing to update
 * the day the tokens move and would be silently wrong in one theme, this asks
 * the browser: it puts the class on a throwaway element and reads back the
 * colour that resulted.
 *
 * So there is one palette, it is the design system's, and it is correct in
 * light and dark without either being written down here.
 */

const INK = {
  gray: 'text-ink-gray-5',
  blue: 'text-ink-blue-3',
  green: 'text-ink-green-3',
  orange: 'text-ink-orange-3',
  red: 'text-ink-red-3',
  amber: 'text-ink-amber-3',
  violet: 'text-ink-violet-3',
  pink: 'text-ink-pink-3',
  teal: 'text-ink-teal-3',
}

/** Last resort, and only reached with no document — a unit test, or SSR. */
const FALLBACK = '#8b8b8b'

/**
 * Any CSS colour as one WebGL will accept.
 *
 * The design tokens are `oklch()`, which is correct and modern and which
 * MapLibre's style specification refuses outright — "color expected,
 * oklch(.964 0 0) found" — and it refuses the whole style, so one unconverted
 * value is a blank map rather than a grey box.
 *
 * Two things that look like they would work and do not: `getComputedStyle`
 * hands oklch back as oklch, and so does a canvas `fillStyle` round-trip. A
 * browser that understands the colour has no reason to downgrade it.
 *
 * So it is *painted* and the pixel read back. One device pixel through the
 * browser's own colour pipeline, which is by definition the right answer, and
 * correct for whatever the tokens become next — no colour library, no table of
 * conversions to keep in step with the design system.
 */
let pad = null

export function paintable(value, fallback = FALLBACK) {
  const text = String(value || '').trim()
  if (!text) return fallback
  if (typeof document === 'undefined') return fallback

  try {
    if (!pad) {
      pad = document.createElement('canvas')
      pad.width = pad.height = 1
    }
    const context = pad.getContext('2d', { willReadFrequently: true })
    context.clearRect(0, 0, 1, 1)
    context.fillStyle = text
    context.fillRect(0, 0, 1, 1)
    const [r, g, b, a] = context.getImageData(0, 0, 1, 1).data
    if (!a) return fallback
    const hex = (n) => n.toString(16).padStart(2, '0')
    return a === 255
      ? `#${hex(r)}${hex(g)}${hex(b)}`
      : `rgba(${r}, ${g}, ${b}, ${(a / 255).toFixed(3)})`
  } catch {
    return fallback
  }
}

/** One design token, ready to paint with. */
export function tokenInk(name, fallback = FALLBACK) {
  if (typeof document === 'undefined') return fallback
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name)
  return paintable(raw, fallback)
}

let cache = {}
let themedFor = ''

function themeNow() {
  if (typeof document === 'undefined') return ''
  const root = document.documentElement
  return `${root.dataset.theme || ''}|${
    window.matchMedia?.('(prefers-color-scheme: dark)')?.matches ? 'dark' : 'light'
  }`
}

export function inkOf(theme) {
  const className = INK[theme] || INK.gray
  if (typeof document === 'undefined') return FALLBACK

  // The cache is per theme, not for ever: a reader switching to dark expects
  // the pins to follow, and a value read before the switch is the wrong one.
  const now = themeNow()
  if (now !== themedFor) {
    cache = {}
    themedFor = now
  }
  if (cache[className]) return cache[className]

  const probe = document.createElement('span')
  probe.className = className
  probe.style.position = 'absolute'
  probe.style.visibility = 'hidden'
  probe.style.pointerEvents = 'none'
  document.body.appendChild(probe)
  const colour = paintable(getComputedStyle(probe).color)
  probe.remove()

  cache[className] = colour
  return colour
}

/** Forget what was read. For a test, and for a theme change nothing observed. */
export function forgetInk() {
  cache = {}
  themedFor = ''
}
