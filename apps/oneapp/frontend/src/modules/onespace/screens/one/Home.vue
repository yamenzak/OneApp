<template>
  <!--
    The front page of a workspace.

    What was here before was a grid of cards called Spaces: a page you arrived
    at in order to leave. Nothing on it was work. The corner answers "which
    spaces does this workspace have" better than a page can, and nobody arrives
    in the morning wondering it — so this answers the three that people
    actually open a tab to find out.

      what needs me      unread notifications, newest first
      what is next       the reader's own diary, today and tomorrow
      what I had open    the files they last touched

    Three blocks, one call — `oneapp/onespace/home.py`. Three endpoints would be
    three spinners and a page that assembles itself in front of the reader,
    which is the same thing OnePeople's own home says about eight.

    A block with nothing in it is absent rather than empty: a workspace that
    keeps no calendar should not have a Next up card with a dash in it every
    morning for a year.
  -->
  <div class="mx-auto flex w-full max-w-5xl flex-col gap-4 p-4">
    <LoadingText v-if="loading && !loaded" :text="__('Loading')" />

    <template v-else>
      <h1 data-slot="home-greeting" class="text-xl-semibold text-ink-primary">
        {{ greeting }}
      </h1>

      <EmptyState
        v-if="!blocks.length"
        icon="lucide-layout-grid"
        :title="__('Nothing is waiting')"
        :description="__('What needs you, what is next and what you had open turn up here.')"
      />

      <div v-else class="grid gap-4" :class="COLUMNS[blocks.length]">
        <Panel v-for="block in blocks" :key="block.key" :data-slot="`home-${block.key}`">
          <div class="mb-1 flex items-center justify-between gap-2">
            <h2 class="truncate text-base-medium text-ink-primary">{{ block.label }}</h2>
            <Button
              v-if="block.to"
              variant="ghost"
              size="sm"
              :label="__('See all')"
              @click="router.push(block.to)"
            />
          </div>

          <!-- `Row`, like every other list in the product — §B1. A hover fill
               written here would be the eighteenth hand-rolled row. -->
          <Row
            v-for="row in block.rows"
            :key="row.key"
            :to="row.to"
            :href="row.href"
            pad="tight"
            align="start"
          >
            <template #lead>
              <Icon :name="row.icon" class="mt-0.5 size-4 text-ink-muted" />
            </template>
            <span class="block truncate text-sm text-ink-primary">{{ row.said }}</span>
            <span
              v-if="row.under"
              class="mt-0.5 block truncate text-xs text-ink-muted"
            >{{ row.under }}</span>
          </Row>
        </Panel>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Button, Icon, LoadingText } from '@/ui'
import EmptyState from '@/shared/components/EmptyState.vue'
import Panel from '@/shared/components/Panel.vue'
import Row from '@/shared/components/Row.vue'
import { workspace } from '@/shared/lib/workspace'
import { fullName } from '@/modules/onespace/lib/shell/user'
import { date as onDate, time as atTime } from '@/shared/lib/runtime/format'
import { __ } from '@/shared/lib/runtime/translate'

const router = useRouter()

const found = ref({})
const loading = ref(false)
const loaded = ref(false)

/**
 * The hour, in four words.
 *
 * Local to the reader's browser rather than the site's clock, which is the one
 * place in this product where that is the right answer: it is about where the
 * person is sitting, not about when a row was written.
 */
const greeting = computed(() => {
  const name = fullName.value || ''
  const hour = new Date().getHours()
  const said =
    hour < 12 ? __('Good morning') : hour < 18 ? __('Good afternoon') : __('Good evening')
  return name ? `${said}, ${name}` : said
})

/**
 * How many columns, for the blocks there actually are.
 *
 * Written out rather than computed into a class string: Tailwind's JIT reads
 * the source for literal class names, so `grid-cols-${n}` emits no CSS at all.
 * And worth doing rather than fixing the count at three — two cards in a
 * three-column grid is a card-shaped hole, which reads as something that
 * failed to load.
 */
