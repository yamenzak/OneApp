/**
 * A space's declared look, turned into the variables that carry it.
 *
 * The manifest says four words — a mode, an accent, a ground, a radius; see
 * `oneapp_core/theming.py` for why four and not a stylesheet. This owns *which*
 * CSS custom properties each of those words moves, so a space declares an
 * intent and never a token.
 *
 * Written on `<html>` rather than on a wrapper: a dropdown, a dialog and a
 * toast are teleported to `document.body`, so a theme scoped to the screen's
 * container would skin the list and leave every menu over it in the other
 * palette.
 *
 * `clear()` puts the document back exactly as it was found, including the
 * reader's own light-or-dark preference, which a theme overrules for as long as
 * it is on screen and never overwrites.
 */

// frappe-ui's own attribute and storage key: apps target `[data-theme='dark']`
// in their CSS and readers have a stored value, so this reads them rather than
// inventing its own.
const MODE_ATTRIBUTE = 'data-theme'

/**
 * The variables each intent owns.
 *
 * `accent` is a short list on purpose: frappe-ui's solid Button, its tab
 * indicator and its links are the surfaces a space's colour should arrive on,
 * and the neutral scale that carries every band, hover and hairline is
 * deliberately left alone.
 */
const ACCENT_VARIABLES = {
  // The solid button, and the progress fill that has no theme of its own.
  '--surface-gray-10': 0,
  '--surface-gray-9': 0.12,
  '--surface-gray-8': 0.24,
  // The tab indicator: the line under the screen you are on.
  '--outline-gray-8': 0,
  // Links, and the blue ink frappe-ui uses for anything it considers a link.
  '--ink-blue-link': 0.1,
  '--ink-blue-2': 0.1,
  '--ink-blue-3': 0,
}

/**
 * The hairlines, taken from the ground rather than left at frappe-ui's, whose
 * own are a fixed step from *its* dark grey — against a much darker declared
 * ground that is a screen ruled into boxes when it should read as one surface.
 *
 * Small numbers on purpose: a hairline exists to be found when you look for it.
 */
const OUTLINE_VARIABLES = {
  '--outline-gray-1': 0.08,
  '--outline-gray-2': 0.13,
  '--outline-gray-3': 0.2,
}

/**
 * The ground, and the two surfaces that step up from it.
 *
 * A panel over a page has to be visible as a panel, and in dark mode that is
 * the elevation tokens rather than a shadow. So a declared ground moves all
 * three together and keeps the steps it was designed with.
 */
const GROUND_VARIABLES = {
  '--surface-base': 0,
  // The rail and the sidebar, which are the frame around every screen. Left
  // out, a declared ground painted the page and stopped at the navigation.
  //
  // A *step* off the ground rather than the ground itself, and the smallest one
  // here: set equal, the navigation and the page read as one flat sheet.
  '--surface-sidebar': 0.04,
  '--surface-elevation-1': 0.05,
  '--surface-elevation-2': 0.09,
  '--surface-elevation-3': 0.14,
}

// frappe-ui's radius scale, in token order. 0 and 9 are left out: zero is zero
// at any sharpness, and 9 is the pill a badge is made of.
const RADIUS_SCALE = [null, 4, 5, 6, 8, 10, 12, 16, 20, null]

// How far each named sharpness moves that scale.
const RADIUS_FACTOR = { sharp: 0.3, soft: 1.5 }

/** `#abc` or `#aabbcc` as three 0-255 numbers. Null for anything else. */
function parse(hex) {
  const value = String(hex || '').trim().replace('#', '')
  const full =
    value.length === 3
      ? value.split('').map((one) => one + one).join('')
      : value
  if (!/^[0-9a-fA-F]{6}$/.test(full)) return null
  return [0, 2, 4].map((at) => parseInt(full.slice(at, at + 2), 16))
}

/** Three 0-255 numbers as `#rrggbb`. */
function hex(rgb) {
  return `#${rgb.map((one) => Math.round(one).toString(16).padStart(2, '0')).join('')}`
}

/**
 * A colour moved toward white by `amount` (0 leaves it alone, 1 is white).
 *
 * Toward white and not black for both families: an accent's hover has to stay
 * visible against its resting state, and a ground's panels have to *rise* out
 * of it.
 */
