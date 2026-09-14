<template>
  <!--
    The tables a space is maintained by, on one page.

    Every space grows a handful of these — leave types, project types, sales
    stages, salary components — and ERPNext gives each a rail entry, interleaved
    with the transactions, which is how a salesperson's list of destinations
    comes to contain Market Segment. `docs/ERP-SPACES.md` §2 pushed them into a
    Setup group at the bottom instead; this is the next step, and it is the one
    that also houses the doctypes a space granted for its *pickers* and never
    gave a screen to at all.

    Every tab is another screen of this space — `onespace/configuration.py` —
    so a tab's columns, permissions and New button are that screen's own. There
    is no second way to reach a doctype here, which is the whole reason it is
    built out of screens rather than out of queries.
  -->
  <div class="flex h-full min-h-0 flex-col">
    <div v-if="!tabs.length" class="p-4">
      <EmptyState
        icon="lucide-settings"
        :title="__('Nothing to set up')"
        :description="__('This space keeps no tables of its own.')"
      />
    </div>

    <!--
      Upright on a desktop, along the top on a phone — the same rule a record
      follows, and for the same reason: a column does not run out of room and
      twelve tables is more than a row holds.
    -->
    <Tabs
      v-else
      v-model="tab"
      :vertical="upright"
      class="min-h-0 flex-1 overflow-y-auto p-4"
      :class="upright ? 'flex items-start gap-6' : undefined"
    >
      <!--
        Upright, and with headings where the page declares them. A space that
        can write thirty tables — which is what "no desk" costs — has a column
        of thirty entries, and a column of thirty entries with nothing dividing
        it is the rail this page was built to replace. The headings are the
        same ones the rail above uses, one level in.

        Drawn when the group *changes*, which is how the rail decides too, so a
        page that declares none needs no second code path.
      -->
      <div
        v-if="upright"
        data-slot="configuration-rail"
        class="sticky top-0 w-48 shrink-0"
      >
        <TabList class="w-full">
          <template v-for="one in tabs" :key="one.screen">
            <p
              v-if="one.heading"
              data-slot="configuration-heading"
              class="px-2 pb-1 pt-3 text-xs uppercase tracking-wide text-ink-gray-4 first:pt-0"
            >{{ one.heading }}</p>
            <TabTrigger
              :value="one.screen"
              :label="one.label"
              :icon-left="one.icon || 'lucide-table'"
            />
          </template>
        </TabList>
      </div>
      <div v-else class="-mx-4 overflow-x-auto overflow-y-hidden px-4">
        <TabList>
          <TabTrigger
            v-for="one in tabs"
            :key="one.screen"
            :value="one.screen"
            :label="one.label"
            :icon-left="one.icon || 'lucide-table'"
          />
        </TabList>
      </div>

      <div :class="upright ? 'min-w-0 flex-1' : undefined">
        <!--
          `RelatedRows` with nothing to narrow to. It was written for a record's
          tabs — "this project's invoices" — and everything else it does is what
          a table on this page wants: the screen's own columns, its count, its
          New button, and a row that opens.
        -->
        <TabPanel v-for="one in tabs" :key="one.screen" :value="one.screen">
          <RelatedRows
            :space-code="spaceCode"
            :screen="one.screen"
            :label="one.label"
            @open="openRow"
          />
        </TabPanel>
      </div>
    </Tabs>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { Tabs, TabList, TabPanel, TabTrigger } from '@/ui'
import EmptyState from '@/shared/components/EmptyState.vue'
import RelatedRows from '@/modules/onespace/components/screen/record/RelatedRows.vue'
import { useIsMobile } from '@/modules/onespace/lib/shell/breakpoint'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  /** The resolved screen. `configuration.tabs` is what this draws. */
  spec: { type: Object, default: () => ({}) },
})

const router = useRouter()
const isMobile = useIsMobile()

/**
 * The tabs, each told whether it opens a heading.
 *
 * Worked out here rather than in the template so the rule is one line and the
 * markup stays a loop: a tab carries the group it is in, and the *first* tab of
 * each group is the one that draws it. Same rule the space rail follows.
 */
const tabs = computed(() => {
  let last = null
  return (props.spec?.configuration?.tabs || []).map((one) => {
    const group = one.group || ''
    const heading = group && group !== last ? group : ''
    last = group
    return { ...one, heading }
  })
})
const upright = computed(() => !isMobile.value)

const tab = ref('')
watch(tabs, (now) => {
  // The first one, and only where what is open has gone — a space whose tabs
  // reload should not throw the reader back to the top of the list.
  if (!now.some((one) => one.screen === tab.value)) tab.value = now[0]?.screen || ''
}, { immediate: true })

/**
 * A row opens where that screen's records live.
 *
 * Not in a pane here: a pane belongs to a list, and this page is a strip of
 * lists. The screen is `hide_in_nav` rather than absent, so it still has a
 * route — which is the whole reason the manifest hides these rather than
 * dropping them.
 */
const openRow = ({ screen, name }) => {
  router.push({
    name: 'Screen',
    params: { spaceCode: props.spaceCode },
    query: { screen, at: `record:${name}` },
  })
}
</script>
