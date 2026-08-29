/**
 * Control-plane endpoints.
 *
 * Everything goes through the shared resource layer, so each call is unwrapped,
 * failures render as parsed Frappe errors, and mutations announce themselves.
 */

import { callMethod } from './resource'

const method = (name) => `oneapp_control.api.${name}`

export const api = {
  readiness: () => callMethod(method('setup.readiness'), {}, { silent: true }),

  checkSlug: (slug) => callMethod(method('admin.check_slug'), { slug }, { silent: true }),
  createTenant: (payload) =>
    callMethod(method('admin.create_tenant'), payload, {
      successMessage: 'Tenant created — provisioning started',
    }),
  provision: (tenant) =>
    callMethod(method('admin.provision'), { tenant }, { successMessage: 'Provisioning queued' }),
  suspend: (tenant, reason) =>
    callMethod(method('admin.suspend'), { tenant, reason }, { successMessage: 'Suspension queued' }),
  resume: (tenant) =>
    callMethod(method('admin.resume'), { tenant }, { successMessage: 'Resume queued' }),
  addDomain: (tenant, domain) =>
    callMethod(method('admin.add_custom_domain'), { tenant, domain }, {
      successMessage: 'Domain queued',
    }),

  shards: () => callMethod(method('admin.shards'), {}, { silent: true }),
  pressCapacity: () => callMethod(method('admin.press_capacity'), {}, { silent: true }),
  benchApps: (releaseGroup) =>
    callMethod(method('admin.bench_apps'), { release_group: releaseGroup }, {
      silent: true, method: 'GET',
    }),
  shard: (shard) => callMethod(method('admin.shard'), { shard }, { silent: true, method: 'GET' }),
  updateShard: (shard, values) =>
    callMethod(method('admin.update_shard'), { shard, values }, {
      successMessage: 'Shard updated',
    }),
  createShard: (payload) =>
    callMethod(method('admin.create_shard'), payload, {
      successMessage: 'Shard registered — the allocator will use it on the next signup',
    }),
  grantApp: (tenant, appCode) =>
    callMethod(method('admin.grant_app'), { tenant, app_code: appCode }, {
      successMessage: 'App enabled',
    }),
  revokeApp: (tenant, appCode) =>
    callMethod(method('admin.revoke_app'), { tenant, app_code: appCode }, {
      successMessage: 'App disabled',
    }),

  // What Frappe Cloud knows about a tenant's site. Read live: the control
  // plane holds intent, press holds what is actually running, and when the two
  // disagree the answer is nearly always in press.
  siteState: (tenant) => callMethod(method('admin.site_state'), { tenant }, { silent: true, method: 'GET' }),
  siteJobs: (tenant) => callMethod(method('admin.site_jobs'), { tenant }, { silent: true, method: 'GET' }),
  siteBackups: (tenant) => callMethod(method('admin.site_backups'), { tenant }, { silent: true, method: 'GET' }),
  siteDomains: (tenant) => callMethod(method('admin.site_domains'), { tenant }, { silent: true, method: 'GET' }),
  supportLogins: (tenant) => callMethod(method('admin.support_logins'), { tenant }, { silent: true, method: 'GET' }),

  takeBackup: (tenant) =>
    callMethod(method('admin.take_backup'), { tenant }, {
      successMessage: 'Backup started',
    }),
  backupDownload: (tenant, backup, file) =>
    callMethod(method('admin.backup_download'), { tenant, backup, file }, {
      silent: true, method: 'GET',
    }),
  setPrimaryDomain: (tenant, domain) =>
    callMethod(method('admin.set_primary_domain'), { tenant, domain }, {
      successMessage: 'Primary domain updated',
    }),
  removeSiteDomain: (tenant, domain) =>
    callMethod(method('admin.remove_domain'), { tenant, domain }, {
      successMessage: 'Domain removed',
    }),
  supportLogin: (tenant, reason) =>
    callMethod(method('admin.support_login'), { tenant, reason }, { silent: true }),

  // The rest of the control plane, so the desk is never the only way in.
  signups: () => callMethod(method('admin.signups'), {}, { silent: true, method: 'GET' }),
  webhookEvents: (status) =>
    callMethod(method('admin.webhook_events'), { status }, { silent: true, method: 'GET' }),
  replayWebhook: (event) =>
    callMethod(method('admin.replay_webhook'), { event }, { successMessage: 'Event replayed' }),
  standbyPool: () => callMethod(method('admin.standby_pool'), {}, { silent: true, method: 'GET' }),

  // The operator's question is what to *grant*, so this is every app with a
  // flag — not admin.tenant_apps, which answers the launcher's question and
  // returns only what the workspace already has.
  tenantAppAccess: (tenant) =>
    callMethod(method('admin.tenant_app_access'), { tenant }, { silent: true, method: 'GET' }),
  tenantBilling: (tenant) =>
    callMethod(method('admin.tenant_billing'), { tenant }, { silent: true, method: 'GET' }),
  adoptPlanTerms: (tenant) =>
    callMethod(method('admin.adopt_plan_terms'), { tenant }, {
      successMessage: 'Moved onto the plan\'s current terms',
    }),
  setTenantPlan: (tenant, plan) =>
    callMethod(method('admin.set_tenant_plan'), { tenant, plan }, {
      successMessage: 'Plan changed',
    }),

  pushBenchConfig: (shard) =>
    callMethod('oneapp_control.provisioning.bench_config.push_to_shard', { shard }, {
      successMessage: 'Config pushed to bench',
    }),
  pushBenchConfigAll: () =>
    callMethod('oneapp_control.provisioning.bench_config.push_to_all_shards', {}, {
      successMessage: 'Config pushed to all shards',
    }),
}

/**
 * Documents and lists come from the shared document layer, which wraps
 * frappe-ui's own `useList` / `useDoc`. This file used to hand-roll both on top
 * of `frappe.client.get_list` — and named its helper `useList`, shadowing the
 * library's.
 */
export { useDocList, useDocument, useDocWrites } from './resource'
