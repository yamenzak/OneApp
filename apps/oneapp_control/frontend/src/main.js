import { createApp } from 'vue'
import { setConfig, frappeRequest } from '@/ui'

import App from './App.vue'
import router from './router'
import './index.css'

// Same-origin session cookie authenticates every call — no tokens, no CORS.
setConfig('resourceFetcher', frappeRequest)

createApp(App).use(router).mount('#app')
