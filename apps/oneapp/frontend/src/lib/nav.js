import { computed } from 'vue'
import { useRoute } from 'vue-router'
// An icon name that only exists in the database emits no CSS, so anything
// outside the generated set falls back to one that does.
import { appIcon } from './icons'
import { session } from './session'

/**
 * Every destination, declared once.
 *
 * The sidebar and the phone's bottom bar are two renderings of one list, not
 * two lists. Declared separately they drift — which is how the control plane
 * ended up calling the same page "Readiness" in one and "Setup" in the other.
 *
 * Inside an app the list is the app's own manifest, so a new app brings its
 * navigation with it rather than needing an edit here. An app can declare more
 * sections than a bottom bar has room for: the first four reach the bar and the
 * rest land in the More sheet, so nothing is silently unreachable on a phone.
 */
export function useNav() {
  const route = useRoute()

  const activeApp = computed(
    () => session.apps.find((a) => a.app_code === route.params.appCode) || null,
  )

  const workspaceItems = [
    { label: 'Apps', icon: 'lucide-layout-grid', to: { name: 'Launcher' } },
    { label: 'Account', icon: 'lucide-circle-user', to: { name: 'Account' } },
  ]

  const items = computed(() => {
    const app = activeApp.value
    if (!app) return workspaceItems

    const declared = app.views || []
    // A single-screen app declares no sections; its landing page is the nav.
    if (!declared.length) {
      return [
        {
          label: app.app_label,
          icon: appIcon(app.icon),
          to: { name: 'App', params: { appCode: app.app_code } },
        },
      ]
    }
    return declared.map((view) => ({
      label: view.label,
      icon: appIcon(view.icon),
      to: {
        name: 'App',
        params: { appCode: app.app_code },
        query: { view: view.view },
      },
    }))
  })

  const nav = computed(() =>
    items.value.map((item) => ({
      ...item,
      active:
        route.name === item.to.name &&
        (!item.to.query?.view || route.query.view === item.to.query.view),
    })),
  )

  return { nav, activeApp }
}
