import { reactive } from 'vue'
import { createResource } from 'frappe-ui'

/**
 * One round trip on boot gives the shell everything it needs: who the user is,
 * which apps they can open, and current quota and credit state.
 */
const resource = createResource({
  url: 'oneapp.api.session',
  cache: 'oneapp-session',
})

export const session = reactive({
  user: null,
  tenant: null,
  apps: [],
  quota: null,
  credits: null,
  loaded: false,
  error: null,

  get isLoggedIn() {
    return Boolean(this.user && this.user.name && this.user.name !== 'Guest')
  },

  hasApp(appCode) {
    return this.apps.some((a) => a.app_code === appCode)
  },

  async load({ force = false } = {}) {
    if (this.loaded && !force) return this

    try {
      const data = await resource.fetch()
      Object.assign(this, data, { loaded: true, error: null })
    } catch (e) {
      this.error = e
      this.loaded = true
    }
    return this
  },

  async refresh() {
    return this.load({ force: true })
  },
})

export function storageFraction() {
  if (!session.quota || !session.quota.storage_quota_bytes) return 0
  return session.quota.storage_used_bytes / session.quota.storage_quota_bytes
}

export function formatBytes(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}
