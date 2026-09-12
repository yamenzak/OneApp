<template>
  <!--
    What needs a person, in one place.

    A `component` screen because it is not a list of anything — it is thirteen
    queries over eleven doctypes, and the row that matters most is rarely in
    the table you happened to open. The console had thirty-two screens and no
    way to say that something was wrong; this is that way.

    Empty is the good outcome and it is drawn as one, not as a shrug: nothing
    here means every sweep ran and found nothing.
  -->
  <div class="mx-auto max-w-4xl p-5">
    <div class="mb-5 flex items-start justify-between gap-3">
      <div class="min-w-0">
        <h2 class="text-lg font-semibold text-ink-primary">{{ __('Attention') }}</h2>
        <p class="mt-0.5 text-p-sm text-ink-secondary">
          {{ summary }}
        </p>
      </div>
      <Button
        icon-left="lucide-refresh-cw"
        :label="__('Check again')"
        :loading="board.loading"
        @click="board.reload()"
      />
    </div>

    <div v-if="board.loading && !rows.length" class="flex flex-col gap-2">
      <Skeleton v-for="n in 3" :key="n" class="h-16 w-full" />
    </div>

    <!-- Nothing wrong, said plainly. The alternative — an empty table with
         headers — reads as a screen that failed to load. -->
    <EmptyState
      v-else-if="!rows.length"
      icon="lucide-check"
      :title="__('Nothing needs you')"
      :description="__('Every check ran and found nothing. You will get an email on the days that changes.')"
    />

    <div v-else class="flex flex-col gap-2">
      <!--
        A row is a link where there is somewhere to go. `screen` names an
        operator screen and `record` one row on it, which is the same pair the
        rest of the console navigates by — so a stuck job opens that job
        rather than the list it is in.
      -->
      <Panel
        v-for="row in rows"
        :key="row.key"
        pad="tight"
        :as="row.screen ? 'button' : 'div'"
        :type="row.screen ? 'button' : undefined"
        data-slot="attention-row"
        :data-severity="row.severity"
        class="flex items-start gap-3 text-start"
        :class="row.screen ? rowState() : ''"
        @click="row.screen && go(row)"
      >
        <!-- The severity as a dot rather than a coloured card: thirteen
             coloured cards is a page that shouts, and the ordering already
             puts the worst first. -->
        <span
          class="mt-1.5 size-2 shrink-0 rounded-full"
          :class="DOT[row.severity] || 'bg-surface-gray-5'"
          :aria-label="LABEL[row.severity] || row.severity"
        />
        <div class="min-w-0 flex-1">
          <p class="text-p-base font-medium text-ink-primary">{{ row.title }}</p>
          <p class="mt-0.5 text-p-sm text-ink-secondary">{{ row.detail }}</p>
        </div>
        <Icon
          v-if="row.screen"
          name="lucide-arrow-up-right"
          class="mt-0.5 size-4 shrink-0 text-ink-gray-4"
        />
      </Panel>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Button, Icon, Skeleton } from '@/ui'
import { useResource } from '@/shared/lib/runtime/resource'
import EmptyState from '@/shared/components/EmptyState.vue'
import { __ } from '@/shared/lib/runtime/translate'
import Panel from '@/shared/components/Panel.vue'
import { rowState } from '@/shared/lib/rowstate'

const props = defineProps({
  spaceCode: { type: String, default: "" },
})

const router = useRouter()

// The three severities, as the server names them. A dot each rather than a
// theme on the whole row.
const DOT = {
  blocking: 'bg-surface-red-6',
  warning: 'bg-surface-amber-6',
  notice: 'bg-surface-gray-5',
}
const LABEL = {
  blocking: __('Blocking'),
  warning: __('Warning'),
  notice: __('Notice'),
}

// Fetched rather than pushed. A board that live-updated would be a board that
// moved under a cursor mid-read, and the thing it reports is measured in
// hours: the crons that feed it run every two minutes at the fastest.
const board = useResource('oneapp_control.attention.board', { immediate: true })

const rows = computed(() => board.data?.rows || [])

const summary = computed(() => {
  const counts = board.data?.counts || {}
  if (!rows.value.length) return __('Everything is where it should be.')
  const parts = []
  if (counts.blocking) parts.push(__('{0} blocking', [counts.blocking]))
  if (counts.warning) parts.push(__('{0} to watch', [counts.warning]))
  if (counts.notice) parts.push(__('{0} worth knowing', [counts.notice]))
  return parts.join(' · ')
})

/**
 * Where a row goes. The same `screen` and `record` pair the console's own
 * links use, so a row that names a job opens that job in the record pane
 * rather than dropping you on a list to find it again.
 */
function go(row) {
  const query = { screen: row.screen }
  if (row.record) query.record = row.record
  router.push({ name: 'Screen', params: { spaceCode: props.spaceCode }, query })
}
</script>
