import { watch } from 'vue'

import { useResource } from './resource'

/**
 * One round trip on boot gives the shell everything it needs: who the user is,
 * which apps they can open, and current quota and credit state.
 *
 * Watches OneSpace Site State so a control-plane sync — a plan change, an app
 * granted — reaches the open tab over the socket rather than on next reload.
 */
export const sessionResource = useResource('oneapp.api.session', {
  cacheKey: 'oneapp-session',
  watch: ['OneSpace Site State'],
})

/**
 * Settles once, the first time the session has loaded, and stays settled.
 *
 * Not `sessionResource.promise`: frappe-ui replaces that with a fresh,
 * unresolved promise after every response, so awaiting it a second time waits
 * for a fetch nobody is going to make. The router guard awaited it on every
 * navigation, which meant client-side navigation in this app worked exactly
 * once — the first load — and then silently did nothing at all. No error, no
 * console message, the URL simply never changed.
 */
export const sessionReady = new Promise((resolve) => {
  watch(
    () => sessionResource.isFinished,
    (finished) => finished && resolve(),
    { immediate: true },
  )
})

export const session = {
  resource: sessionResource,

  get data() {
    return sessionResource.data || {}
  },
  get user() {
    return this.data.user || null
  },
  get tenant() {
    return this.data.tenant || null
  },
  /** Every space this person may open, in the order the manifest gave them. */
  get spaces() {
    return this.data.spaces || []
  },
  get quota() {
    return this.data.quota || null
  },
  get credits() {
    return this.data.credits || null
  },
  get loaded() {
    return sessionResource.isFinished
  },
  get isLoggedIn() {
    return Boolean(this.user?.name && this.user.name !== 'Guest')
  },

  /**
   * Whether this person administers the workspace — the owner, an Admin member,
   * or our support signed in as Administrator.
   *
   * Not "is a System Manager": the workspace owner deliberately is not one, so
   * that question answers about us rather than about them.
   */
  get isAdmin() {
    return Boolean(this.user?.is_workspace_admin)
  },

  hasSpace(spaceCode) {
    return this.spaces.some((space) => space.space_code === spaceCode)
  },

  reload: () => sessionResource.reload(),
}

