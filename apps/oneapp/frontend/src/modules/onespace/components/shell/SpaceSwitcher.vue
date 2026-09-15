<template>
  <!--
    The corner: where you are, and behind it everything there is.

    A board and not a menu. A menu is a list of words, and an app is a face —
    the same face the marketplace and every "Open in" draw. Once there are
    twenty-seven of them a column of labels is something to read; a board of
    marks is something to recognise, which is the whole reason the marks exist.

    What changed is what is *on* the board. It used to be this workspace's
    spaces and the four apps that happened to be switched on, so the answer to
    "is there a OneTask" was silence — indistinguishable from "yes, and you
    cannot see it". Now the set is the whole catalogue, the ones this workspace
    does not have are drawn dim and say why, and `lib/shell/apps.js` is the one
    place that decides which is which. §F1: a source declares what it can do and
    the surface renders exactly that much.

    `bare`, so the panel is ours: frappe-ui's own is padded for menu rows.
  -->
  <Popover :bare="true" align="start" :offset="6">
    <template #trigger="{ open }">
      <!--
        Two shapes, because the column has two widths and a folded corner is
        not a narrow wide one. Open, it is a mark, a name and the chevrons —
        `[&>span]` and not a `flex-1` inside the slot, because Button wraps the
        default slot in a `truncate` span of its own and a `flex-1` in there
        has nothing to grow against. Folded, it is the mark alone in a square:
        no chevrons at 3rem — they would take a third of the width to say
        something the press already says — and the ring rather than a fill
        marks it open, so the mark keeps its own colours against the rail.
      -->
      <Button
        variant="ghost"
        data-slot="space-switcher"
        :label="here.label"
        :class="[
          collapsed
            ? '!size-8 !p-0 justify-center'
            : '!h-8 w-full !px-1 [&>span]:min-w-0 [&>span]:flex-1 [&>span]:text-start',
          open ? (collapsed ? 'ring-2 ring-outline-gray-3' : '!bg-surface-gray-3') : '',
        ]"
      >
        <template v-if="!collapsed" #prefix>
          <SpaceFace :space="here" size="lg" class="size-6 shrink-0" />
        </template>
        <SpaceFace v-if="collapsed" :space="here" size="lg" class="size-6 shrink-0" />
        <SpaceName
          v-else
          :brand="here.brand"
          :label="here.label"
          :renamed="here.renamed"
          class="truncate text-base"
        />
        <template v-if="!collapsed" #suffix>
          <Icon name="lucide-chevrons-up-down" class="size-4 shrink-0 text-ink-muted" />
        </template>
      </Button>
    </template>

    <template #default="{ close }">
      <Panel ground="raised" pad="tight" elevation="floating" class="w-[460px]">
        <!--
          The workspace, said once, at the top of its own board. The corner
          below no longer says which workspace you are in — it says which app —
          so this is the only place it is written, and it costs no row.
        -->
        <div class="flex items-center gap-2 px-1 pb-2">
          <SpaceFace :space="workspace" size="sm" class="shrink-0" />
          <p class="min-w-0 flex-1 truncate text-sm text-ink-secondary">
            {{ workspace.label }}
          </p>
        </div>

        <!--
          Scrolls, and has to: twenty-seven tiles is six rows, and a popover as
          tall as the window is a popover whose bottom row is off the screen on
          a laptop. `max-h-overlay` is the product's one answer to how tall a
          floating thing may be, and it is the viewport's rather than a number
          of rows — so a workspace with two spaces gets a short panel and one
          with twelve gets a scroller.

          `FadedScroll` and not a plain `ScrollArea`, because a row of tiles cut
          in half by a hard edge reads as a rendering fault rather than as
          "there is more below" — which is exactly what the first build of this
          did with the second row of Apps.
        -->
        <FadedScroll data-slot="app-board" class="max-h-overlay px-0.5">
          <template v-for="group in groups" :key="group.key">
            <p :class="HEADING">{{ group.label }}</p>
            <div :class="GRID">
              <!--
                Three shapes, the same three the dock draws — `DockTile.vue`
                has the argument. A window presses, because a window has no
                address to link to; a page is a link, so middle-click opens a
                tab; an app this workspace has not got is neither, and says
                why.

                The board drew only the first two, so OneCloud and the three
                editors navigated from here and opened a window from the dock:
                one tile, two behaviours, depending which copy of it you
                pressed.
              -->
              <component
                :is="app.act ? 'button' : app.to ? 'router-link' : 'div'"
                v-for="app in group.items"
                :key="app.key"
                :to="app.to"
                :type="app.act ? 'button' : undefined"
                :title="app.why || app.said || ''"
                :data-slot="app.to || app.act ? 'app-tile' : 'app-tile-off'"
                :data-app="app.key || app.brand"
                :aria-disabled="app.to || app.act ? undefined : 'true'"
                :class="[
                  TILE,
                  app.to || app.act ? HOVER : 'cursor-default',
                  app.space && app.space.space_code === active ? 'bg-surface-gray-2' : '',
                ]"
                @click="(app.to || app.act) && (app.act?.(), close())"
              >
                <!--
                  Dimmed rather than greyed. A mark stripped of its colour is a
                  different drawing — the whole set is built out of hue — and a
                  row of grey squircles reads as broken rather than as absent.
                  At 40% the shape is still the app's and the tile is plainly
                  not one you can press.
                -->
                <SpaceFace
                  :space="app.space || { label: app.label, brand: app.brand }"
                  size="2xl"
                  decorative
                  :class="[FACE, app.to || app.act ? '' : 'opacity-40']"
                />
                <SpaceName
                  :brand="app.brand"
                  :label="app.label"
                  :renamed="app.renamed"
                  :class="[CAPTION, app.to || app.act ? '' : 'opacity-60']"
                />
              </component>
            </div>
          </template>
        </FadedScroll>

        <!--
          The one row that leaves. A tile is the wrong shape for a place that is
          not in this workspace at all, and the arrow says so before the words
          do.

          It has to be a link rather than a screen: a tenant site's HMAC secret
          proves it is *itself*, so it can never show you the other two
          workspaces on the same account. The control plane is the one place
          that knows there are three.

          Absent for a member: the account is a billing surface, and the server
          sends the address only to somebody who administers the workspace.
        -->
        <template v-if="accountUrl">
          <Divider class="my-2" />
          <a
            :href="accountUrl"
            target="_blank"
            rel="noopener"
            data-slot="my-workspaces"
            :class="['flex items-center gap-2 rounded-4 px-2 py-1.5', HOVER]"
            @click="close()"
          >
            <Icon name="lucide-building-2" class="size-4 shrink-0 text-ink-secondary" />
            <span class="flex-1 truncate text-sm text-ink-primary">
              {{ __('My workspaces') }}
            </span>
            <Icon name="lucide-arrow-up-right" class="size-4 shrink-0 text-ink-muted" />
          </a>
        </template>
      </Panel>
    </template>
  </Popover>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Button, Divider, Icon, Popover } from '@/ui'
