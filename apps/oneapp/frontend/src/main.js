import { createApp } from 'vue'
import { FrappeUI, setConfig, frappeRequest } from 'frappe-ui'

import App from './App.vue'
import router from './router'
import './index.css'

// Same-origin session cookie authenticates every call.
setConfig('resourceFetcher', frappeRequest)

const app = createApp(App)
app.use(router)
app.use(FrappeUI)
app.mount('#app')
