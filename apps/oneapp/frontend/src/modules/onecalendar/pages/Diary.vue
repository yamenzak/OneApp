<template>
  <!--
    The diary: every calendar this workspace has, on one grid.

    A screen's calendar reads one doctype. This reads all of them — the week
    somebody actually has is a quotation due on Tuesday, a site visit on
    Wednesday and a review in their own diary. Nothing here is stored: every
    entry belongs to a record somewhere else, says which, and opens it.

    The merge is the server's (`onecalendar/diary.py`), because it is the same
    permission path each screen uses.
  -->
  <!--
    The bar, which is the shell's on the page and the window's own inside one.

    Teleported rather than drawn again: a window already has a bar with a name
    in it, and a second row under it holding one button is the band OneCloud
    spent a stage removing. `WINDOW_BAR` in `lib/desk/windows.js`.
  -->
  <Teleport v-if="inWindow" :to="`#${inWindow}`">
    <!-- Whose days these are. Icons in a window's bar, where there is room for
         two glyphs and not for two words. -->
    <Button
      v-for="one in LENSES"
      :key="one.lens"
      variant="ghost"
      :icon="one.icon"
      :label="one.label"
      :tooltip="one.label"
      :class="diary.lens === one.lens ? '!bg-surface-gray-3' : ''"
      :data-slot="`diary-lens-${one.lens}`"
      @click="lookAt(one.lens)"
    />
    <Button
      variant="ghost"
      icon="lucide-plus"
      :label="__('New event')"
      :tooltip="__('New event')"
      data-slot="diary-new"
      @click="start()"
    />
  </Teleport>

  <PageHeader v-else>
    <Trail :items="crumbs" />

    <!--
      Whose days these are — `docs/WORK.md` §6. Two buttons and not a
      dropdown: there are two answers, they are the two questions anybody opens
      a calendar with, and a menu would hide one of them behind the other.
    -->
    <div class="flex items-center gap-0.5">
      <!-- The chosen one is held down. `!` because a Button draws its own
           background for its variant and this has to beat it — the same way
           the space switcher marks itself open. -->
      <Button
        v-for="one in LENSES"
        :key="one.lens"
        variant="ghost"
        :icon-left="one.icon"
        :label="one.label"
        :class="diary.lens === one.lens ? '!bg-surface-gray-3' : ''"
        :data-slot="`diary-lens-${one.lens}`"
        @click="lookAt(one.lens)"
      />
    </div>

    <!-- The one thing this surface writes. Everything else on the grid is a
         record under a screen's rules, and New there means New *there*. -->
    <Button
      variant="solid"
      icon-left="lucide-plus"
      :label="__('New event')"
      data-slot="diary-new"
      @click="start()"
    />
  </PageHeader>

  <div class="min-h-0 flex-1 overflow-auto p-3" data-slot="diary">
    <Alert v-if="error" theme="red" :title="__('Your calendar did not load')">
      <template #description>{{ error }}</template>
    </Alert>

    <Calendar
      v-else
      :events="events"
      :config="CONFIG"
      :on-click="({ calendarEvent }) => open(calendarEvent)"
      :on-cell-click="({ date }) => start(date)"
      @range-change="moved"
    />
  </div>

  <EventDialog
    v-model="writing"
    :editing="editing"
    :on="startingOn"
    @saved="reload()"
  />
</template>

<script setup>
import { computed, inject, onMounted, ref, unref } from 'vue'
import { useRouter } from 'vue-router'
import { Alert, Button, Calendar, PageHeader } from '@/ui'
import Trail from '@/shared/components/Trail.vue'
import { useCrumbs } from '@/shared/composables/useCrumbs'
import EventDialog from '@/modules/onecalendar/components/EventDialog.vue'
import { workspace } from '@/shared/lib/workspace'
import { WINDOW_BAR } from '@/modules/onespace/lib/desk/windows'
import { KIND, writeAt } from '@/shared/lib/url/at'
import { useIsMobile } from '@/modules/onespace/lib/shell/breakpoint'
import { settings } from '@/shared/lib/runtime/format'
import { errorText } from '@/shared/lib/runtime/errors'
import { __ } from '@/shared/lib/runtime/translate'
import {
  EVERYONE, MINE, diary, diaryEvents, look, showing,
} from '@/modules/onespace/lib/screen/diary'

