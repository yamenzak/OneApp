/**
 * A word, drawn as a coloured badge, with the colour read out of the word.
 *
 * A Link is a foreign key and the engine draws one as a record — a face, a
 * title, an id underneath. Right for a Link to a *record*; wrong for the ones
 * that are really categories, which is most of the Links on a doctype somebody
 * else designed. A Designation and a Department are Links because ERPNext keeps
 * a table of them, not because anybody wants to look one up, and drawn as
 * records they are three lines of chrome per cell saying one word.
 *
 * So a screen may name them — `view_settings.tags` — and they come back with
 * `cell: "tag"`. This decides what colour one is.
 *
 * **Derived, not configured.** A tenant's designations are whatever that tenant
 * typed, so there is nobody to ask what colour "Quantity Surveyor" should be
 * and no settings page worth building to ask them. The value hashes to one of
 * the five, which means: the same word is always the same colour, on every
 * screen and for every reader; two different words are usually different
 * colours; and a workspace that renames a department gets a new one, which is
 * honest — it is a different word.
 *
 * **Five, and they are the product's own.** There is a tension worth naming:
 * elsewhere in OneSpace a badge's colour *means* something — green is fine, red
 * is a problem, amber is something to know. A tag's colour means nothing except
 * "not the same as that one". They are told apart by where they are: a tag sits
 * in a column the screen declared as a tag, beside other tags, and a status
 * badge sits in the status column. Using a separate palette was the other
 * option and it would have cost the product a second set of colours to keep in
 * step with the first.
 *
 * Gray is deliberately not in the ring. It is what an empty value draws as, and
 * a real value that happened to hash to gray would be indistinguishable from
 * one that is missing.
 */

/** The ring. `Badge`'s own themes, minus gray — see above. */
export const TAG_THEMES = ['blue', 'green', 'amber', 'red', 'violet']

/** What a tag with nothing in it is. */
export const EMPTY_THEME = 'gray'

/**
 * FNV-1a, 32-bit.
 *
 * Any stable hash would do; this one is four lines, has no dependency, and
 * spreads short strings — which is what these are — far better than summing
 * character codes, where "Designer" and "Desginer" land next to each other and
 * every word of the same length clusters.
 *
 * `>>> 0` after each step keeps it in 32 unsigned bits: JavaScript's bitwise
 * operators work on signed 32-bit integers, so without it the multiply drifts
 * into the float range and two runs can disagree.
 */
export function seed(value) {
  let hash = 0x811c9dc5
  const text = String(value ?? '')
  for (let at = 0; at < text.length; at += 1) {
    hash ^= text.charCodeAt(at)
    hash = Math.imul(hash, 0x01000193) >>> 0
  }
  return hash
}

/**
 * The theme for one tag.
 *
 * Trimmed and case-folded first, so "Engineer" and "engineer " are one tag
 * rather than two colours for the same job.
 */
export function tagTheme(value) {
  const text = String(value ?? '').trim()
  if (!text) return EMPTY_THEME
  return TAG_THEMES[seed(text.toLowerCase()) % TAG_THEMES.length]
}
