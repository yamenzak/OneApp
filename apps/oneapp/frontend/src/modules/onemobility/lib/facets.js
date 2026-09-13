/**
 * How this space is narrowed, once for the whole of it.
 *
 * Four screens carried a facet bar and each one carried it alone: its own
 * `facets` ref, its own `offered` ref, its own `network.offered()` on mount and
 * its own `JSON.stringify` on the way out. `docs/UNIFICATION.md` §B2 counted
 * the duplication; the consequence is worse than the line count. The map took
 * a line and Insights took a line separately, so a person who narrowed the
 * network to U6 and then opened Insights was looking at the whole fleet and
 * had no way to tell — which is one filter behaving as two.
 *
 * So the chosen set is module-level state, and the vocabulary behind it is
 * fetched once. Moving from the map to the charts keeps what you were looking
 * at, which is what "one filter" has to mean if it means anything.
 *
 * And it is in the URL — §C4. A narrowing you cannot send is a narrowing you
 * describe in a message instead ("filter by U6, then the Tuesday"), which is
 * the same failure the settings dialog had. `narrow=line:U6;stop:Alexanderplatz`,
 * because a reader should be able to see what a link does before following it.
 */
import { ref } from 'vue'

import { useAddress } from '@/shared/composables/useAddress'

import { network } from './api'

//: What every screen in this space is narrowed by. One object, shared, because
//: two of them is the bug this exists to remove.
const chosen = ref({})

//: The vocabulary, from the server — `onemobility/facets.py`. Asked once per
//: session rather than once per screen: it is a list of dimensions, and it does
//: not change between two clicks of the sub-nav.
const offered = ref([])
let asked = null

/** `{line: 'U6', stop: 'Alex'}` → `line:U6;stop:Alex`, each half escaped. */
function written(what) {
  return Object.entries(what || {})
    .filter(([, value]) => value !== '' && value !== null && value !== undefined)
    .map(([key, value]) => `${encodeURIComponent(key)}:${encodeURIComponent(value)}`)
    .join(';')
}

/** And back. A pair with no colon in it is dropped rather than guessed at. */
function read(text) {
  const found = {}
  for (const pair of (text || '').split(';')) {
    if (!pair) continue
    const at = pair.indexOf(':')
    if (at < 1) continue
    found[decodeURIComponent(pair.slice(0, at))] = decodeURIComponent(pair.slice(at + 1))
  }
  return found
}

/**
 * The shared narrowing, for one screen.
 *
 * `unavailable` stays the caller's: which dimensions a *particular* answer
 * cannot honour is a fact about that screen's own query, and the server says
 * so per endpoint.
 */
export function useFacets() {
  if (!asked) {
    asked = network.offered()
      .then((choices) => { offered.value = choices.facets || [] })
      .catch(() => { offered.value = [] })
  }

  useAddress('narrow', {
    read: () => written(chosen.value),
    write: (value) => { chosen.value = read(value) },
  })

  return {
    facets: chosen,
    offered,
    /** As the endpoints want it: one JSON object, in one place. */
    asJson: () => JSON.stringify(chosen.value),
  }
}
