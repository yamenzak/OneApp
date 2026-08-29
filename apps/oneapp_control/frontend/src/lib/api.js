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
