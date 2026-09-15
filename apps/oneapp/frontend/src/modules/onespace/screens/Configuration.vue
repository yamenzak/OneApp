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

    A tab may also be a **settings panel**, which is where the dialog went.
    Twenty-two panels behind a gear, opening over whatever you were looking at,
    offered from a menu — everything wrong with that is what this page already
    got right, so the panels came here rather than a second version of this page
    being built beside them. A panel is drawn by the component that always drew
    it, and gated by the audience it always declared.
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
          <template v-for="one in tabs" :key="one.key">
            <p
              v-if="one.heading"
              data-slot="configuration-heading"
              class="px-2 pb-1 pt-3 text-xs uppercase tracking-wide text-ink-gray-4 first:pt-0"
            >{{ one.heading }}</p>
            <TabTrigger
              :value="one.key"
              :label="one.label"
              :icon-left="iconFor(one)"
            />
          </template>
        </TabList>
      </div>
      <div v-else class="-mx-4 overflow-x-auto overflow-y-hidden px-4">
        <TabList>
          <TabTrigger
            v-for="one in tabs"
            :key="one.key"
            :value="one.key"
            :label="one.label"
            :icon-left="iconFor(one)"
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
        <!--
          `v-if` on the open tab and not only the `TabPanel`'s own `value`.
          A panel fetches when it mounts — the model catalogue, the backup
          list, every doctype's naming series — and One's Configuration has
          nineteen of them. Mounting all nineteen to show one is nineteen
          requests for a page somebody opened to change their password.
        -->
        <TabPanel v-for="one in tabs" :key="one.key" :value="one.key">
          <template v-if="tab === one.key">
          <RelatedRows
            v-if="one.screen && !one.component"
            :space-code="spaceCode"
            :screen="one.screen"
            :label="one.label"
            @open="openRow"
          />
          <!-- A tab whose screen is a *component*. Same sentence as the line
               above — "another screen of this space, drawn the way that screen
               draws" — and the first one where that is not a list: a Single
               has one document, so there is nothing to list. -->
          <component
            :is="screenComponent(one.component)"
            v-else-if="one.component && screenComponent(one.component)"
            :space-code="spaceCode"
            :screen="one.screen"
            :spec="{ screen_label: one.label }"
          />
          <!-- A `fields` panel is a spec the server renders and checks writes
               against; the rest the SPA draws, because they are not lists of
               fields. `settings/panels.js` is the whole of that second
               contract, and `tests/test_settings_tabs.py` holds both ends. -->
          <SettingsFields
            v-else-if="one.kind === FIELDS"
            :group="groupFor(one.panel)"
            @saved="loadGroups"
          />
          <component
            :is="PANELS[one.panel]"
            v-else-if="PANELS[one.panel]"
            :space="SPACE_PANELS.includes(one.panel) ? spaceCode : undefined"
          />
          </template>
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
import SettingsFields from '@/modules/onespace/components/settings/SettingsFields.vue'
import { PANELS, SPACE_PANELS } from '@/modules/onespace/components/settings/panels'
import { screenComponent } from '@/modules/onespace/screens'
// Imported for the literals rather than for the value: Tailwind emits a
// `lucide-*` class only where it can read it as a string, and a tab's icon is
// named in Python. See `settings/icons.js`.
import { TAB_ICONS } from '@/modules/onespace/components/settings/icons'
import { TAB } from '@/modules/onespace/lib/shell/settings'
import { useIsMobile } from '@/modules/onespace/lib/shell/breakpoint'
import { useAddress } from '@/shared/composables/useAddress'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'

//: A settings tab the server renders from a spec, as opposed to one the SPA
//: draws. `onespace/tabs.py` is where the word is decided.
const FIELDS = 'fields'

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
    // One key for both kinds, because a tab strip needs one. A screen tab is
    // keyed by its screen and a panel tab by its panel, and the server never
    // sends both on one tab — see `configuration._panel`.
    return { ...one, heading, key: one.screen || one.panel }
  })
})

/** An icon the build never saw is a blank space, so fall back to one it did. */
const iconFor = (one) =>
  one.screen ? one.icon || 'lucide-table'
    : TAB_ICONS.includes(one.icon) ? one.icon : 'lucide-settings'
const upright = computed(() => !isMobile.value)

const tab = ref('')
watch(tabs, (now) => {
  // The first one, and only where what is open has gone — a space whose tabs
  // reload should not throw the reader back to the top of the list. A tab
  // named in the URL that this reader may not open is one of those: the
  // server did not send it, so it is not here, and they land on the first one
  // they do have rather than on a blank panel.
  if (!now.some((one) => one.key === tab.value)) tab.value = now[0]?.key || ''
}, { immediate: true })

/**
 * Which tab, in the address — `?screen=configuration&tab=backups`.
 *
 * The whole of what the dialog could not do. Twenty-two panels and no way to
 * link to one made every support answer "open settings, then find Backups";
 * §C4 bolted a `?panel=` onto whatever page was underneath, which was the
 * right idea in the wrong place because the page underneath was not settings.
 * Now it is a screen, so this is an ordinary piece of screen state.
 */
useAddress(TAB, {
  read: () => tab.value,
  write: (value) => {
    if (value) tab.value = value
  },
})

/**
 * The `fields` panels' specs, fetched only where this page has one.
 *
 * `workspace.settings()` reads several singles, so a space's Configuration —
 * which is tables and nothing else — must not pay for it. One's does.
 */
const groups = ref([])
const groupFor = (key) => groups.value.find((one) => one.key === key) || null

const loadGroups = async () => {
  groups.value = (await workspace.settings())?.groups || []
}

watch(
  () => tabs.value.some((one) => one.kind === FIELDS),
  (needed) => needed && !groups.value.length && loadGroups(),
  { immediate: true },
)

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
