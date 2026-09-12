import { createApp } from 'vue'
import { setConfig, frappeRequest } from '@/ui'
import { brand, lang, systemTimezone } from '@/shared/lib/runtime/boot'
import { direction, loadTranslations } from '@/shared/lib/runtime/translate'
import { loadDates } from '@/shared/lib/runtime/dates'
import { setBrand } from '@/modules/onespace/lib/shell/theme'
import { dropFiles } from '@/shared/lib/files/drop'

import './index.css'

// Same-origin session cookie authenticates every call.
setConfig('resourceFetcher', frappeRequest)

// What `dayjsLocal` converts *from*. Frappe writes datetimes in the site's
// timezone, so without this a stored timestamp is read as if it were already
// local and every date is out by the offset between the two.
if (systemTimezone) setConfig('systemTimezone', systemTimezone)

// The workspace's own colour, on the document before anything is drawn — a
// button painted grey and then repainted is the flash this avoids. A space's
// own theme layers over it on navigation; see lib/shell/theme.js.
setBrand({ accent: brand.accent })

// The reader's language, on the document before anything asks what it says.
// `lang` is what a screen reader announces in and what `:lang()` CSS selects
// on; `dir` is the whole layout, and changing it after the first paint moves
// every element on the page.
document.documentElement.lang = lang
document.documentElement.dir = direction(lang)

// And the catalogue, awaited: a page that draws in English and then repaints
// in Arabic has also changed direction. English loads nothing — the msgid is
// the English sentence — so this costs a round trip only where it buys one.
//
// `loadDates` beside it because "8 days ago" is not in the catalogue: it is
// built by dayjs out of a locale of its own, and without one every row of
// every list says its age in English on an otherwise Arabic screen.
//
// The app is *imported* here rather than at the top, and that is the load-order
// that makes the whole thing work. A static import is evaluated before any line
// of this file runs, so a component that builds a table of labels as it is
// imported — `const WHEN = [{ label: __('made') }]` — would ask for a word
// before the catalogue existed and hold the English answer for the rest of the
// session. Importing after the await means every module in the graph, however
// eagerly it translates, is evaluated with the catalogue already in hand.
Promise.all([loadTranslations(lang), loadDates(lang)]).then(async () => {
  const [{ default: App }, { default: router }] = await Promise.all([
    import('./App.vue'),
    import('./router'),
  ])
  // `v-drop-files`, the one drop target in the product — §D3. Registered
  // here rather than imported per surface, because a directive five
  // components reach for is a directive, and five copies of three event
  // handlers is what it replaced.
  createApp(App).use(router).directive('drop-files', dropFiles).mount('#app')
})
