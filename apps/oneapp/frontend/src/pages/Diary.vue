<template>
  <!--
    The diary: every calendar this workspace has, on one grid.

    A screen's calendar reads one doctype. This reads all of them — the week
    somebody actually has is a quotation due on Tuesday, a site visit on
    Wednesday and a review in their own diary, and no single screen holds those
    three. Nothing here is stored: every entry belongs to a record somewhere
    else, says which, and opens it.

    The merge is the server's (`oneapp_core/diary.py`), because it is the same
    permission path each screen uses. Five sources from the browser would be
    five round trips and five chances to disagree about who may see what.
  -->
  <PageHeader>
    <nav data-slot="breadcrumb" aria-label="Breadcrumb" class="flex min-w-0 items-center">
      <Breadcrumbs :items="[{ label: 'Calendar', route: { name: 'Calendar' } }]" />
    </nav>
  </PageHeader>

  <div class="min-h-0 flex-1 overflow-auto p-3" data-slot="diary">
    <Alert v-if="error" theme="red" title="The calendar could not be loaded">
      <template #description>{{ error }}</template>
    </Alert>

    <Calendar
      v-else
      :events="events"
      :config="CONFIG"
      :on-click="({ calendarEvent }) => open(calendarEvent)"
      @range-change="moved"
    />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Alert, Breadcrumbs, Calendar, PageHeader } from '@/ui'
import { workspace } from '../lib/workspace'
import { errorText } from '../lib/errors'
import { diary, diaryEvents, showing } from '../lib/diary'

/**
 * Read-only, and more firmly than the screen calendar is.
 *
 * Every entry here belongs to a different doctype under a different screen's
 * rules. Dragging one would be writing a field on a record this surface knows
 * nothing about — where it is, what else it validates, whether this person may
 * write it at all. The record it opens is where that question already has an
 * answer.
 */
const CONFIG = { isEditMode: false, defaultMode: 'Month' }

const router = useRouter()

const rows = ref([])
const error = ref('')
// Through the rail's switches, and coloured by the same list they are drawn
// from — so a row's dot and its entries on the grid are one fact.
const events = computed(() => diaryEvents(showing(rows.value), diary.sources))

/** Where an entry came from, so a click can go back to it. */
const source = (id) => rows.value.find((one) => one.id === id) || null

function open(event) {
  const found = source(event?.id)
  // A personal event has no screen behind it — there is nowhere to go, and the
  // grid's own popover has already said what it is. Stage two of this is the
  // event surface that makes it a record like any other.
  if (!found?.screen) return
  router.push({
    name: 'Screen',
    params: { spaceCode: found.space },
    query: { screen: found.screen, record: found.record },
  })
}

/**
 * The days now on screen, which is the whole of what this page fetches.
 *
 * `rangeChange` fires on mount as well as on every move, so there is no second
 * load on open — the grid says which month it is showing and that is the
 * request.
 */
async function moved({ startDate, endDate }) {
  if (!startDate || !endDate) return
  error.value = ''
  try {
    const answer = await workspace.agenda(startDate, endDate)
    rows.value = answer?.events || []
    // Every calendar there is, not only the ones with something in them this
    // month: a rail whose rows appear and disappear as you page is a set of
    // switches that moves under the cursor.
    diary.sources = answer?.sources || []
  } catch (raised) {
    // A failed read is not an empty diary, and saying "you have nothing on"
    // when the server refused is the most confidently wrong thing this page
    // could do.
    rows.value = []
    error.value = errorText(raised)
  }
}
</script>
