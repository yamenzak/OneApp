import { createApp } from 'vue'
import { setConfig, frappeRequest } from '@/ui'
import { brand, lang, systemTimezone } from '@/lib/runtime/boot'
import { direction, loadTranslations } from '@/lib/runtime/translate'
import { setBrand } from '@/lib/shell/theme'

import App from './App.vue'
import router from './router'
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
loadTranslations(lang).finally(() => {
  createApp(App).use(router).mount('#app')
})
