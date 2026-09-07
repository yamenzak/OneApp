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
        class="w-[380px] rounded-6 border border-outline-gray-2 bg-surface-elevation-2 p-2 shadow-2xl"
      >
        <p class="px-2 pb-2 pt-1 text-p-xs text-ink-gray-5">{{ __('Spaces') }}</p>

        <div class="grid grid-cols-3 gap-1">
          <router-link
            v-for="space in spaces"
            :key="space.space_code"
            :to="{ name: 'Screen', params: { spaceCode: space.space_code } }"
            class="flex flex-col items-center gap-2 rounded-4 px-2 py-3 hover:bg-surface-gray-2"
            :class="space.space_code === active ? 'bg-surface-gray-2' : ''"
            @click="close()"
          >
            <SpaceFace :space="space" size="2xl" />
            <span class="w-full truncate text-center text-p-sm text-ink-gray-7">
              {{ space.space_label }}
            </span>
          </router-link>
        </div>

        <Divider class="my-2" />

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
import { useSidebar } from '@/lib/shell/sidebar'
import { __ } from '@/lib/runtime/translate'

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

const active = computed(() => route.params.spaceCode || '')

function goTo(to, close) {
  close()
  router.push(to)
}

</script>
