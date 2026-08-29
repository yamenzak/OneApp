import { reactive } from 'vue'
import { api } from './api'
import { notifyError } from './notify'

/**
 * Configuration readiness.
 *
 * Loaded once at boot and re-checked after any settings change. The admin UI
 * gates provisioning on it rather than letting a half-configured run fail
 * several steps in, after a real site already exists on Frappe Cloud.
 */
export const setup = reactive({
  loading: true,
  error: null,
  canProvision: false,
  canBill: false,
  checks: [],
  summary: null,

  group(name) {
    return this.checks.filter((c) => c.group === name)
  },

  get blockers() {
    return this.group('blocking').filter((c) => !c.ok)
  },

  async load() {
    this.loading = true
    try {
      const data = await api.readiness()
      this.canProvision = data.can_provision
      this.canBill = data.can_bill
      this.checks = data.checks
      this.summary = data.summary
      this.error = null
    } catch (e) {
      this.error = e
      notifyError(e)
    } finally {
      this.loading = false
    }
  },
})
