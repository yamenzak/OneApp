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
        :label="workspace.label"
        class="!h-8 w-full !px-1 [&>span]:min-w-0 [&>span]:flex-1 [&>span]:text-start"
        :class="open ? '!bg-surface-gray-3' : ''"
      >
        <template #prefix>
          <SpaceFace :space="workspace" size="lg" class="size-6 shrink-0" />
        </template>
        <span v-if="!collapsed" class="truncate text-base text-ink-gray-8">
          {{ workspace.label }}
        </span>
        <template v-if="!collapsed" #suffix>
          <Icon name="lucide-chevrons-up-down" class="size-4 shrink-0 text-ink-gray-5" />
        </template>
      </Button>
    </template>

    <template #default="{ close }">
      <div
        class="w-[348px] rounded-6 border border-outline-gray-2 bg-surface-elevation-2 p-3 shadow-2xl"
      >
        <p class="px-1 pb-2 text-p-xs text-ink-gray-5">{{ __('Spaces') }}</p>

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
          the assistant. They are tiles here and outlines in the foot of the
          column, and that is the split on purpose: this is the board you look
          at when you are choosing where to go, which is the one place a mark
          earns its colour. Only the ones that *have* a mark; settings opens a
          dialog rather than going anywhere and is in the account menu.
        -->
        <template v-if="apps.length">
          <Divider class="my-3" />
          <p class="px-1 pb-2 text-p-xs text-ink-gray-5">{{ __('Apps') }}</p>

          <div :class="GRID">
            <router-link
              v-for="app in apps"
              :key="app.key"
              :to="app.to"
              :class="TILE"
              @click="close()"
            >
              <SpaceFace :space="{ label: app.label, brand: app.brand }" size="2xl" :class="FACE" />
              <span :class="CAPTION">{{ app.label }}</span>
            </router-link>
          </div>
        </template>

        <Divider class="my-3" />

        <div class="flex flex-col gap-0.5">
          <Button
            variant="ghost"
            class="!justify-start"
            icon-left="lucide-layout-grid"
            :label="__('All spaces')"
            @click="goTo({ name: 'Launcher' }, close)"
          />
          <!--
            Adding a space is something you do to the *workspace*, so it belongs
            where the workspace's spaces are, not beside the day's work. Absent
            for somebody who may not: `require_workspace_admin` on the control
            plane admits the owner and an Admin member, and a row leading to a
            page of refusals is worse than no row.
          -->
          <Button
            v-if="session.isAdmin"
            variant="ghost"
            class="!justify-start"
            :label="__('Add a space')"
            @click="goTo({ name: 'Marketplace' }, close)"
          >
            <template #prefix>
              <BrandMark name="onemarket" class="size-4" />
            </template>
          </Button>
        </div>
      </div>
    </template>
  </Popover>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button, Divider, Icon, Popover } from '@/ui'
import BrandMark from '../brand/BrandMark.vue'
import SpaceFace from '../brand/SpaceFace.vue'
import { TENANT_APP } from '@/lib/runtime/brand'
import { brand } from '@/lib/runtime/boot'
import { session } from '@/lib/shell/session'
import { useNav } from '@/lib/shell/nav'
import { useSidebar } from '@/lib/shell/sidebar'
import { __ } from '@/lib/runtime/translate'

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
const GRID = 'grid grid-cols-3'
const TILE = 'flex h-[100px] flex-col items-center gap-1.5 rounded-4 px-1 pt-3 hover:bg-surface-gray-2'
const FACE = 'h-12 shrink-0'
const CAPTION = 'line-clamp-2 w-full text-center text-p-xs leading-tight text-ink-gray-7'

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

function goTo(to, close) {
  close()
  router.push(to)
}

</script>
