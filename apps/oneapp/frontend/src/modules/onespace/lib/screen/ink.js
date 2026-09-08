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
  const colour = getComputedStyle(probe).color || FALLBACK
  probe.remove()

  cache[className] = colour
  return colour
}

/** Forget what was read. For a test, and for a theme change nothing observed. */
export function forgetInk() {
  cache = {}
  themedFor = ''
}
