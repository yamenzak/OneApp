/**
 * A screen, narrowed to one record — carried in the URL.
 *
 * A record's tab already draws another screen's rows filtered to it: a
 * project's tasks, a client's invoices, an employee's leave. What the tab
 * cannot do is *be* that screen — it is a table, and the board, the calendar
 * and the dashboard are exactly what somebody wants when the question stops
 * being "what is filed against this" and becomes "show me this project's
 * work". Copying the screen shell into a tab is `docs/UNIFICATION.md` F1's
 * mistake written out one more time, so the tab opens the real screen instead
 * and hands it the narrowing in the URL.
 *
 *     ?screen=tasks&type=board&narrow=project:PROJ-0001
 *
 * The same `narrow` the mobility space has always used, in the same grammar —
 * `lib/url/narrow.js`, `docs/UNIFICATION.md` §C4. Semicolons separate pairs,
 * which is how a Dynamic Link travels: it is two columns, an id and the
 * doctype that id belongs to, and narrowing on the id alone would put a
 * licence's letters on a project that shares its name.
 *
 * What arrives is an **ordinary filter**, seeded into the panel where the
 * reader can see it and take it off. Not a second kind of narrowing and not a
 * hidden one: a list narrowed by something with no control on screen is the
 * thing `useScreenAsked.narrowTo` was written to avoid, and this is the same
 * rule reached from the URL instead of from a tally.
 */
import { readNarrowing, writeNarrowing } from '@/shared/lib/url/narrow'

/** The query key. Declared in `lib/url/params.js` with every other one. */
export const NARROW = 'narrow'

/**
 * The filters a URL is asking for, as `[field, '=', value]` rows.
 *
 * Anything malformed is dropped rather than refused: a truncated link should
 * open the screen, not an error page.
 */
export function narrowingIn(query) {
  const asked = query?.[NARROW]
  // A repeated key arrives as an array. Not a shape we write, and not one to
  // fall over on either — a link is a thing people edit by hand.
  const text = Array.isArray(asked) ? asked.join(';') : asked
  return Object.entries(readNarrowing(text))
    .filter(([field, value]) => field && value)
    .map(([field, value]) => [field, '=', value])
}

/**
 * The other direction: what a record's tab puts in the link.
 *
 * `where` is the tab's own extra — the doctype half of a Dynamic Link — and it
 * comes through as more pairs rather than as a second parameter, so a reader
 * of the URL sees one idea written once.
 */
export function narrowingFor(field, name, where = []) {
  if (!field || !name) return ''
  const pairs = { [field]: name }
  for (const one of where || []) {
    if (!Array.isArray(one) || one.length < 3) continue
    const [column, operator, value] = one
    // An equality and nothing else: the URL says "narrowed to this one", and
    // anything cleverer is a filter somebody set, which belongs in the panel
    // they set it in.
    if (operator !== '=' || !column || typeof value !== 'string') continue
    pairs[column] = value
  }
  return writeNarrowing(pairs)
}

/** Whether two sets of filters say the same thing, in the same order. */
export function sameNarrowing(one, other) {
  return JSON.stringify(one || []) === JSON.stringify(other || [])
}
