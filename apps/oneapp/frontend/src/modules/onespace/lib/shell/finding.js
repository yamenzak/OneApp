/**
 * The one box, and the two halves of what it answers.
 *
 * **Where to go** needs no server at all. `api.session` already hands the
 * browser every space this person may open with the screens their seat allows,
 * so the rail, flattened, *is* the go-to list — filtered in memory, on the
 * keystroke, with nothing on the wire. That is why the box is useful the
 * instant it opens rather than after a round trip.
 *
 * **What to find** is `onespace/finding.py`, which fans a `like` out over
 * every screen the same person could open and hands back hits that already
 * know which space and screen they belong to.
 *
 * Both are ranked the same way and sorted into one list, because a person
 * typing `inv` means either and should not have to say which. Screens come
 * first at equal rank: there are a handful of them, they are what the word
 * usually meant, and a destination is cheaper to be wrong about than a record.
 */
import { computed, reactive } from 'vue'

import { session } from '@/modules/onespace/lib/shell/session'
import { workspace } from '@/shared/lib/workspace'
import { KIND, withAt } from '@/shared/lib/url/at'

/** Nothing is searched for less than this — the server's own floor. */
export const SHORTEST = 2

/** Screens offered before anybody types, and after. */
const SCREENS_SHOWN = 8

/** Where a match landed, best first — the same four the server ranks by. */
export const EXACT = 0
export const STARTS = 1
export const WORD = 2
export const ANYWHERE = 3
const NOWHERE = 9

/** How well one label matches, or `NOWHERE`. */
export function where(text, label) {
  const asked = String(text || '').trim().toLowerCase()
  const low = String(label || '').toLowerCase()
  if (!asked) return ANYWHERE
  if (low === asked) return EXACT
  if (low.startsWith(asked)) return STARTS
  if (` ${low}`.includes(` ${asked}`)) return WORD
  return low.includes(asked) ? ANYWHERE : NOWHERE
}

/**
 * Every screen this person could open, as one flat list.
 *
 * A component screen is in it and a screen with a doctype is in it, because
 * going somewhere does not care which: Configuration is a place in OneBook
 * exactly as Invoices is.
 */
export function screensOf(spaces) {
  const found = []
  for (const space of spaces || []) {
    for (const screen of space.screens || []) {
      found.push({
        kind: 'screen',
        key: `screen:${space.space_code}/${screen.screen}`,
        title: screen.label || screen.screen,
        space: space.space_code,
        spaceLabel: space.space_label || space.space_code,
        brand: space.brand || '',
        screen: screen.screen,
        icon: screen.icon || 'lucide-layout-grid',
      })
    }
  }
  return found
}

/**
 * The screens matching what was typed, best first.
 *
 * With nothing typed it is **where you already are**. The first eight screens
 * of a workspace with nine spaces in it are whichever two spaces sort first,
 * which is a list of places nobody asked about — and the box opens on it, so
 * it is the first thing anybody sees. The space you are standing in is the one
 * answer that is never arbitrary.
 */
export function screensMatching(screens, text, from = '') {
  const asked = String(text || '').trim()
  if (!asked) {
    const here = (screens || []).filter((one) => !from || one.space === from)
    return (here.length ? here : screens || []).slice(0, SCREENS_SHOWN)
  }
  const scored = (screens || [])
    .map((one) => ({
      ...one,
      rank: Math.min(where(asked, one.title), where(asked, one.spaceLabel)),
    }))
    .filter((one) => one.rank !== NOWHERE)
  scored.sort((a, b) => a.rank - b.rank || a.title.localeCompare(b.title))
  return scored.slice(0, SCREENS_SHOWN)
}

/** A record hit from the server, as a row this list can draw. */
export function recordRow(hit) {
  return {
    kind: 'record',
    key: `record:${hit.doctype}/${hit.name}`,
    title: hit.title,
    id: hit.id || '',
    label: hit.label || hit.doctype,
    space: hit.space,
    spaceLabel: hit.space_label || hit.space,
    brand: hit.brand || '',
    screen: hit.screen,
    icon: hit.icon || 'lucide-file-text',
    name: hit.name,
    rank: hit.rank ?? ANYWHERE,
  }
}

/**
 * Screens and records in one list.
 *
 * Sorted by how well each matched, and a screen ahead of a record at the same
 * rank. Not interleaved further than that: the server has already taken every
 * screen's best hit before anybody's second, so the order it sent is the order
 * that is kept inside a rank.
 */
export function merge(screens, records) {
  const rows = [
    ...screens.map((one, at) => ({ ...one, seat: at, first: 0 })),
    ...records.map((one, at) => ({ ...one, seat: at, first: 1 })),
  ]
  rows.sort((a, b) => a.rank - b.rank || a.first - b.first || a.seat - b.seat)
  return rows
}

/** Where one row goes. */
export function routeFor(row) {
  const query = { screen: row.screen }
  return {
    name: 'Screen',
    params: { spaceCode: row.space },
    query: row.kind === 'record' ? withAt(query, KIND.RECORD, row.name) : query,
  }
}

//: Open state, what was typed, and what came back. One object for the session,
//: because the box is the shell's and there is only ever one of it.
export const finder = reactive({
  open: false,
  typed: '',
  results: [],
  looking: false,
  failed: '',
  //: Where the box was opened from, which breaks a tie and narrows nothing.
  from: '',
})

export const screens = computed(() => screensOf(session.spaces))

export const shown = computed(() =>
  merge(
    screensMatching(screens.value, finder.typed, finder.from),
    finder.results.map(recordRow),
  ),
)

export function openFinder(from = '') {
  finder.from = from || ''
  finder.open = true
}

export function closeFinder() {
  finder.open = false
  finder.typed = ''
  finder.results = []
  finder.failed = ''
  finder.looking = false
}

//: Only the newest answer is kept. A search is debounced but not serialised,
//: so a slow request for `inv` can land after a fast one for `invoice` and
//: repaint the list with the older word's hits.
let asked = 0

export async function look(text) {
  const query = String(text || '').trim()
  if (query.length < SHORTEST) {
    finder.results = []
    finder.failed = ''
    finder.looking = false
    return
  }
  const mine = ++asked
  finder.looking = true
  try {
    const answer = await workspace.find(query, finder.from)
    if (mine !== asked) return
    finder.results = answer?.results || []
    finder.failed = ''
  } catch (error) {
    if (mine !== asked) return
    finder.results = []
    finder.failed = String(error?.message || error || '')
  } finally {
    if (mine === asked) finder.looking = false
  }
}
