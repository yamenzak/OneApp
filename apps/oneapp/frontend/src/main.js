import { createApp } from 'vue'
import { setConfig, frappeRequest } from '@/ui'
import { systemTimezone } from './lib/boot'

import App from './App.vue'
import router from './router'
import './index.css'

// Same-origin session cookie authenticates every call.
setConfig('resourceFetcher', frappeRequest)

// What `dayjsLocal` converts *from*. Frappe writes datetimes in the site's
// timezone, so without this a stored timestamp is read as if it were already
// local and every date is out by the offset between the two.
if (systemTimezone) setConfig('systemTimezone', systemTimezone)

createApp(App).use(router).mount('#app')
