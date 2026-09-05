/**
 * A space's declared look, turned into the variables that carry it.
 *
 * The manifest says four words — a mode, an accent, a ground, a radius; see
 * `oneapp_core/theming.py` for why four and not a stylesheet. This is the other
 * half of that bargain: it owns *which* CSS custom properties each of those
 * words moves, so a space declares an intent and never a token, and the day
 * frappe-ui renames one there is a single list to correct.
 *
 * Written on `<html>` rather than on a wrapper element, and that is the whole
 * reason it works on everything: a dropdown, a dialog and a toast are teleported
 * to `document.body`, so a theme scoped to the screen's own container would skin
 * the list and leave every menu over it in the other palette.
 *
 * And taken off again on the way out. A space's personality is that space's —
 * the launcher, the account area and the next space are not it — so `clear()`
 * puts the document back exactly as it was found, including the reader's own
 * light-or-dark preference, which a theme overrules for as long as it is on
 * screen and never overwrites.
 */

// frappe-ui's own attribute and storage key. Both are load-bearing names in the
// library — apps target `[data-theme='dark']` in their CSS and readers have a
// stored value — so this reads them rather than inventing its own.
const MODE_ATTRIBUTE = 'data-theme'

/**
 * The variables each intent owns.
 *
 * `accent` is the short list on purpose. frappe-ui's solid Button is
 * `bg-surface-gray-10` with 9 and 8 for hover and active, its tab indicator is
 * `--outline-gray-8`, and its links are the blue inks — so those are the
 * surfaces a space's own colour should arrive on, and the neutral scale that
 * carries every band, hover and hairline in the product is deliberately left
 * alone. A theme that repainted `--surface-gray-2` would be a theme that
 * repainted every row hover in the app.
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
 * The hairlines, taken from the ground rather than left at frappe-ui's.
 *
 * These are the borders: a card's edge, the rule between two sections, the
 * line under a table header. frappe-ui's own are a fixed step from *its* dark
 * grey, and a space that declares a much darker ground gets them at full
 * strength against a page they were never measured on — which is a screen
 * ruled into boxes when it should read as one surface.
 *
 * Small numbers on purpose: a hairline exists to be found when you look for
 * it, not to divide the page. The three are the same three frappe-ui uses in
 * that order — a rule, a border, and a border that wants to be noticed.
 */
const OUTLINE_VARIABLES = {
  '--outline-gray-1': 0.08,
  '--outline-gray-2': 0.13,
  '--outline-gray-3': 0.2,
}

/**
 * The ground, and the two surfaces that step up from it.
 *
 * A panel over a page has to be *visible* as a panel, and in dark mode that is
 * the elevation tokens rather than a shadow — see `RecordDrawer`. So a declared
 * ground moves all three together and keeps the steps it was designed with,
 * rather than leaving a near-black page under frappe-ui's own near-black
 * panels, which is a page with invisible panels on it.
 */
const GROUND_VARIABLES = {
  '--surface-base': 0,
  // The rail and the sidebar, which are the frame around every screen. Left
  // out, a declared ground painted the page and stopped at the navigation —
  // frappe-ui's own grey on three sides of somebody's black.
  //
  // A *step* off the ground rather than the ground itself, and the smallest one
  // here. Set equal, the navigation and the page it navigates were the same
  // black and the whole window read as one flat sheet with some text on it;
  // frappe-ui's own light theme makes the same distinction the same way, with
  // the sidebar a shade off the page. Small, because this is the frame telling
  // you it is the frame, not a panel asking for attention.
  '--surface-sidebar': 0.04,
  '--surface-elevation-1': 0.05,
  '--surface-elevation-2': 0.09,
  '--surface-elevation-3': 0.14,
}

// frappe-ui's radius scale, in the order the tokens are numbered. 0 and 9 are
// left out: zero is zero at any sharpness, and 9 is the pill a badge and an
// avatar are made of, which is a shape rather than a corner.
const RADIUS_SCALE = [null, 4, 5, 6, 8, 10, 12, 16, 20, null]

// How far each named sharpness moves that scale. `sharp` is a poster — a corner
// you can still see and would not call round; `soft` is the other direction,
// for a space that wants to feel gentler than the product's default.
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
 * Toward white and not black, for both families: an accent's hover state has to
 * stay visible against its own resting state, and a ground's panels have to
 * *rise* out of it. On a light ground the same lift reads as a tint rather than
 * a highlight, which is the right answer there too — a white page with a panel
 * a shade off white is how every light interface draws one.
 */
function lift(rgb, amount) {
  return hex(rgb.map((one) => one + (255 - one) * amount))
}

/**
 * How bright a colour reads, 0 to 1. WCAG's relative luminance.
 *
 * Not the average of the channels, and the difference is the whole reason this
 * exists: green carries most of the perceived brightness and blue almost none,
 * so `#ffcd11` and `#1100ff` have similar arithmetic means and are a light
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
 * is light.
 *
 * `lift` is wrong for anything that has to stay visible **on** the colour it is
 * derived from. A hairline lifted toward white is a hairline on a dark page and
 * nothing at all on a white one, and a theme whose borders vanish in light mode
 * is a theme that only works in the mode it was written in.
 */
function step(rgb, amount) {
  const away = luminance(rgb) < 0.5 ? 255 : 0
  return hex(rgb.map((one) => one + (away - one) * amount))
}

/**
 * The variables one theme sets, as `{ '--token': 'value' }`.
 *
 * Pure, and exported for the same reason `lib/format.js` is: the mapping from a
 * declared intent to the tokens it moves is the interesting part, and a test
 * should be able to ask about it without a browser.
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
    // button and nothing else, so this is that one question and not a licence
    // to repaint text: a dark accent takes white, a bright one takes near-black.
    //
    // Without it an accent is only usable if it happens to be dark. Netflix red
    // is; Caterpillar yellow is not, and white on `#ffcd11` is a button whose
    // label you cannot read — which is exactly the failure a space would blame
    // on the product rather than on its own manifest.
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

// What was on the document before a theme arrived, so leaving puts it back.
// Module state rather than a caller's, because the caller is a component and a
// component that unmounts mid-navigation would take the way back with it.
let applied = null
let previousMode = null

/**
 * Put a theme on the document, replacing whichever one is there.
 *
 * Called with nothing — a space that declares no theme — it clears, so the
 * caller can hand it whatever the current space says without asking whether
 * that is a theme or an absence.
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

  // Light or dark. Remembered on the first override only, so moving from one
  // themed space to another does not record the first one's mode as the
  // reader's own.
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
