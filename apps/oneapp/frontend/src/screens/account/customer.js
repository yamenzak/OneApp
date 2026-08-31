/**
 * The customer's account, for the account Space.
 *
 * Every call here is a whitelisted method on this same site — the control
 * plane, where `oneapp` is installed for its shell. Nothing is cross-site, and
 * nothing needs to be: this is exactly why the account area belongs here rather
 * than inside a tenant workspace. A person with three tenancies authenticates
 * once, in the one place that knows about all three.
 *
 * Ported from the portal SPA. The calls and their reasoning are unchanged; only
 * the import paths moved.
 */

import { computed, reactive } from 'vue'

import { callMethod, useResource } from '../../lib/resource'

const method = (name) => `oneapp_control.api.customer.${name}`

export const customer = {
  workspaces: () => callMethod(method('my_workspaces'), {}, { silent: true }),
  overview: (workspace) => callMethod(method('overview'), { workspace }, { silent: true }),
  creditHistory: (workspace) => callMethod(method('credit_history'), { workspace }, { silent: true }),
  invoices: (workspace) => callMethod(method('invoices'), { workspace }, { silent: true }),
  packs: () => callMethod(method('packs'), {}, { silent: true }),

  buyCredits: (workspace, pack) => callMethod(method('buy_credits'), { workspace, pack }),

  // Storage is an add-on rather than a pack now: bought per month against the
  // subscription, prorated, and released the same way. `addons` answers with the
  // catalogue and what this workspace holds together, because a stepper needs
  // both in the same render.
  addons: (workspace) =>
    callMethod(method('addons'), { workspace }, { silent: true, method: 'GET' }),
  setAddon: (workspace, addon, quantity) =>
    callMethod(
      method('set_addon'),
      { workspace, addon, quantity },
      { successMessage: quantity ? 'Added — it is on your next invoice' : 'Released' },
    ),
  billingPortal: (workspace) => callMethod(method('billing_portal'), { workspace }),
  // Ours, not the Stripe portal: the portal cannot know our quotas, so it would
  // sell a downgrade to a workspace already holding more than the smaller plan
  // allows. See api/customer.change_plan.
  changePlan: (workspace, plan, interval = 'Monthly') =>
    callMethod(method('change_plan'), { workspace, plan, interval }, {
      successMessage: 'Plan changed',
    }),

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

export const setMemberRoles = (workspace, email, roles, access) =>
  callMethod(
    'oneapp_control.api.customer.set_member_roles',
    { workspace, email, roles, access },
    { successMessage: 'Saved — it applies on the next sync' },
  )

/**
 * The roles a workspace may hand out, and the parts a new one is built from.
 *
 * Shipped roles come from the spaces this workspace is entitled to; custom ones
 * it built itself. One list, because the person handing them out does not care
 * which of the two a role is — only what it lets somebody do.
 */
export function useRoles(workspaceRef) {
  return useResource('oneapp_control.api.customer.roles', {
    params: () => ({ workspace: workspaceRef.value }),
    refetch: true,
    watch: ['Workspace Role'],
  })
}

export const saveRole = (workspace, payload) =>
  callMethod('oneapp_control.api.customer.save_role', { workspace, ...payload }, {
    successMessage: 'Saved — it applies on the next sync',
  })

export const deleteRole = (workspace, name) =>
  callMethod('oneapp_control.api.customer.delete_role', { workspace, name }, {
    successMessage: 'Deleted',
  })

/** What this workspace can open — the same manifest its launcher renders. */
export function useApps(workspaceRef) {
  return useResource('oneapp_control.api.customer.apps', {
    params: () => ({ workspace: workspaceRef.value }),
    watch: ['Space Entitlement'],
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
