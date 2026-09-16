/**
 * Every app in the product, and what this workspace has of it.
 *
 * The shell used to answer "where else can I go" with a list of five, written
 * into `nav.js` an entry at a time as each one shipped. That list was true and
 * it was not the answer: the design draws twenty-seven marks, the product
 * builds nine of them, and a workspace holds some subset of *those* — so the
 * five were the intersection of three different facts, and a person looking at
 * them could not tell which of the other twenty-two did not exist, were not
 * switched on, or were one click from being added.
 *
 * `docs/UNIFICATION.md` F1 names this as one idea seen from three directions —
 * a source declares what it can do and the surface renders exactly that much,
 * disabled, with the reason. A facet that cannot be used is shown greyed and
 * says why; an app that is not here should be too.
 *
 * So there is one catalogue and it is the whole set. `CATALOGUE` is the
 * build-time half — what exists and how it is reached — and `useApps()` is the
 * workspace's half, which turns each entry into one of four states:
 *
 *     here   this workspace has it and you may open it
 *     off    built, and not switched on here — no address, no assistant
 *     add    a space this workspace could have, and you may add one
 *     soon   drawn, not built
 *
 * `surfaces` is the live subset the rail, the foot and the phone's sheet draw,
 * which is what `nav.js` exported before this module existed and still
 * re-exports so nothing had to move at once.
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  ASSISTANT,
  assistant,
  assistantName,
  assistantShowing,
  openAssistant,
  pressAssistant,
} from '@/modules/onespace/lib/shell/assistant'
import { press, shown } from '@/modules/onespace/lib/desk/windows'
import { APPS as DRIVE_APPS } from '@/modules/onestorage/lib/window'
import { openContext } from '@/modules/onespace/lib/shell/context'
import { openSettings } from '@/modules/onespace/lib/shell/settings'
import { mail } from '@/modules/onespace/lib/shell/mail'
import { session } from '@/modules/onespace/lib/shell/session'
import { MARKS } from '@/shared/lib/brand/marks'
import { nameOf, theirs } from '@/shared/lib/brand/naming'
import { __ } from '@/shared/lib/runtime/translate'

/** How an app is reached. */
export const SURFACE = 'surface'
export const SPACE = 'space'
export const SOON = 'soon'

/** What a workspace has of one. */
export const HERE = 'here'
export const OFF = 'off'
export const ADD = 'add'

/**
 * The whole set, in the design's own order.
 *
 * `brand` is the key: it is the mark, it is the name — `SpaceName` writes
 * `MARKS[brand].name` — and it is what a space manifest declares, which is how
 * a `SPACE` entry knows whether this workspace has it without a second list of
 * space codes to keep in step.
 *
 * `key`, `label` and `icon` are the phone's, not the board's: a sheet row draws
 * a lucide glyph and the word "Files", where the board and the dock draw the
 * mark and the word OneCloud. The key is the *destination's* name and not the
 * mark's — `data-app="files"`, where `data-app="onestorage"` would be naming
 * the drawing rather than the place. `quick` is which of them the dock and the
 * phone's More sheet carry — four, because the three editors are not places you
 * go, they are what opens when you press a file.
 *
 * Two of the twenty-seven are deliberately absent. **One** is the shell you are
 * standing in rather than somewhere to go, and **OneAdmin** is ours: the
 * operator console is a different product on a different host, and the one row
 * that leaves this workspace is already in the switcher's foot.
 */