import SpaceFace from '@/shared/components/brand/SpaceFace.vue'
import SpaceName from '@/shared/components/brand/SpaceName.vue'
import { TENANT_APP } from '@/shared/lib/runtime/brand'
import { brand } from '@/shared/lib/runtime/boot'
import { session } from '@/modules/onespace/lib/shell/session'
import { useApps } from '@/modules/onespace/lib/shell/apps'
import { useSidebar } from '@/modules/onespace/lib/shell/sidebar'
import { __ } from '@/shared/lib/runtime/translate'
import { HOVER } from '@/shared/lib/rowstate'
import { theirs } from '@/shared/lib/brand/naming'
import Panel from '@/shared/components/Panel.vue'
import FadedScroll from '@/shared/components/FadedScroll.vue'

/*
 * The tile, which is one shape used for everything on the board.
 *
 * Google's app grid is the reference, and what it gets right is regularity:
 * the mark sits in a box of a fixed height whatever its own proportions are,
 * the caption sits under it at a fixed distance, and a two-word name wraps
 * instead of truncating — so no tile is a different height from its neighbours
 * and the board reads as a board rather than as a paragraph of icons.
 *
 * Five columns and not four. The set is twenty-seven now; at four it is seven
 * rows and the scroll starts inside the first group. The face stays at 48,
 * because a mark's ink fills about two thirds of its own box — a 40px face
 * draws a 26px object, which is smaller than the launcher it is copying.
 */
const GRID = 'grid grid-cols-5'
// A tile is not a row, and it still lights up the same way one does: the hover
// fill is the product's, from `lib/rowstate.js`, and not a second opinion about
// how hard a hovered thing should glow.
const TILE = 'flex h-[100px] flex-col items-center gap-1.5 rounded-4 px-0.5 pt-3'
const FACE = 'h-12 shrink-0'
// `break-words` as well as the clamp: half these names are a single word —
// OneScratchpad, OneSignature, OneGovernance — and a clamp cannot wrap what has
// no space in it, so they ran out of their tile and into the next one.
const CAPTION =
  'line-clamp-2 w-full break-words text-center text-p-xs leading-tight text-ink-secondary'
const HEADING = 'px-1.5 pb-1.5 pt-2 text-p-xs text-ink-muted'

const route = useRoute()
const { collapsed } = useSidebar()
const { groups } = useApps()

// The workspace's own face, drawn from what it chose for its tab. One that
// chose nothing gets its initial, which is what SpaceFace does with a space
// that named no mark.
const workspace = computed(() => ({
  label: session.tenant?.name || TENANT_APP,
  logo: brand.favicon || null,
}))

const spaces = computed(() => session.spaces)

const active = computed(() => route.params.spaceCode || '')

// Empty for a member, and empty on a development bench with no control plane.
// Either way the row is not drawn — see `workspace.account_url`.
const accountUrl = computed(() => session.tenant?.account_url || '')

/**
 * Where you are, which is what the trigger of a switcher shows.
 *
 * It used to show the workspace, always — the reasoning being that the corner
 * names the workspace and the trail beside it names the page. That held while
 * the only things in here were spaces. Now that Mail, Files and the calendar
 * are in it too, a control listing five places and never saying which of them
 * you are in is a picker with no value in it, and the workspace's name has
 * somewhere better to be: over its own board, one row down.
 *
 * A route this does not recognise — the marketplace, your account — falls back
 * to the workspace, which is true of both: neither is inside anything.
 */
const here = computed(() => {
  const code = route.params.spaceCode
  if (code) {
    const found = spaces.value.find((one) => one.space_code === code)
    if (found) {
      // `theirs` and not `true`. A space *is* somebody's, which is what this
      // used to say — but OnePeople is a space and its name is still ours, so
      // the corner wrote it flat while the board one row down wrote it the
      // family way. The question is the name, not the kind of thing.
      return {
        label: found.space_label,
        logo: found.logo,
        brand: found.brand,
        renamed: theirs(found.brand, found.space_label),
      }
    }
  }
  const app = groups.value
    .flatMap((group) => group.items)
    .find((one) => one.to?.name && one.to.name === route.name && !one.space)
  if (app) return { label: app.label, brand: app.brand, renamed: !!app.renamed }
  return { ...workspace.value, renamed: true }
})
</script>
