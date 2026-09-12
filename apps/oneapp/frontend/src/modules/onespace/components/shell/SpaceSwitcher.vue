<template>
  <!--
    The corner: the workspace, and behind it every space in it.

    A grid and not a menu. A menu is a list of words, and a space is a face —
    the same face the launcher and the marketplace draw. Once there are a dozen
    of them a column of labels is something to read; a grid of marks is
    something to recognise, which is the whole reason the marks exist.

    `bare`, so the panel is ours: frappe-ui's own panel is padded for menu rows
    and this is a board of tiles.
  -->
  <Popover :bare="true" align="start" :offset="6">
    <template #trigger="{ open }">
      <!--
        `[&>span]` and not a `flex-1` inside the slot: Button wraps whatever the
        default slot holds in a `truncate` span of its own, so a `flex-1` in
        there had nothing to grow against and the arrows sat on the last letter
        of the name however wide the corner was. The span itself is the thing
        that has to take the slack.
      -->
      <Button
        variant="ghost"
        data-slot="space-switcher"
        :label="here.label"
        class="!h-8 w-full !px-1 [&>span]:min-w-0 [&>span]:flex-1 [&>span]:text-start"
        :class="open ? '!bg-surface-gray-3' : ''"
      >
        <template #prefix>
          <SpaceFace :space="here" size="lg" class="size-6 shrink-0" />
        </template>
        <SpaceName
          v-if="!collapsed"
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
      <Panel ground="raised" pad="tight" elevation="floating" class="w-[392px]">
        <!--
          The way to the full list sits on the group it belongs to rather than
          in a footer under everything. A footer row reads as another
          destination in the same list as Mail and the calendar; beside the
          word "Spaces" it reads as what it is — more of these.
        -->
        <div class="flex items-center justify-between gap-2 px-1 pb-2">
          <!-- Named by the workspace rather than by the word "Spaces": these
               are its spaces, the corner no longer says which workspace you
               are in, and a heading is somewhere to say it that costs no
               row. -->
          <p class="truncate text-xs text-ink-muted">{{ workspace.label }}</p>
          <Button
            variant="ghost"
            size="sm"
            :label="__('View all')"
            @click="goTo({ name: 'Launcher' }, close)"
          />
        </div>

        <div :class="GRID">
          <router-link
            v-for="space in spaces"
            :key="space.space_code"
            :to="{ name: 'Screen', params: { spaceCode: space.space_code } }"
            :class="[TILE, space.space_code === active ? 'bg-surface-gray-2' : '']"
            @click="close()"
          >
            <SpaceFace :space="space" size="2xl" :class="FACE" />
            <span :class="CAPTION">{{ space.space_label }}</span>
          </router-link>
        </div>

        <!--
          The apps that are not inside any space — Mail, Files, the calendar,
          the assistant, and the marketplace. They are tiles here and outlines
          in the foot of the column, and that is the split on purpose: this is
          the board you look at when you are *choosing* where to go, which is
          the one place a mark earns its colour.

          The marketplace is one of them rather than a footer row, because
          adding a space is the same kind of act as opening one and reads
          better as the empty tile at the end of the board than as a line of
          text under it. Absent for somebody who may not add one:
          `require_workspace_admin` admits the owner and an Admin member, and
          `nav.js` leaves the entry out for everyone else.

          Only what has a mark and somewhere to go: settings opens a dialog
          rather than going anywhere and is in the account menu.
        -->
        <template v-if="apps.length">
          <Divider class="my-3" />
          <p class="px-1 pb-2 text-p-xs text-ink-muted">{{ __('Apps') }}</p>

          <div :class="GRID">
            <router-link
              v-for="app in apps"
              :key="app.key"
              :to="app.to"
              :class="TILE"
              @click="close()"
            >
              <SpaceFace :space="{ label: app.label, brand: app.brand }" size="2xl" :class="FACE" />
              <SpaceName
                :brand="app.brand"
                :label="app.label"
                :renamed="app.renamed"
                :class="CAPTION"
              />
            </router-link>
          </div>
        </template>

        <!--
          The one row that leaves. A footer row is the wrong shape for another
          space — that is what the tiles are — but it is exactly the right one
          for a place that is not in this workspace at all, and the arrow says
          so before the words do.

          It has to be a link rather than a screen: a tenant site's HMAC secret
          proves it is *itself*, so it can never show you the other two
          workspaces on the same account. The control plane is the one place
          that knows there are three.

          Absent for a member: the account is a billing surface, and the server
          sends the address only to somebody who administers the workspace.
        -->
        <template v-if="accountUrl">
          <Divider class="my-3" />
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
import { useRoute, useRouter } from 'vue-router'
import { Button, Divider, Icon, Popover } from '@/ui'
import SpaceFace from '@/shared/components/brand/SpaceFace.vue'
import SpaceName from '@/shared/components/brand/SpaceName.vue'
import { TENANT_APP } from '@/shared/lib/runtime/brand'
import { brand } from '@/shared/lib/runtime/boot'
import { session } from '@/modules/onespace/lib/shell/session'
import { useNav } from '@/modules/onespace/lib/shell/nav'
import { useSidebar } from '@/modules/onespace/lib/shell/sidebar'
import { __ } from '@/shared/lib/runtime/translate'
import { HOVER } from '@/shared/lib/rowstate'
import Panel from '@/shared/components/Panel.vue'