export const CATALOGUE = [
  {
    brand: 'onemail',
    key: 'mail',
    kind: SURFACE,
    quick: true,
    label: __('Mail'),
    icon: 'lucide-mail',
    to: { name: 'Mail' },
    // Absent for somebody who holds no address, which is most people until
    // somebody sets one up.
    live: () => mail.held,
    why: __('No address here yet'),
  },
  {
    brand: 'onecalendar',
    key: 'calendar',
    kind: SURFACE,
    quick: true,
    label: __('Calendar'),
    icon: 'lucide-calendar',
    to: { name: 'Calendar' },
    live: () => true,
  },
  {
    brand: 'onestorage',
    key: 'files',
    kind: SURFACE,
    quick: true,
    label: __('Files'),
    icon: 'lucide-folder',
    to: { name: 'Drive' },
    live: () => true,
  },
  {
    brand: 'oneai',
    key: 'chat',
    kind: SURFACE,
    quick: true,
    icon: 'lucide-sparkles',
    to: { name: 'Chat' },
    // The workspace names its own assistant, so the surfaces that write an
    // app's product name write this one's label instead. See `SpaceName`.
    renamed: true,
    // AI can be switched off, unconfigured, or suspended by an operator.
    live: () => assistant.available,
    why: __('Not switched on here'),
  },
  // The three editors. Each is reached through the place in the Drive that
  // holds what it makes — `onestorage/components/places.js` — rather than
  // through a route of its own, because there is no such route: a document is
  // a `File`, so the way in is a list of files of that kind. Three tiles
  // pointing at one page would be wrong; three tiles pointing at three
  // different queries is what the rail there already does.
  // Two of the three are in the dock. They are applets — a window you keep
  // open beside the thing you are writing about — which is the whole of what
  // `quick` means here, and writing and reckoning are what most people in a
  // workspace do most days.
  //
  // OneCode is not, and the line is honest rather than tidy: a dock is what
  // you reach for without thinking, and a code editor is somewhere you go on
  // purpose. It keeps its window and its tile on the board, and anybody who
  // lives in it is one press further away than they would like — which is a
  // better complaint to have than seven tiles nobody can tell apart.
  {
    brand: 'onedoc',
    kind: SURFACE,
    quick: true,
    to: { name: 'Drive', query: { place: 'documents' } },
    live: () => true,
  },
  {
    brand: 'onesheet',
    kind: SURFACE,
    quick: true,
    to: { name: 'Drive', query: { place: 'workbooks' } },
    live: () => true,
  },
  {
    brand: 'onecode',
    kind: SURFACE,
    to: { name: 'Drive', query: { place: 'code' } },
    live: () => true,
  },
  {
    brand: 'onemarket',
    key: 'marketplace',
    kind: SURFACE,
    label: __('Add a space'),
    icon: 'lucide-store',
    to: { name: 'Marketplace' },
    // `require_workspace_admin` on the control plane admits the owner and an
    // Admin member, and a tile leading to a page of refusals is worse than a
    // tile that says who it is for.
    live: () => session.isAdmin,
    why: __('Only an admin can add a space'),
  },

  // The spaces. Live when *any* space in this workspace wears the mark, which
  // is a rule rather than a list: a manifest declaring `brand` is the one
  // place that has to say so, and a space somebody writes themselves lights
  // its own tile the moment it names one.
  { brand: 'oneproject', kind: SPACE },
  { brand: 'onecrm', kind: SPACE },
  { brand: 'onehr', kind: SPACE },
  { brand: 'onebook', kind: SPACE },
  { brand: 'oneinventory', kind: SPACE },
  { brand: 'onemobility', kind: SPACE },

  // Drawn and not built. Listed for the reason the whole file exists: the
  // question "is there a OneTask" has an answer, and silence is not it.
  { brand: 'onetask', kind: SOON },
  { brand: 'onescratchpad', kind: SOON },
  { brand: 'oneforms', kind: SOON },
  { brand: 'oneslide', kind: SOON },
  { brand: 'oneticket', kind: SOON },
  { brand: 'onesignature', kind: SOON },
  { brand: 'onedb', kind: SOON },
  { brand: 'onedisplay', kind: SOON },
  { brand: 'onegovernance', kind: SOON },
  { brand: 'onefit', kind: SOON },
  { brand: 'onestudy', kind: SOON },
]

/**
 * The window a mark opens, where it opens one.
 *
 * OneCloud and the three editors are one component over four `where`s —
 * `onestorage/lib/window.js` — and every one of them is a press rather than a
 * link, because what they open is a window and a window has no address.
 */
const windowFor = (brand) => DRIVE_APPS.find((one) => one.brand === brand)?.id || ''

/** What is said under a tile nobody can press. One sentence each. */
const REASON = {
  [ADD]: __('Not in this workspace'),
  [SOON]: __('Not built yet'),
}

/**
 * The catalogue against this workspace.
 *
 * `board` is all of it, each entry with a state and, where it is not `here`,
 * the reason. `surfaces` is the live subset that is not inside a space, which
 * is the list the rail, the foot and the phone's More sheet draw.
 */
