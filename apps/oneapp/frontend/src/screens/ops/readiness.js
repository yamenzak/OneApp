/**
 * Configuration readiness, for the operator console.
 *
 * The control plane's own `setup.readiness` endpoint, which is a whitelisted
 * method on the same site — so this reaches it exactly as any other screen
 * reaches a method, with no cross-site anything.
 *
 * Reactive and loaded on demand rather than a `useResource`: this is one
 * screen's state, re-checked after a settings change, and the shape the
 * endpoint returns (grouped checks plus two verdicts) is not a list of records.
 */

import { reactive } from 'vue'

import { callMethod } from '../../lib/resource'
import { notifyError } from '../../lib/notify'

export const readiness = reactive({
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
      const data = await callMethod(
        'oneapp_control.api.setup.readiness',
        {},
        { silent: true },
      )
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
