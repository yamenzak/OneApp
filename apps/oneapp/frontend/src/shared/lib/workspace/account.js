/**
 * The workspace's own administration — who is in it, what roles it has, what
 * it is called on the internet.
 *
 * The rows are the control plane's and these endpoints are a relay: see
 * `onespace/account.py` for what is asserted and what is checked, and
 * `docs/MARKETPLACE.md` §2 for why these three questions are asked from inside
 * the workspace while billing is not.
 */

import { callMethod } from '@/shared/lib/runtime/resource'

const at = (method) => `oneapp.onespace.account.${method}`

export const account = {
  members: () => callMethod(at('members'), {}, { silent: true, method: 'GET' }),

  inviteMember: (email, fullName = '') =>
    callMethod(at('invite_member'), { email, full_name: fullName }),

  removeMember: (email) => callMethod(at('remove_member'), { email }),

  // Access and roles are one write on the control plane, because they are one
  // question about a person; this passes only what the caller changed.
  setMemberAccess: (email, access) =>
    callMethod(at('set_member_roles'), { email, access }),

  setMemberRoles: (email, roles) =>
    callMethod(at('set_member_roles'), { email, roles }),

  workspaceRoles: () => callMethod(at('roles'), {}, { silent: true, method: 'GET' }),

  saveWorkspaceRole: (label, grants, name = null) =>
    callMethod(at('save_role'), { role_label: label, grants, name }),

  deleteWorkspaceRole: (name) => callMethod(at('delete_role'), { name }),

  domain: () => callMethod(at('domain'), {}, { silent: true, method: 'GET' }),

  requestDomain: (domain) => callMethod(at('request_domain'), { domain }),

  // The marketplace. `docs/MARKETPLACE.md` §4: what this workspace could add,
  // narrowed to what it is entitled to *see*.
  marketplace: () => callMethod(at('marketplace'), {}, { silent: true, method: 'GET' }),

  enableSpace: (space) => callMethod(at('enable_space'), { space }),

  disableSpace: (space) => callMethod(at('disable_space'), { space }),

  // What removing it would uninstall, asked before the confirmation is drawn
  // so the sentence names the apps rather than saying "some data".
  removable: (space) => callMethod(at('removable'), { space }, { silent: true }),

  removeSpace: (space, confirm) =>
    callMethod(at('remove_space'), { space, confirm }),

  redeemClaimCode: (code) => callMethod(at('redeem_claim_code'), { code }),
}