function lift(rgb, amount) {
  return hex(rgb.map((one) => one + (255 - one) * amount))
}

/**
 * How bright a colour reads, 0 to 1. WCAG's relative luminance, not the average
 * of the channels: green carries most of the perceived brightness and blue
 * almost none, so `#ffcd11` and `#1100ff` have similar means and are a light
 * colour and a dark one. Getting that wrong puts white text on yellow.
 */
function luminance(rgb) {
  const [r, g, b] = rgb.map((one) => {
    const channel = one / 255
    return channel <= 0.03928
      ? channel / 12.92
      : ((channel + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

/**
 * A colour moved *away* from its own brightness — up if it is dark, down if it
 * is light. `lift` is wrong for anything that has to stay visible **on** the
 * colour it is derived from: a hairline lifted toward white is nothing at all
 * on a white page.
 */
function step(rgb, amount) {
  const away = luminance(rgb) < 0.5 ? 255 : 0
  return hex(rgb.map((one) => one + (away - one) * amount))
}

/**
 * The variables one theme sets, as `{ '--token': 'value' }`. Pure, and exported
 * so a test can ask about the mapping without a browser.
 */
export function variables(theme) {
  const out = {}
  if (!theme) return out

  const accent = parse(theme.accent)
  if (accent) {
    for (const [token, amount] of Object.entries(ACCENT_VARIABLES)) {
      out[token] = lift(accent, amount)
    }
    // The ink that goes *on* the accent, decided by the accent rather than
    // declared beside it. `--ink-base` is what frappe-ui puts on every solid
    // button and nothing else: a dark accent takes white, a bright one
    // near-black. Without it, white on `#ffcd11` is a button whose label you
    // cannot read.
    out['--ink-base'] = luminance(accent) > 0.45 ? '#1c1c1c' : '#ffffff'
  }

  const ground = parse(theme.ground)
  if (ground) {
    for (const [token, amount] of Object.entries(GROUND_VARIABLES)) {
      out[token] = lift(ground, amount)
    }
    for (const [token, amount] of Object.entries(OUTLINE_VARIABLES)) {
      out[token] = step(ground, amount)
    }
  }

  const factor = RADIUS_FACTOR[theme.radius]
  if (factor) {
    RADIUS_SCALE.forEach((size, at) => {
      if (size) out[`--radius-${at}`] = `${Math.round(size * factor)}px`
    })
  }

  return out
}

// What was on the document before a theme arrived. Module state rather than a
// caller's, because a component that unmounts mid-navigation would take the way
// back with it.
let applied = null
let previousMode = null

/**
 * Put a theme on the document, replacing whichever one is there. Called with
 * nothing it clears, so the caller can hand it whatever the current space says.
 */
export function applyTheme(theme) {
  const wanted = variables(theme)
  const root = document.documentElement

  // The previous theme's variables, minus the ones this theme sets anyway.
  // Removed rather than overwritten: a theme that sets an accent and no ground
  // must not inherit the last one's ground.
  for (const token of Object.keys(applied || {})) {
    if (!(token in wanted)) root.style.removeProperty(token)
  }
  for (const [token, value] of Object.entries(wanted)) {
    root.style.setProperty(token, value)
  }
  applied = Object.keys(wanted).length ? wanted : null

  // Light or dark. Remembered on the first override only, so moving between two
  // themed spaces does not record the first one's mode as the reader's own.
  const mode = theme?.mode
  if (mode) {
    if (previousMode === null) previousMode = root.getAttribute(MODE_ATTRIBUTE) ?? ''
    root.setAttribute(MODE_ATTRIBUTE, mode)
  } else {
    restoreMode(root)
  }
}

/** Everything back the way it was found. */
export function clearTheme() {
  const root = document.documentElement
  for (const token of Object.keys(applied || {})) root.style.removeProperty(token)
  applied = null
  restoreMode(root)
}

function restoreMode(root) {
  if (previousMode === null) return
  if (previousMode) root.setAttribute(MODE_ATTRIBUTE, previousMode)
  else root.removeAttribute(MODE_ATTRIBUTE)
  previousMode = null
}
