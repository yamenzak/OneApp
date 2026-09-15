<template>
  <!--
    A space's front page.

    A space without one lands on whatever its first rail entry happens to be,
    which is a list of somebody's records — usually not the reader's, usually
    sorted by when they were made, and never the thing the person came to do.

    Every block is another *screen* of this space — `onespace/homepage.py` — so
    a block draws that screen's own columns, counts what that screen counts,
    and is checked where every list is checked. Which is also the whole of
    "role-specific": a block whose screen the reader cannot open is not sent,
    and where the difference is whose rows rather than which screens, the
    manifest names a `@me`-narrowed twin. Nothing here knows what a role is.

    Two columns on a desktop and one on a phone, because a block is a short
    list and two short lists side by side is the shape that fits six of them on
    a laptop without scrolling past the last.
  -->
  <div class="flex h-full min-h-0 flex-col overflow-y-auto">
    <div class="mx-auto flex w-full max-w-5xl flex-col gap-4 p-4">
      <div v-if="!blocks.length" class="pt-8">
        <EmptyState
          icon="lucide-layout-grid"
          :title="__('Nothing on this page yet')"
          :description="__('The rail beside it has everything this space can do.')"
        />
      </div>

      <template v-else>
        <h1 data-slot="space-greeting" class="text-xl-semibold text-ink-primary">
          {{ greeting }}
        </h1>

        <div class="grid gap-4 md:grid-cols-2">
          <!--
            `Panel` and `RelatedRows`, which is the same pair the Configuration
            page uses and for the same reason: everything a block wants — the
            screen's columns, its count, its New button, a row that opens — is
            what that component already does, and the only thing it needed was
            a shorter page.
          -->
          <!--
            `min-w-0` on the block and `overflow-x-auto` around its table.

            A grid item's `min-width` defaults to `auto` — it refuses to shrink
            below its content — so a screen with six columns stretched its half
            of the grid and the numbers came out clipped against the panel's
            own edge, with nothing to scroll. The same thing the settings
            panels hit inside a dialog, one layout out.
          -->
          <Panel
            v-for="block in blocks"
            :key="block.screen"
            class="min-w-0"
            :data-slot="`home-block-${block.screen}`"
          >
            <div class="flex items-center gap-2">
              <Icon :name="block.icon || 'lucide-layout-grid'" class="size-4 text-ink-muted" />
              <h2 class="min-w-0 flex-1 truncate text-base-medium text-ink-primary">
                {{ block.label }}
              </h2>
              <Button
                variant="ghost"
                size="sm"
                :label="__('Open')"
                @click="open(block.screen)"
              />
            </div>

            <div class="min-w-0 overflow-x-auto">
              <RelatedRows
                :space-code="spaceCode"
                :screen="block.screen"
                :label="block.label"
                :limit="rows"
                :columns-at-most="COLUMNS"
                @open="openRow"
              />
            </div>
          </Panel>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import { Button, Icon } from '@/ui'
import EmptyState from '@/shared/components/EmptyState.vue'
import Panel from '@/shared/components/Panel.vue'
import RelatedRows from '@/modules/onespace/components/screen/record/RelatedRows.vue'
import { fullName } from '@/modules/onespace/lib/shell/user'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  /** The resolved screen. `home.blocks` is what this draws. */
  spec: { type: Object, default: () => ({}) },
})

//: A name and two facts. Six columns in a quarter of a page is a table you
//: have to scroll sideways to read an amount, which is not what a glance is;
//: the screen itself is one press away and has all of them.
const COLUMNS = 3

const router = useRouter()

const blocks = computed(() => props.spec?.home?.blocks || [])
const rows = computed(() => props.spec?.home?.rows || 5)

/**
 * The hour, in four words.
 *
 * Local to the reader's browser rather than the site's clock, which is the one
 * place in this product where that is the right answer: it is about where the
 * person is sitting, not about when a row was written. Same line One's own
 * home opens with, because it is the same sentence.
 */
const greeting = computed(() => {
  const hour = new Date().getHours()
  const said =
    hour < 12 ? __('Good morning') : hour < 18 ? __('Good afternoon') : __('Good evening')
  return fullName.value ? `${said}, ${fullName.value}` : said
})

/** The screen itself, which is what a block is a glance at. */
const open = (screen) =>
  router.push({
    name: 'Screen',
    params: { spaceCode: props.spaceCode },
    query: { screen },
  })

/**
 * A row opens where that screen's records live.
 *
 * Not in a pane here: a pane belongs to a list, and this page is a grid of
 * them. Same rule the Configuration page follows.
 */
const openRow = ({ screen, name }) =>
  router.push({
    name: 'Screen',
    params: { spaceCode: props.spaceCode },
    query: { screen, at: `record:${name}` },
  })
</script>
