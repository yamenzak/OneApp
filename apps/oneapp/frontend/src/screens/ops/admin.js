/**
 * The control-plane endpoints the operator Space's bespoke screens call.
 *
 * Every screen over a doctype talks to the space resolver and needs none of
 * this. What is left here is the part that is not a doctype at all: what Frappe
 * Cloud says about a site, its backups and domains, a support sign-in, and the
 * billing calls that do more than write a field.
 *
 * The methods themselves are unchanged and still guard themselves — each is
 * `_require_manager()` on the control plane. This is only how the screens name
 * them.
 */

import { callMethod } from '../../lib/resource'

const method = (name) => `oneapp_control.api.admin.${name}`

// A press read reports failure in-band as `{error}` rather than raising, so a
// panel can name what is missing instead of a toast saying something went
// wrong. `silent` keeps the toast out of the way of that.
const read = (name) => (params) => callMethod(method(name), params, { silent: true, method: 'GET' })

export const admin = {
  siteState: (tenant) => read('site_state')({ tenant }),
  siteJobs: (tenant) => read('site_jobs')({ tenant }),
  siteBackups: (tenant) => read('site_backups')({ tenant }),
  siteDomains: (tenant) => read('site_domains')({ tenant }),
  supportLogins: (tenant) => read('support_logins')({ tenant }),
  tenantAppAccess: (tenant) => read('tenant_app_access')({ tenant }),
  tenantBilling: (tenant) => read('tenant_billing')({ tenant }),
  // Where this workspace stands on the ladder: the clock, the copy we hold, the
  // backups arriving from the site, and what the sweep actually did. One call
  // because "why is this suspended" needs all four at once.
  tenantLifecycle: (tenant) => read('tenant_lifecycle')({ tenant }),

  provision: (tenant) =>
    callMethod(method('provision'), { tenant }, { successMessage: 'Provisioning queued' }),
  suspend: (tenant, reason) =>
    callMethod(method('suspend'), { tenant, reason }, { successMessage: 'Suspension queued' }),
  resume: (tenant) =>
    callMethod(method('resume'), { tenant }, { successMessage: 'Resume queued' }),

  takeBackup: (tenant) =>
    callMethod(method('take_backup'), { tenant }, { successMessage: 'Backup started' }),
  backupDownload: (tenant, backup, file) =>
    callMethod(method('backup_download'), { tenant, backup, file }, { silent: true, method: 'GET' }),
  setPrimaryDomain: (tenant, domain) =>
    callMethod(
      method('set_primary_domain'),
      { tenant, domain },
      { successMessage: 'Primary domain updated' },
    ),
  removeSiteDomain: (tenant, domain) =>
    callMethod(method('remove_domain'), { tenant, domain }, { successMessage: 'Domain removed' }),

  // Deliberately not silent and deliberately not a toast on success: what comes
  // back is a URL into somebody else's workspace, and the screen opens it.
  supportLogin: (tenant, reason) =>
    callMethod(method('support_login'), { tenant, reason }, { silent: true }),

  grantApp: (tenant, spaceCode) =>
    callMethod(method('grant_app'), { tenant, space_code: spaceCode }, { successMessage: 'App enabled' }),
  revokeApp: (tenant, spaceCode) =>
    callMethod(method('revoke_app'), { tenant, space_code: spaceCode }, { successMessage: 'App disabled' }),

  // Per-tenant, which is the cut the AI usage screen cannot make: that one is
  // every call on the site. `reconcile` takes nothing, so it is a button on the
  // panel rather than an action against a record.
  aiUsage: (params) => read('ai_usage')(params),
  reconcileAiUsage: () =>
    callMethod(method('reconcile_ai_usage'), {}, { successMessage: 'Compared against the gateway log' }),

  // The only way credits arrive that is not Stripe telling us something
  // happened. A reason is required and lands on the ledger row.
  grantCredits: (tenant, credits, reason) =>
    callMethod(
      method('grant_credits'),
      { tenant, credits, reason },
      { successMessage: 'Credits added' },
    ),

  holdLifecycle: (tenant) =>
    callMethod(method('hold_lifecycle'), { tenant }, { successMessage: 'Held from the lifecycle' }),
  releaseLifecycle: (tenant) =>
    callMethod(
      method('release_lifecycle'),
      { tenant },
      { successMessage: 'Released into the lifecycle' },
    ),
  runLifecycle: (tenant) =>
    callMethod(method('run_lifecycle'), { tenant }, { successMessage: 'Lifecycle applied' }),
  takeColdCopy: (tenant) =>
    callMethod(method('take_cold_copy'), { tenant }, { successMessage: 'Cold copy requested' }),
  restoreFromCold: (tenant) =>
    callMethod(method('restore_from_cold'), { tenant }, { successMessage: 'Restore queued' }),

  adoptPlanTerms: (tenant) =>
    callMethod(
      method('adopt_plan_terms'),
      { tenant },
      { successMessage: "Moved onto the plan's current terms" },
    ),
  setTenantPlan: (tenant, plan) =>
    callMethod(method('set_tenant_plan'), { tenant, plan }, { successMessage: 'Plan changed' }),
}