/*
 * The launcher's tile, which is one shape used twice.
 *
 * Google's app grid is the reference, and what it gets right is regularity:
 * the mark sits in a box of a fixed height whatever its own proportions are,
 * the caption sits under it at a fixed distance, and a two-word name wraps
 * instead of truncating — so no tile is a different height from its
 * neighbours and the grid reads as a grid rather than as a paragraph of
 * icons.
 *
 * Hence a height on the face rather than letting each mark set its own, and a
 * two-line clamp rather than `truncate`: "Compliance" is a word and "Cloud
 * Search" is two, and cutting the second is worse than wrapping it.
 *
 * The face is 48 and not 40 because a mark's ink fills about two thirds of its
 * own 100-unit box — the shapes start at 18 and end at 82 — so a 40px face
 * draws a 26px object, which is smaller than the launcher it is copying. The
 * panel
 * is 348 rather than a round number so three tiles and the padding divide it
 * exactly — a launcher whose columns do not fit its width has a ragged edge.
 */
const GRID = 'grid grid-cols-4'
// A tile is not a row, and it still lights up the same way one does: the
// hover fill is the product's, from `lib/rowstate.js`, and not a second
// opinion about how hard a hovered thing should glow.
const TILE = `flex h-[100px] flex-col items-center gap-1.5 rounded-4 px-0.5 pt-3 ${HOVER}`
const FACE = 'h-12 shrink-0'
const CAPTION = 'line-clamp-2 w-full text-center text-p-xs leading-tight text-ink-secondary'

const route = useRoute()
const router = useRouter()
const { collapsed } = useSidebar()

// The workspace's own face, drawn from what it chose for its tab. One that
// chose nothing gets its initial, which is what SpaceFace does with a space
// that named no mark.
const workspace = computed(() => ({
  label: session.tenant?.name || TENANT_APP,
  logo: brand.favicon || null,
}))

const spaces = computed(() => session.spaces)

// From the one declaration the foot of the column reads, filtered to what has
// a mark and a place to go: settings opens a dialog, and a tile that is not a
// destination is a tile that lies about being one.
const { surfaces } = useNav()

const apps = computed(() => surfaces.value.filter((one) => one.brand && one.to))

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
 * somewhere better to be: over its own spaces, one row down.
 *
 * A route this does not recognise — the launcher, the marketplace, your
 * account — falls back to the workspace, which is true of all three: none of
 * them is inside anything.
 */
const here = computed(() => {
  const code = route.params.spaceCode
  if (code) {
    const found = spaces.value.find((one) => one.space_code === code)
    if (found) {
      return { label: found.space_label, logo: found.logo, brand: found.brand, renamed: true }
    }
  }
  const app = apps.value.find((one) => one.to?.name === route.name)
  if (app) return { label: app.label, brand: app.brand, renamed: !!app.renamed }
  return { ...workspace.value, renamed: true }
})

function goTo(to, close) {
  close()
  router.push(to)
}

</script>