export function useApps() {
  const route = useRoute()

  /** Which marks the workspace's spaces wear. */
  const held = computed(
    () => new Set(session.spaces.map((one) => one.brand).filter(Boolean)),
  )

  const board = computed(() =>
    CATALOGUE.map((app) => {
      const state = stateOf(app, held.value)
      const space =
        app.kind === SPACE
          ? session.spaces.find((one) => one.brand === app.brand) || null
          : null
      return {
        ...app,
        // A surface's own key where it has one, the mark where it does not.
        // Unique either way: no space or unbuilt app carries a surface's key.
        key: app.key || app.brand,
        // The workspace names its own assistant, and that name is the only one
        // on the board that is not ours to write — so it is read here rather
        // than declared, and the tile says what the rail says.
        // The mark's own name where the catalogue does not write one, which is
        // most of them: `MARKS[brand].name` is the only place a product name
        // is written down — see `CLAUDE.md` and `scripts/gen_brand.py`, and
        // the reason is that four of the ids disagree with their names on
        // purpose. `SpaceName` draws it; this is the string, for the places
        // that need one: a tile's accessible name, its tooltip, the label a
        // window opens under.
        //
        // It was empty for the three editors, which was invisible until they
        // went in the dock and arrived as tiles a screen reader calls nothing.
        label: space
          ? space.space_label
          : app.brand === 'oneai'
            ? assistantName.value
            : app.label || nameOf(app.brand),
        // Said whole where the name is somebody else's choice — a space a
        // customer renamed, an assistant a workspace named. `theirs` asks the
        // name rather than the kind of thing, which is what the corner used to
        // get wrong about a space still called what its mark is called.
        renamed: space ? theirs(space.brand, space.space_label) : !!app.renamed,
        state,
        // What it is for, in the designer's four words — the tooltip under a
        // tile that works, where the reason is the tooltip under one that does
        // not.
        said: MARKS[app.brand]?.said || '',
        why: state === HERE ? '' : app.why || REASON[state] || '',
        // Null is the whole of "you cannot press this": the tile is a link
        // where there is somewhere to go and a plain element where there is
        // not, so a disabled tile is not a link that refuses.
        to: space
          ? { name: 'Screen', params: { spaceCode: space.space_code } }
          : state === HERE
            ? app.to
            : state === ADD && session.isAdmin
              ? { name: 'Marketplace' }
              : null,
        // And the ones that open a window rather than going anywhere:
        // OneCloud and the three editors, which are one component over four
        // `where`s — `onestorage/lib/window.js`. Declared here rather than
        // only on the row of shortcuts, because the switcher's board draws
        // from *this* list and drew them as links: one tile with two
        // behaviours depending which copy of it you pressed.
        ...(state === HERE && windowFor(app.brand)
          ? {
            act: () => press(windowFor(app.brand), {
              label: app.label || '', icon: app.icon || '', brand: app.brand,
            }),
          }
          : {}),
      }
    }),
  )

  const surfaces = computed(() => [
    ...board.value
      .filter((one) => one.quick && one.state === HERE)
      .map((one) => ({
        key: one.key,
        label: one.label,
        icon: one.icon || '',
        brand: one.brand,
        renamed: one.renamed,
        to: one.to,
        // Which of them you are standing in. Every other navigation in this
        // product marks that — the rail's open item, a list's open row — and
        // this row did not, so four identical glyphs said nothing about where
        // you were. The assistant is marked when its widget is *showing*,
        // because that is what "you are in it" means for a surface that
        // floats over the page rather than replacing it.
        active:
          one.brand === 'oneai'
            ? assistantShowing.value
            : windowFor(one.brand)
              ? shown(windowFor(one.brand))
                || (one.brand === 'onestorage' && route.name === 'Drive')
              : !!one.to?.name && route.name === one.to.name,
        // `act` and not `to`: the assistant opens a panel over the page rather
        // than navigating to one. Going somewhere to ask about the thing you
        // were looking at is the shape this exists to avoid.
        //
        // OneCloud is the second, for the same reason turned around: a file
        // manager is what you keep open *beside* what you are doing, and going
        // somewhere to look at one drawing took the project it belonged to
        // away. `docs/DESKTOP.md` stage 6 — its route stays as the maximised
        // case, so a deep link still works.
        ...(one.brand === 'oneai'
          ? { act: () => openAssistant() }
          : {}),
        // And the three editors with it. A document is a `File`, so OneWriter
        // is this same window landed on `place=documents` — one component,
        // four doors, `onestorage/lib/window.js`.
        ...(windowFor(one.brand)
          ? {
            act: () => press(windowFor(one.brand), {
              label: one.label, icon: one.icon, brand: one.brand,
            }),
          }
          : {}),
        // The badge in the rail and the number in the sheet's label — one
        // figure, said twice.
        ...(one.brand === 'onemail' ? { count: mail.unread } : {}),
      })),
    // Settings, for everybody rather than for admins, and not an app: it opens
    // a dialog over whatever you were looking at. `onespace/tabs.py` decides
    // what is behind it, and a member finds their own four tabs there.
    {
      key: 'settings',
      label: __('Settings'),
      icon: 'lucide-settings',
      act: () => openSettings(),
    },
  ])

  /**
   * What the dock draws: the same four, and the ones this workspace has not
   * got rather than a gap where they would be.
   *
   * `surfaces` is the live subset and is the right list for a *row of
   * shortcuts*, which is what the sidebar's foot was. A dock is not that: it
   * is the place where the apps are, so an app that is missing has to be
   * visibly missing and say why — the same rule the board follows, and the
   * reason `apps.js` exists at all. Somebody whose workspace has no mail
   * address should see OneMail dim and told, not an absence they cannot ask a
   * question about.
   *
   * The spaces are not here. They are in the switcher, which is where you
   * change *where you are*; the dock is what you open *while* you are there.
   */
  const dock = computed(() =>
    board.value
      .filter((one) => one.quick)
      .map((one) => ({
        ...one,
        // The tiles that press rather than navigate, because what they open
        // is a window. `window` is what stops the dock drawing a second,
        // nameless tile for the same thing — see `loose` in `Dock.vue`.
        ...(one.brand === 'oneai' && one.state === HERE
          ? { window: ASSISTANT, act: () => pressAssistant() }
          : {}),
        // OneCloud, since `docs/DESKTOP.md` stage 6. A file manager is what
        // you keep open beside what you are doing, and going somewhere to look
        // at one drawing took the project it belonged to away. Its route stays
        // as the maximised case, so a deep link still works.
        ...(windowFor(one.brand) && one.state === HERE
          ? {
            window: windowFor(one.brand),
            act: () => press(windowFor(one.brand), {
              label: one.label, icon: one.icon, brand: one.brand,
            }),
          }
          : {}),
        active:
          one.brand === 'oneai'
            ? assistantShowing.value
            : windowFor(one.brand)
              // The route counts as open for OneCloud only: `/files` is its
              // maximised case, and the editors have no route of their own —
              // theirs is this same page under a different `place`.
              ? shown(windowFor(one.brand))
                || (one.brand === 'onestorage' && route.name === 'Drive')
              : !!one.to?.name && route.name === one.to.name,
        count: one.brand === 'onemail' ? mail.unread : 0,
      })),
  )

  /**
   * The board, in the three groups it is looked at in.
   *
   * **Spaces** comes from the session rather than from the catalogue, because
   * a workspace's spaces include ones we did not write: a customer's own space
   * wears no mark from this list and still belongs first. The catalogue's
   * `SPACE` entries that this workspace holds are therefore *not* repeated
   * here — they are already in that first group, under the name the workspace
   * gave them.
   *
   * **Apps** is what is live and is not inside a space. **Not here yet** is
   * everything else, which is most of the set and is the point: the question
   * "is there a OneTask" now has an answer on the page.
   */
  const groups = computed(() => {
    const rest = board.value.filter((one) => one.state !== HERE)
    return [
      {
        key: 'spaces',
        label: __('Spaces'),
        items: session.spaces.map((space) => ({
          key: space.space_code,
          space,
          label: space.space_label,
          brand: space.brand || '',
          renamed: theirs(space.brand, space.space_label),
          said: space.description || '',
          state: HERE,
          to: { name: 'Screen', params: { spaceCode: space.space_code } },
        })),
      },
      {
        key: 'apps',
        label: __('Apps'),
        items: board.value.filter(
          (one) => one.state === HERE && one.kind === SURFACE,
        ),
      },
      {
        key: 'rest',
        label: __('Not here yet'),
        items: rest,
      },
    ].filter((group) => group.items.length)
  })

  return { board, dock, groups, surfaces }
}

/** One app's state. Split out so a test can ask it without a router. */
export function stateOf(app, held) {
  if (app.kind === SOON) return SOON
  if (app.kind === SPACE) return held.has(app.brand) ? HERE : ADD
  return app.live?.() ? HERE : OFF
}
