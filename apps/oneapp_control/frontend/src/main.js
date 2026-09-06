import { createApp } from 'vue'
import { setConfig, frappeRequest } from '@/ui'
import { lang, systemTimezone } from '@/lib/runtime/boot'
import { direction, loadTranslations } from '@/lib/runtime/translate'

import './index.css'

// Same-origin session cookie authenticates every call — no tokens, no CORS.
setConfig('resourceFetcher', frappeRequest)

// What `dayjsLocal` converts *from*. Frappe writes datetimes in the site's
// timezone, so without this a stored timestamp is read as if it were already
// local and every date is out by the offset between the two.
if (systemTimezone) setConfig('systemTimezone', systemTimezone)

// The reader's language, on the document before anything asks what it says —
// see the tenant app's own main.js for why this is not a repaint.
document.documentElement.lang = lang
document.documentElement.dir = direction(lang)

// And the catalogue, awaited: a page that draws in English and then repaints
// in Arabic has also changed direction. English loads nothing — the msgid is
// the English sentence — so this costs a round trip only where it buys one.
//
// The app is *imported* here rather than at the top, and that is the load-order
// that makes the whole thing work. A static import is evaluated before any line
// of this file runs, so a component that builds a table of labels as it is
// imported — `const WHEN = [{ label: __('made') }]` — would ask for a word
// before the catalogue existed and hold the English answer for the rest of the
// session. Importing after the await means every module in the graph, however
// eagerly it translates, is evaluated with the catalogue already in hand.
loadTranslations(lang).then(async () => {
  const [{ default: App }, { default: router }] = await Promise.all([
    import('./App.vue'),
    import('./router'),
  ])
  createApp(App).use(router).mount('#app')
})
