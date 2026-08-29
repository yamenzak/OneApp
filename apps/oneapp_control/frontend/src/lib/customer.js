import { computed, reactive } from 'vue'

import { callMethod, useResource } from './resource'

const method = (name) => `oneapp_control.api.customer.${name}`

export const customer = {
  workspaces: () => callMethod(method('my_workspaces'), {}, { silent: true }),
  overview: (workspace) => callMethod(method('overview'), { workspace }, { silent: true }),
  creditHistory: (workspace) => callMethod(method('credit_history'), { workspace }, { silent: true }),
  invoices: (workspace) => callMethod(method('invoices'), { workspace }, { silent: true }),
  packs: () => callMethod(method('packs'), {}, { silent: true }),

  buyCredits: (workspace, pack) => callMethod(method('buy_credits'), { workspace, pack }),
  buyStorage: (workspace, pack) => callMethod(method('buy_storage'), { workspace, pack }),
  billingPortal: (workspace) => callMethod(method('billing_portal'), { workspace }),

  domainGuide: (workspace) => callMethod(method('domain_instructions'), { workspace }, { silent: true }),
  addDomain: (workspace, domain) =>
    callMethod(method('request_custom_domain'), { workspace, domain }, {
      successMessage: 'Domain queued — we are verifying your DNS',
    }),
}

/**
 * The workspaces this account owns.
 *
 * An account may own several — signing up for a company and later for something
 * at home is ordinary — so the portal is always scoped to one of them, chosen
 * here rather than assumed.
 */
export const workspaces = reactive({
  list: [],
  current: null,
  loading: true,

  get selected() {
    return this.list.find((w) => w.name === this.current) || null
  },

  async load(preferred = null) {
    this.loading = true
    try {
      this.list = (await customer.workspaces()) || []
      const known = this.list.some((w) => w.name === preferred)
      this.current = known ? preferred : this.list[0]?.name || null
    } catch (e) {
      // An expired session is the ordinary case here, not an error worth
      // showing: send them to sign in and come back to the same page. Anything
      // else is a real failure and should surface.
      if (isNotSignedIn(e)) return signIn()
      throw e
    } finally {
      this.loading = false
    }
  },
})

function isNotSignedIn(error) {
  const status = error?.httpStatus ?? error?.status
  const type = error?.exc_type || error?.exception || ''
  return status === 401 || status === 403 || /PermissionError/.test(type)
}

/**
 * Hand off to Frappe's login page, which returns here afterwards.
 *
 * A full navigation rather than a router push: the session cookie is set by the
 * server, so the SPA has to be reloaded for it to take effect.
 */
export function signIn() {
  const back = encodeURIComponent(window.location.pathname + window.location.search)
  window.location.href = `/login?redirect-to=${back}`
}

export const hasWorkspaces = computed(() => workspaces.list.length > 0)

export function useOverview(workspaceRef) {
  return useResource(`oneapp_control.api.customer.overview`, {
    params: () => ({ workspace: workspaceRef.value }),
    refetch: true,
    watch: ['Tenant'],
  })
}

/**
 * Who can sign in to a workspace.
 *
 * An invite is a row in the control plane; the workspace's site turns it into
 * an account on its next sync, because nothing here can write into a tenant's
 * database. The page says so rather than leaving someone wondering why their
 * colleague cannot sign in yet.
 */
export function useMembers(workspaceRef) {
  return useResource('oneapp_control.api.customer.members', {
    params: () => ({ workspace: workspaceRef.value }),
    refetch: true,
    watch: ['Tenant'],
  })
}

export const inviteMember = (workspace, payload) =>
  callMethod('oneapp_control.api.customer.invite_member', { workspace, ...payload }, {
    successMessage: 'Invited — they can sign in once the workspace next syncs',
  })

export const removeMember = (workspace, email) =>
  callMethod('oneapp_control.api.customer.remove_member', { workspace, email }, {
    successMessage: 'Removed',
  })

/** What this workspace can open — the same manifest its launcher renders. */
export function useApps(workspaceRef) {
  return useResource('oneapp_control.api.customer.apps', {
    params: () => ({ workspace: workspaceRef.value }),
    watch: ['App Entitlement'],
  })
}

/**
 * What the workspace is on and what else it could be on.
 *
 * Every plan carries every feature — they differ only in quotas — so the
 * comparison is the numbers, and a plan too small for what is already stored
 * comes back marked rather than merely listed.
 */
export function usePlans(workspaceRef) {
  return useResource('oneapp_control.api.customer.plans', {
    params: () => ({ workspace: workspaceRef.value }),
    watch: ['Tenant'],
  })
}
