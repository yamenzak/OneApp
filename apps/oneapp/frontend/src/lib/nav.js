import { computed } from 'vue'
import { useRoute } from 'vue-router'
// An icon name that only exists in the database emits no CSS, so anything
// outside the generated set falls back to one that does.
import { spaceIcon } from './icons'
import { session } from './session'
import { VIEW_TYPES, viewTypesOf } from './viewTypes'

/**
 * Every destination, declared once.
 *
 * The sidebar and the phone's bottom bar are two renderings of one list, not
 * two lists. Declared separately they drift — which is how the control plane
 * ended up calling the same page "Readiness" in one and "Setup" in the other.
 *
 * Inside a space the list is the space's own manifest, so a new space brings
 * its navigation with it rather than needing an edit here. A space can declare
 * more screens than a bottom bar has room for: the first four reach the bar and
 * the rest land in the More sheet, so nothing is silently unreachable.
 */
export function useNav() {
  const route = useRoute()

  const activeSpace = computed(
    () => session.spaces.find((s) => s.space_code === route.params.spaceCode) || null,
  )

  const workspaceItems = [
    { label: 'Spaces', icon: 'lucide-layout-grid', to: { name: 'Launcher' } },
    { label: 'Account', icon: 'lucide-circle-user', to: { name: 'Account' } },
  ]

  const screenRoute = (space, screen, viewType) => ({
    name: 'Screen',
    params: { spaceCode: space.space_code },
    query: {
      screen: screen.screen,
      // Only when it is not the screen's own first type: a query parameter
      // that repeats the default is noise in every link and every bookmark.
      ...(viewType && viewType !== viewTypesOf(screen)[0] ? { type: viewType } : {}),
    },
  })

  const items = computed(() => {
    const space = activeSpace.value
    if (!space) return workspaceItems

    const declared = space.screens || []
    // A space with one screen declares none; its landing page is the nav.
    if (!declared.length) {
      return [
        {
          label: space.space_label,
          icon: spaceIcon(space.icon),
          to: { name: 'Screen', params: { spaceCode: space.space_code } },
        },
      ]
    }
    return declared.map((screen) => ({
      key: screen.screen,
      label: screen.label,
      icon: spaceIcon(screen.icon),
      to: screenRoute(space, screen),
      // What the sidebar offers when this screen is expanded. A screen that
      // only knows one way to be looked at has nothing to expand.
      viewTypes: viewTypesOf(screen).map((type) => ({
        key: type,
        label: VIEW_TYPES[type].label,
        icon: VIEW_TYPES[type].icon,
        to: screenRoute(space, screen, type),
      })),
    }))
  })

  const activeType = computed(() => route.query.type || '')

  const nav = computed(() =>
    items.value.map((item) => ({
      ...item,
      active:
        route.name === item.to.name &&
        (!item.to.query?.screen || route.query.screen === item.to.query.screen),
      viewTypes: (item.viewTypes || []).map((type) => ({
        ...type,
        active:
          route.query.screen === item.to.query?.screen &&
          (activeType.value || item.viewTypes[0].key) === type.key,
      })),
    })),
  )

  return { nav, activeSpace }
}
