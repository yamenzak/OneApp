import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
// An icon name that only exists in the database emits no CSS, so anything
// outside the generated set falls back to one that does.
import { spaceIcon } from '@/modules/onespace/lib/shell/icons'
import { session } from '@/modules/onespace/lib/shell/session'
import { workspace } from '@/shared/lib/workspace'
import { VIEW_TYPES, viewTypesOf } from '@/modules/onespace/lib/screen/viewTypes'
import { NARROW } from '@/modules/onespace/lib/screen/narrowing'
import { useApps } from '@/modules/onespace/lib/shell/apps'
export { includedContexts, openContext, openContexts } from '@/modules/onespace/lib/shell/context'
import { __ } from '@/shared/lib/runtime/translate'

/**
 * Every destination, declared once.
 *
 * The sidebar and the phone's bottom bar are two renderings of one list, not
 * two lists — declared separately they drift, which is how one page came to be
 * called "Readiness" in the rail and "Setup" in the bar.
 *
 * Inside a space the list is the space's own manifest. A space can declare more
 * screens than a bottom bar has room for: the first four reach the bar and the
 * rest land in the More sheet.
 */
export function useNav() {
  const route = useRoute()

  const activeSpace = computed(
    () => session.spaces.find((s) => s.space_code === route.params.spaceCode) || null,
  )

  // The rail on a route that is not inside a space — your account, the
  // marketplace. "Spaces" used to head it and pointed at a page of cards;
  // that page is gone and the corner is where a space is chosen, so what is
  // left is the one destination that is genuinely not in any space.
  const workspaceItems = [
    { label: __('Account'), icon: 'lucide-circle-user', to: { name: 'Account' } },
  ]

  const screenRoute = (space, screen, viewType, layout) => ({
    name: 'Screen',
    params: { spaceCode: space.space_code },
    query: {
      screen: screen.screen,
      // Only when it is not the screen's own first type: a query parameter
      // that repeats the default is noise in every link.
      ...(viewType && viewType !== viewTypesOf(screen)[0] ? { type: viewType } : {}),
      ...(layout ? { layout } : {}),
      // A narrowing survives a change of view and nothing else. "This
      // project's work as a calendar" is the same question as the board it was
      // switched from; the next screen along in the rail is a different one,
      // and carrying somebody's project onto it would narrow a list by a
      // record it is not about.
      ...(route.query[NARROW] && route.query.screen === screen.screen
        ? { [NARROW]: route.query[NARROW] }
        : {}),
    },
  })

  // The space's named layouts, keyed by screen. Fetched once when a space is
  // opened rather than per screen: a request per item to draw a menu is a menu
  // that arrives in pieces.
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

    // A screen may be routable without being a destination — §E5. The rail is
    // a list of places to go and work; a reference shelf sitting in it beside
    // Sources and Deliveries reads as a fourth thing to configure and is not
    // one. It is still a screen and still reachable; something else links to
    // it.
    const declared = (space.screens || []).filter((one) => !one.hide_in_nav)
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
    return declared.map((screen, at) => ({
      key: screen.screen,
      label: screen.label,
      icon: spaceIcon(screen.icon),
      // The heading this screen sits under, and only on the first of a run.
      // The rail draws a heading when the group *changes*, which keeps this a
      // flat ordered list — the record pane, the phone's More sheet and the
      // active-screen marking all walk it, and none of them wants a tree.
      //
      // A space with six screens declares none and gets none: a heading over
      // every item is a rail that is twice as tall and says nothing. The
      // operator console has thirty and earns them.
      heading:
        screen.screen_group && screen.screen_group !== declared[at - 1]?.screen_group
          ? screen.screen_group
          : '',
      to: screenRoute(space, screen),
      // The ways this screen can be drawn, then the layouts somebody named.
      // Two groups rather than one list, because they answer different
      // questions — "as a board or a list" and "which slice of it".
      viewTypes: viewTypesOf(screen).map((type) => ({
        key: type,
        label: VIEW_TYPES[type].label,
        icon: VIEW_TYPES[type].icon,
        to: screenRoute(space, screen, type),
      })),
      layouts: (layouts.value[screen.screen] || []).map((layout) => ({
        key: layout.name,
        label: layout.label,
        // The view's own icon where somebody gave it one, else who it is for.
        icon: layout.icon || (layout.shared ? 'lucide-users' : 'lucide-bookmark'),
        to: screenRoute(space, screen, layout.view_type, layout.name),
      })),
    }))
  })

  const activeType = computed(() => route.query.type || '')
  const activeLayout = computed(() => route.query.layout || '')

  // A space opened without a screen in the URL renders its first one, so the
  // sidebar has to mark the same item. Reading `route.query.screen` alone left
  // the whole list unmarked on the one route people arrive at from the
  // launcher.
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
          // A layout is open, so no view type is what you are looking at.
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

  // The live apps that are not inside a space — Mail, Files, the calendar,
  // the assistant — plus settings, which is not an app. One catalogue, in
  // `lib/shell/apps.js`, so the rail and the board are two renderings of one
  // list rather than two lists: declared separately they drift, which is how
  // the rail came to have Mail and the More sheet not to.
  const { services } = useApps()

  return { nav, services, activeSpace }
}

/**
 * Which screen in a space shows a given doctype, if any.
 *
 * A Link field holds a doctype and an id, and that is not enough to open
 * anything: this product has no route for a doctype, only for a *screen*. The
 * answer is per space and comes out of the session's own manifest.
 *
 * Empty for a doctype no screen covers, which is the common case and not a
 * failure. The first match wins where a space shows one doctype twice — the
 * manifest's order is the space's own preference.
 */
export function screenFor(spaceCode, doctype) {
  if (!spaceCode || !doctype) return ''
  const space = session.spaces.find((one) => one.space_code === spaceCode)
  const found = (space?.screens || []).find((one) => one.document_type === doctype)
  return found?.screen || ''
}
