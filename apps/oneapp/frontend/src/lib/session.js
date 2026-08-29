import { useResource } from './resource'

/**
 * One round trip on boot gives the shell everything it needs: who the user is,
 * which apps they can open, and current quota and credit state.
 *
 * Watches OneApp Site State so a control-plane sync — a plan change, an app
 * granted — reaches the open tab over the socket rather than on next reload.
 */
export const sessionResource = useResource('oneapp.api.session', {
  cacheKey: 'oneapp-session',
  watch: ['OneApp Site State'],
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
  get apps() {
    return this.data.apps || []
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

  hasApp(appCode) {
    return this.apps.some((a) => a.app_code === appCode)
  },

  reload: () => sessionResource.reload(),
}

