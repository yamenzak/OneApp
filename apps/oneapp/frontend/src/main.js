import { createApp } from 'vue'
import { setConfig, frappeRequest } from '@/ui'
import { brand, systemTimezone } from '@/lib/runtime/boot'
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

createApp(App).use(router).mount('#app')