const COLUMNS = {
  1: 'md:grid-cols-1',
  2: 'md:grid-cols-2',
  3: 'md:grid-cols-2 xl:grid-cols-3',
  // Two by two rather than four across: a fourth column makes every card too
  // narrow for the line under a row, which is where each of them says what it
  // is about.
  4: 'md:grid-cols-2',
}

/**
 * When something is, and the two cases that are not a time of day.
 *
 * A screen's calendar can be keyed on a plain `Date` field, and an all-day
 * `Event` is stored at midnight. `moment()` prints the clock either way, so
 * every one of those lines read "00:00:00" — eight characters of noise that
 * look like a bug rather than like a day with no time in it.
 *
 * And to the minute where there is one: seconds under a diary entry are three
 * more characters nobody reads.
 */
const when = (value) => {
  const said = String(value || '')
  const clock = /\d{2}:\d{2}/.test(said) && !said.includes('00:00:00')
  return clock ? `${onDate(said)} ${atTime(said, { toTheMinute: true })}` : onDate(said)
}

/** A notification, as one line and where it goes. */
const fromNotice = (one) => ({
  key: one.name,
  icon: one.read ? 'lucide-circle-dashed' : 'lucide-circle-dot',
  said: one.said,
  under: one.body || '',
  to: one.route || null,
  href: one.route ? '' : one.link || '',
})

/**
 * Something waiting on a yes or a no.
 *
 * It goes to the Approvals screen rather than to the record, and that is
 * deliberate: a card is four lines, the verbs do not fit on one, and a row
 * that opened the record would put somebody one page further from the thing
 * they came to do than the screen this card is advertising.
 */
const fromApproval = (one) => ({
  key: `${one.doctype}/${one.name}`,
  icon: one.icon || 'lucide-inbox',
  said: one.title,
  under: [one.placed ? `${one.label} · ${one.space_label}` : '', one.state]
    .filter(Boolean)
    .join(' · '),
  to: { name: 'Screen', params: { spaceCode: 'one' }, query: { screen: 'waiting' } },
  href: '',
})

/** A diary entry: what it is, and when. */
const fromEvent = (one) => ({
  key: one.id,
  icon: 'lucide-calendar',
  said: one.title,
  under: [when(one.start), one.screen_label].filter(Boolean).join(' · '),
  to: { name: 'Calendar' },
  href: '',
})

/** A file, and the place it opens in. */
const fromFile = (one) => ({
  key: one.name,
  icon: 'lucide-file-text',
  said: one.file_name || one.name,
  under: '',
  to: { name: 'Drive', query: { place: 'recents' } },
  href: '',
})

/**
 * The blocks that have something to say, in the order they are read.
 *
 * Declared as a list rather than three `v-if`s so the grid has no holes in it:
 * a workspace with no diary gets two cards side by side rather than two cards
 * and a gap where the third would have been.
 */
const blocks = computed(() =>
  [
    {
      key: 'attention',
      label: __('What needs you'),
      rows: (found.value.attention || []).map(fromNotice),
      to: null,
    },
    {
      key: 'approvals',
      label: __('Waiting on you'),
      rows: (found.value.approvals || []).map(fromApproval),
      to: { name: 'Screen', params: { spaceCode: 'one' }, query: { screen: 'waiting' } },
    },
    {
      key: 'day',
      label: __('Next up'),
      rows: (found.value.day || []).map(fromEvent),
      to: { name: 'Calendar' },
    },
    {
      key: 'files',
      label: __('Recently opened'),
      rows: (found.value.files || []).map(fromFile),
      to: { name: 'Drive', query: { place: 'recents' } },
    },
  ].filter((block) => block.rows.length),
)

onMounted(async () => {
  loading.value = true
  try {
    found.value = (await workspace.myHome()) || {}
  } finally {
    loaded.value = true
    loading.value = false
  }
})
</script>