/**
 * Read-only, and more firmly than the screen calendar is: every entry here
 * belongs to a different doctype under a different screen's rules, so dragging
 * one would be writing a field on a record this surface knows nothing about.
 *
 * And a day on a phone — §E6. A month grid at 390px is thirty-one cells four
 * characters wide, which is a month you can count but not read; what a person
 * with a phone in their hand is asking is "what have I got on". That is the
 * component's own `Day` mode rather than a media query over the month, which
 * is the audit's point: it is a different view, not a narrower one. The
 * switcher stays, so somebody who does want the month can still have it.
 */
const phone = useIsMobile()
const CONFIG = computed(() => ({
  isEditMode: false,
  defaultMode: phone.value ? 'Day' : 'Month',
  // The clock the workspace set — §D1. The grid was on the component's own
  // default, so a workspace on a 24-hour clock everywhere else had one
  // surface saying 2 PM.
  timeFormat: settings().time.includes('a') ? '12h' : '24h',
}))

/**
 * Whether this is inside a window, and where its bar is.
 *
 * Held until mounted, because a `<Teleport>` resolves its target when it
 * patches and a target appearing in the same tick is one Vue warns about and
 * then ignores — the same hold `EditorChrome` makes, for the same reason.
 */
const bar = inject(WINDOW_BAR, null)
const ready = ref(false)
onMounted(() => { ready.value = true })
const inWindow = computed(() => (ready.value ? unref(bar) || '' : ''))

/**
 * The two lenses, as the row of buttons draws them.
 *
 * Built in a function rather than at module scope for the reason every other
 * list of `__()` in this app is: a constant built when the module loads calls
 * the translator before the catalogue has arrived.
 */
const LENSES = [
  { lens: MINE, label: __('Mine'), icon: 'lucide-user' },
  { lens: EVERYONE, label: __('Everyone'), icon: 'lucide-users' },
]

const router = useRouter()

const rows = ref([])
const error = ref('')
// Through the rail's switches, and coloured by the same list they are drawn
// from — so a row's dot and its entries on the grid are one fact.
const events = computed(() => diaryEvents(showing(rows.value), diary.sources))

/** Where an entry came from, so a click can go back to it. */
const source = (id) => rows.value.find((one) => one.id === id) || null

const writing = ref(false)
const editing = ref('')
const startingOn = ref('')

/** New, on a day if the reader picked one by clicking a cell. */
function start(on = '') {
  editing.value = ''
  startingOn.value = String(on || '')
  writing.value = true
}

function open(event) {
  const found = source(event?.id)
  if (!found) return
  // Yours opens here, and everything else opens where it lives.
  if (found.mine || !found.screen) {
    editing.value = found.record
    startingOn.value = ''
    writing.value = true
    return
  }
  router.push({
    name: 'Screen',
    params: { spaceCode: found.space },
    query: { screen: found.screen, at: writeAt(KIND.RECORD, found.record) },
  })
}

/**
 * The days now on screen, which is the whole of what this page fetches.
 * `rangeChange` fires on mount as well as on every move, so there is no second
 * load on open.
 */
// The days last asked for, so a save can ask for them again. The grid does not
// re-emit its range when nothing about it moved.
const days = ref(null)

const reload = () => (days.value ? moved(days.value) : null)

/**
 * Change the lens, and ask the same days again.
 *
 * The lens is the server's question rather than a filter over what arrived:
 * "everyone" reads sources "mine" never asked for, so there is nothing in the
 * browser to filter down to. `docs/WORK.md` §6.
 */
function lookAt(lens) {
  if (diary.lens === lens) return
  look(lens)
  reload()
}

async function moved({ startDate, endDate }) {
  if (!startDate || !endDate) return
  days.value = { startDate, endDate }
  error.value = ''
  try {
    const answer = await workspace.agenda(startDate, endDate, diary.lens)
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

// One root for every surface — §C1.
const crumbs = useCrumbs({ label: __('Calendar'), route: { name: 'Calendar' } })
</script>
