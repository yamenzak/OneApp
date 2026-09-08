import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
// An icon name that only exists in the database emits no CSS, so anything
// outside the generated set falls back to one that does.
import { spaceIcon } from '@/lib/shell/icons'
import { assistant, assistantName, openAssistant } from '@/lib/shell/assistant'
import { openSettings } from '@/lib/shell/settings'
import { mail } from '@/lib/shell/mail'
import { session } from '@/lib/shell/session'
import { workspace } from '@/lib/workspace'
import { VIEW_TYPES, viewTypesOf } from '@/lib/screen/viewTypes'
import { __ } from '@/lib/runtime/translate'

/**
 * What the reader has open, for the assistant to be scoped to.
 *
 * Read off the route rather than passed down, because the rail is not inside
 * the page and the panel is not inside either of them. Only three facts, and
 * only the label is for the browser — the server resolves the space, the screen
 * and the record through the same checks a click goes through, so a stale URL
 * narrows to nothing rather than widening anything.
 *
 * Null outside a space. Mail, the Drive and the calendar are not screens, and
 * an assistant told it is "on Files" would be told something its tools cannot
 * act on.
 */
export function openContext(route, spaces = session.spaces) {
  const code = route?.params?.spaceCode
  const screen = route?.query?.screen
  if (!code || !screen) return null

  const space = spaces.find((one) => one.space_code === code)
  const found = (space?.screens || []).find((one) => one.screen === screen)
  if (!found) return null

  const record = route.query.record || ''
  return {
    space: code,
    screen,
    ...(record ? { docname: record } : {}),
    // Said to the reader, not to the model: the panel puts it under its own
    // title so what the answers will be about is legible before the first
    // question rather than inferred from the first answer.
    label: record ? `${found.label} · ${record}` : found.label,
  }
}


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

  const workspaceItems = [
    { label: __('Spaces'), icon: 'lucide-layout-grid', to: { name: 'Launcher' } },
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

/**
 * The destinations that are not inside a space, declared once.
 *
 * Mail, Files and the assistant are peers: the addresses somebody holds do not
 * change when they switch space, neither does the workspace's file table, and
 * the assistant answers across every space its reader can open. Here rather
 * than in App.vue for the reason this module exists — declared in the shell,
 * the rail had Mail and the More sheet did not.
 */
  const surfaces = computed(() => [
    // `brand` beside `icon`: the mark is what a desktop draws, the lucide name
    // is what the phone's sheet and the bottom bar draw, because a 100×100
    // gradient at 16px in a row of outlines is a smudge among glyphs.
    {
      key: 'files',
      label: __('Files'),
      icon: 'lucide-folder',
      brand: 'onestorage',
      to: { name: 'Drive' },
    },
    // Absent until the server says the workspace has one — AI can be switched
    // off, unconfigured, or suspended by an operator, and a rail entry that
    // leads to "not switched on here" is worse than no entry.
    // Settings, for everybody rather than for admins.
    //
    // It used to be one row in the account menu, offered only where
    // `session.isAdmin`, because every tab in it was the workspace's and a
    // member opening it would have been refused by all of them. The dialog has
    // a "You" section now — your name, your password, what you are told about,
    // how this looks — so it is a door that opens for whoever presses it, and
    // it belongs in the rail beside the other things that are not inside a
    // space. `oneapp_core/tabs.py` decides what is behind it.
    {
      key: 'settings',
      label: __('Settings'),
      icon: 'lucide-settings',
      act: () => openSettings(),
    },
    // `act` and not `to`: this one opens a panel over the page rather than
    // navigating to one. Going somewhere to ask about the thing you were
    // looking at is the shape this exists to avoid.
    ...(assistant.available
      ? [{
        key: 'chat',
        label: assistantName.value,
        icon: 'lucide-sparkles',
        brand: 'oneai',
        to: { name: 'Chat' },
        act: () => openAssistant(openContext(route)),
      }]
      : []),
    // Always here, unlike Mail: everybody has days.
    {
      key: 'calendar',
      label: __('Calendar'),
      icon: 'lucide-calendar',
      brand: 'onecalendar',
      to: { name: 'Calendar' },
    },
    // What the workspace could add. Offered to whoever may actually add it —
    // `require_workspace_admin` on the control plane admits the owner and an
    // Admin member, and a rail icon leading to a page of refusals is worse
    // than no icon. `docs/MARKETPLACE.md` §4.
    ...(session.isAdmin
      ? [{
        key: 'marketplace',
        label: __('Add a space'),
        icon: 'lucide-store',
        brand: 'onemarket',
        to: { name: 'Marketplace' },
      }]
      : []),
    // Absent for somebody who holds no address, which is most people until
    // somebody sets one up. `count` is the badge in the rail and the number in
    // the sheet's label — one figure, said twice.
    ...(mail.held
      ? [
          {
            key: 'mail',
            label: __('Mail'),
            icon: 'lucide-mail',
            brand: 'onemail',
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
