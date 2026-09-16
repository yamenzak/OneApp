/**
 * The `narrow` parameter's grammar, written once.
 *
 * `narrow=line:U6;stop:Alexanderplatz` — pairs of a key and a value, each half
 * percent-encoded, joined by semicolons. `lib/url/params.js` declares the key;
 * this is what is inside it.
 *
 * Two surfaces narrow: the mobility space, where it is a facet bar shared by
 * four screens, and any record's related tab, which opens the screen behind it
 * narrowed to that record — `modules/onespace/lib/screen/narrowing.js`. They
 * mean the same thing by the word and a reader should be able to tell what a
 * link does before following it, so they say it the same way. Two grammars
 * under one key is the §C4 defect in miniature: the same idea encoded
 * differently on each surface that reached for it.
 */

/** What separates one pair from the next, and a key from its value. */
const BETWEEN = ';'
const AT = ':'

/** `{line: 'U6', stop: 'Alex'}` → `line:U6;stop:Alex`, each half escaped. */
export function writeNarrowing(what) {
  return Object.entries(what || {})
    .filter(([, value]) => value !== '' && value !== null && value !== undefined)
    .map(([key, value]) => `${encodeURIComponent(key)}${AT}${encodeURIComponent(value)}`)
    .join(BETWEEN)
}

/** And back. A pair with no colon in it is dropped rather than guessed at. */
export function readNarrowing(text) {
  const found = {}
  for (const pair of (text || '').split(BETWEEN)) {
    if (!pair) continue
    const at = pair.indexOf(AT)
    if (at < 1) continue
    found[decodeURIComponent(pair.slice(0, at))] = decodeURIComponent(pair.slice(at + 1))
  }
  return found
}
