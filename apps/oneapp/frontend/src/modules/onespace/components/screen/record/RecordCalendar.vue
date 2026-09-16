<template>
  <!--
    One record's own month — `docs/WORK.md` §6(c).

    A project's milestones and the hours booked against it; an employee's
    leave, interviews and training; a client's deliveries. **Declared
    nowhere**: the record already says which screens are about one of these
    and which field points back, so this is the tab strip above it read as a
    calendar. A record that gains a tab gains a calendar with it.

    Its own component rather than the diary with a filter, because the two
    answer different questions: the diary is somebody's week and has a lens
    for whose it is, and this is one record's month and has no lens — the
    narrowing *is* the record.
  -->
  <div class="flex min-h-0 flex-1 flex-col gap-3" data-slot="record-calendar">
    <Alert v-if="error" theme="red" :title="__('This calendar did not load')">
      <template #description>{{ error }}</template>
    </Alert>

    <EmptyState
      v-else-if="asked && !sources.length"
      icon="lucide-calendar"
      :title="__('Nothing here has a date')"
      :description="__('Screens about this record would show their dates here.')"
    />

    <template v-else>
      <!-- What the month is made of, and the colour each source's entries
           carry — the same legend the diary's rail draws, laid along the top
           because a record tab has no rail of its own. -->
      <div v-if="sources.length" class="flex flex-wrap items-center gap-3">
        <span
          v-for="one in sources"
          :key="one.key"
          class="flex items-center gap-1.5 text-p-xs text-ink-secondary"
          data-slot="record-calendar-source"
        >
          <span class="size-2.5 shrink-0 rounded-full" :style="dot(one.key)" />
          {{ one.label }}
        </span>
      </div>

      <Calendar
        :events="events"
        :config="CONFIG"
        :on-click="({ calendarEvent }) => open(calendarEvent)"
        @range-change="moved"
      />
    </template>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Alert, Calendar, CalendarColorMap } from '@/ui'
import EmptyState from '@/shared/components/EmptyState.vue'
import { colourFor, diaryEvents } from '@/modules/onespace/lib/screen/diary'
import { workspace } from '@/shared/lib/workspace'
import { settings } from '@/shared/lib/runtime/format'
import { errorText } from '@/shared/lib/runtime/errors'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  name: { type: String, required: true },
})

const emit = defineEmits(['open'])

// The workspace's own week start and clock, the same two the diary reads.
const CONFIG = computed(() => ({
  defaultMode: 'Month',
  isEditMode: false,
  redundantCellHeight: 100,
  weekStart: settings().week_start || 0,
  timeFormat: settings().time.includes('a') ? '12h' : '24h',
}))

const rows = ref([])
const sources = ref([])
const error = ref('')
const asked = ref(false)

const events = computed(() => diaryEvents(rows.value, sources.value))

/** The grid's own palette, for the reason `DiarySidebar` gives at length. */
const dot = (key) => {
  const found = CalendarColorMap[colourFor(key, sources.value)]
  return { backgroundColor: found?.color || 'var(--outline-gray-3)' }
}

/** Where an entry came from, so a click can go there. */
const source = (id) => rows.value.find((one) => one.id === id) || null

function open(event) {
  const found = source(event?.id)
  // Out to the record it belongs to, on its own screen — the same rule the
  // diary follows, and the reason an entry carries where it came from.
  if (found?.screen) emit('open', { screen: found.screen, name: found.record })
}

async function moved({ startDate, endDate }) {
  if (!startDate || !endDate) return
  error.value = ''
  try {
    const answer = await workspace.recordCalendar(
      props.spaceCode, props.screen, props.name, startDate, endDate,
    )
    rows.value = answer?.events || []
    sources.value = answer?.sources || []
  } catch (raised) {
    rows.value = []
    error.value = errorText(raised)
  } finally {
    asked.value = true
  }
}
</script>
