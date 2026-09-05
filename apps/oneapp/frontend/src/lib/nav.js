import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
// An icon name that only exists in the database emits no CSS, so anything
// outside the generated set falls back to one that does.
import { spaceIcon } from './icons'
import { mail } from './mail'
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

  /**
   * The destinations that are not inside a space, declared once.
   *
   * Mail and Files are peers: the addresses somebody holds do not change when
   * they switch space, and neither does the workspace's file table. So they
   * live in the rail's footer beside the notification bell rather than in any
   * space's navigation — and, because a phone draws no rail at all, they need
   * a row in the More sheet too.
   *
   * Here rather than in App.vue for the reason this module exists: two
   * renderings of one list, not two lists. Declared in the shell, the rail had
   * Mail and the sheet did not, and on a phone the only way to it was typing
   * the URL.
   */
  const surfaces = computed(() => [
    { key: 'files', label: 'Files', icon: 'lucide-folder', to: { name: 'Drive' } },
    // Absent for somebody who holds no address, which is most people until
    // somebody sets one up. An icon that opens an empty page is worse than no
    // icon. `count` is the badge in the rail and the number in the sheet's
    // label — one figure, said twice, because a phone has only the second.
    ...(mail.held
      ? [
          {
            key: 'mail',
            label: 'Mail',
            icon: 'lucide-mail',
            to: { name: 'Mail' },
            count: mail.unread,
          },
        ]
      : []),
  ])

  return { nav, surfaces, activeSpace }
}

/**
 * Which screen in a space shows a given doctype, if any.
 *
 * A Link field holds a doctype and an id, and that is not enough to open
 * anything: this product has no route for a doctype, only for a *screen*, and
 * one space may show Project on a screen the next space does not show at all.
 * So the answer is per space, and it comes out of the session's own manifest
 * rather than from a request — every screen a person may open is already in
 * hand before the first field renders.
 *
 * Empty for a doctype no screen covers, which is the common case and not a
 * failure: a Link to Currency or UOM points at a master nobody browses, and the
 * honest answer is that there is nowhere to go.
 *
 * The first match wins where a space shows one doctype twice. That is a real
 * shape — a screen filtered to open invoices beside one showing all of them —
 * and the manifest's order is the space's own preference, which is a better
 * answer than refusing to choose.
 */
export function screenFor(spaceCode, doctype) {
  if (!spaceCode || !doctype) return ''
  const space = session.spaces.find((one) => one.space_code === spaceCode)
  const found = (space?.screens || []).find((one) => one.document_type === doctype)
  return found?.screen || ''
}
