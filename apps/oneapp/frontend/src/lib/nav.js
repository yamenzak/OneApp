import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
// An icon name that only exists in the database emits no CSS, so anything
// outside the generated set falls back to one that does.
import { spaceIcon } from './icons'
import { session } from './session'
import { workspace } from './workspace'
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

  const screenRoute = (space, screen, viewType, layout) => ({
    name: 'Screen',
    params: { spaceCode: space.space_code },
    query: {
      screen: screen.screen,
      // Only when it is not the screen's own first type: a query parameter
      // that repeats the default is noise in every link and every bookmark.
      ...(viewType && viewType !== viewTypesOf(screen)[0] ? { type: viewType } : {}),
      ...(layout ? { layout } : {}),
    },
  })

  // The space's named layouts, keyed by screen. Fetched once when a space is
  // opened rather than per screen: the sidebar lists what every screen can be
  // looked at as, and a request per item to draw a menu is a menu that
  // arrives in pieces.
  const layouts = ref({})
  watch(
    () => activeSpace.value?.space_code,
    async (code) => {
      layouts.value = code ? (await workspace.spaceLayouts(code)) || {} : {}
    },
    { immediate: true },
  )

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
      // What the sidebar offers when this screen is expanded: the ways it can
      // be drawn, then the layouts somebody named. Two groups rather than one
      // list, because they answer different questions — "as a board or a
      // list" and "which slice of it" — and a menu that mixes them reads as
      // one set of alternatives when picking a layout leaves the view type
      // where it was.
      viewTypes: viewTypesOf(screen).map((type) => ({
        key: type,
        label: VIEW_TYPES[type].label,
        icon: VIEW_TYPES[type].icon,
        to: screenRoute(space, screen, type),
      })),
      layouts: (layouts.value[screen.screen] || []).map((layout) => ({
        key: layout.name,
        label: layout.label,
        // The view's own icon where somebody gave it one. Otherwise who it is
        // for, which is the next most useful thing a row can say.
        icon: layout.icon || (layout.shared ? 'lucide-users' : 'lucide-bookmark'),
        to: screenRoute(space, screen, layout.view_type, layout.name),
      })),
    }))
  })

  const activeType = computed(() => route.query.type || '')
  const activeLayout = computed(() => route.query.layout || '')

  // A space opened without a screen in the URL renders its first one — that is
  // what the server resolves to — so the sidebar has to mark the same item.
  // Reading `route.query.screen` alone left the whole list unmarked on the one
  // route people arrive at from the launcher.
  const activeScreen = computed(
    () => route.query.screen || items.value[0]?.to.query?.screen || '',
  )

  const nav = computed(() =>
    items.value.map((item) => {
      const here = activeScreen.value === item.to.query?.screen
      return {
        ...item,
        active: route.name === item.to.name && (!item.to.query?.screen || here),
        viewTypes: (item.viewTypes || []).map((type) => ({
          ...type,
          // A layout is open, so no view type is what you are looking at —
          // marking one active would claim the list is unfiltered.
          active:
            here &&
            !activeLayout.value &&
            (activeType.value || item.viewTypes[0].key) === type.key,
        })),
        layouts: (item.layouts || []).map((layout) => ({
          ...layout,
          active: here && activeLayout.value === layout.key,
        })),
      }
    }),
  )

  return { nav, activeSpace }
}
