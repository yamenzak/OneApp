<template>
  <!--
    OneTask: a door onto the same tasks, from wherever you are standing.

    `docs/WORK.md` §12. It is not a space and it owns no table — every row here
    is an ERPNext `Task`, the same one OneProject's board draws. What it is for
    is the thing going there costs: capturing a line without leaving the
    document you are writing, ticking something off without losing the
    quotation you were in the middle of, starting the clock on the job you have
    just picked up.

    So it is deliberately three controls and two lists. Anything that wants a
    filter, a column or an order wants the space, and the foot says so and
    goes there.
  -->
  <!--
    The trail, on the route and not in the window.

    A window already has a name in its bar — `SpaceName` draws it — and a
    second header under it saying the same word is the band every window in
    this product was designed without. `WINDOW_BAR` is how a surface knows
    which of the two it is in; the diary makes the same split.
  -->
  <PageHeader v-if="!inWindow">
    <Trail :items="crumbs" />
  </PageHeader>

  <!--
    One column, capped. Inside the window the cap does nothing — it is 400px
    wide — and on the route it stops a list of one-line things spreading to
    1600px, which is the same list with the tick and the clock a foot apart.
  -->
  <div
    class="mx-auto flex min-h-0 w-full max-w-2xl flex-1 flex-col"
    data-slot="task-service"
  >
    <!--
      Capture, at the top and always there.

      Not behind a New button: the whole claim of an service is that a thought
      costs one keystroke to catch, and a button that opens a form is a form.
      A task made here has no project, which is what makes it free — ERPNext's
      Task has an optional project, so the inbox is a filter rather than a
      staging table somebody has to empty.
    -->
    <div class="shrink-0 border-b border-outline-gray-1 p-2">
      <TextInput
        v-model="said"
        :placeholder="__('Add a task…')"
        data-slot="task-capture"
        @keydown.enter="write()"
      >
        <template #prefix>
          <Icon name="lucide-plus" class="size-4 text-ink-gray-4" />
        </template>
      </TextInput>
    </div>

    <!--
      What is running, where something is.

      Above the lists rather than beside its row: a clock is one per person —
      `onetask/timing.py` — so it is a fact about the reader rather than about
      any row, and a window that hid it inside a scrolling list would be a
      window you have to hunt through to find out whether you are timing.
    -->
    <Row
      v-if="service.running.name"
      pad="tight"
      edge="none"
      :hover="false"
      data-slot="task-running"
    >
      <template #lead>
        <Icon name="lucide-clock" class="size-4 text-ink-amber-3" />
      </template>
      <span class="truncate text-base text-ink-primary">
        {{ service.running.subject || service.running.task }}
      </span>
      <template #trail>
        <Button
          variant="ghost"
          :label="__('Stop')"
          data-slot="task-stop"
          @click="clock('')"
        />
      </template>
    </Row>

    <!-- Mine, or what nobody has placed. Two words rather than a menu: there
         are two answers and they are the two questions this window is opened
         with. -->
    <div class="flex shrink-0 items-center gap-0.5 border-b border-outline-gray-1 px-2 py-1.5">
      <Button
        v-for="one in lists"
        :key="one.key"
        variant="ghost"
        :label="one.label"
        :class="showing === one.key ? '!bg-surface-gray-3' : ''"
        :data-slot="`task-list-${one.key}`"
        @click="showing = one.key"
      />
      <div class="flex-1" />
      <span class="pe-1 text-sm text-ink-muted">{{ rows.length }}</span>
    </div>

    <div class="min-h-0 flex-1 overflow-auto" data-slot="task-rows">
      <EmptyState
        v-if="service.ready && !rows.length"
        icon="lucide-check"
        :title="showing === MINE ? __('Nothing on you') : __('The inbox is empty')"
        :description="
          showing === MINE
            ? __('Work assigned to you turns up here.')
            : __('A task with no project waits here until somebody places it.')
        "
      />
      <Row
        v-for="row in rows"
        :key="row.name"
        :to="doorTo(row)"
        pad="tight"
        align="start"
        data-slot="task-row"
      >
        <template #lead>
          <!--
            The tick, and it is a button beside the row rather than the row's
            own click: pressing a task opens it, and a row that finished it
            instead is the one mistake a list like this must not make.
          -->
          <Button
            variant="ghost"
            icon="lucide-circle"
            :label="__('Tick off')"
            :tooltip="__('Tick off')"
            data-slot="task-tick"
            @click.prevent.stop="done(row)"
          />
        </template>
        <span class="block truncate text-base text-ink-primary">{{ row.subject }}</span>
        <span
          v-if="row.project_name"
          class="mt-0.5 block truncate text-sm text-ink-muted"
        >{{ row.project_name }}</span>
        <template #trail>
          <Button
            variant="ghost"
            icon="lucide-clock"
            :label="__('Start timing')"
            :tooltip="__('Start timing')"
            data-slot="task-start"
            @click.prevent.stop="clock(row.name)"
          />
        </template>
      </Row>
    </div>

    <!-- Where the rest of it is. A window with no way through to the space
         would be a window that has to grow one of everything. -->
    <div class="shrink-0 border-t border-outline-gray-1 p-2">
      <Button
        variant="ghost"
        icon-left="lucide-arrow-right"
        class="w-full"
        :label="__('Open the board')"
        data-slot="task-board"
        @click="openBoard()"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, inject, onMounted, ref, unref } from 'vue'
import { useRouter } from 'vue-router'
import { Button, Icon, PageHeader, TextInput } from '@/ui'
import EmptyState from '@/shared/components/EmptyState.vue'
import Row from '@/shared/components/Row.vue'
import Trail from '@/shared/components/Trail.vue'
import { useCrumbs } from '@/shared/composables/useCrumbs'
import { service, capture, clock, load, tick } from '@/modules/onetask/lib/service'
import { WINDOW_BAR } from '@/modules/onespace/lib/desk/windows'
import { KIND, writeAt } from '@/shared/lib/url/at'
import { session } from '@/modules/onespace/lib/shell/session'
import { nameOf } from '@/shared/lib/brand/naming'
import { __ } from '@/shared/lib/runtime/translate'

/** The two lists, by the key the server answers under. */
const MINE = 'mine'
const INBOX = 'inbox'

const router = useRouter()
const said = ref('')
const showing = ref(MINE)

/**
 * Whether this is inside a window, and where its bar is.
 *
 * Held until mounted, because a `<Teleport>` resolves its target when it
 * patches — the same hold the diary makes, for the same reason, and this one
 * only needs the *answer* rather than the teleport.
 */
const bar = inject(WINDOW_BAR, null)
const mounted = ref(false)
const inWindow = computed(() => (mounted.value ? unref(bar) || '' : ''))

// The mark's own name, never typed: `MARKS[id].name` is the one place a
// product name is written down — `CLAUDE.md`, and the reason is that four of
// the ids disagree with their names on purpose.
const crumbs = useCrumbs({ label: nameOf('onetask'), route: { name: 'Tasks' } })

// Built in a function rather than at module scope, for the reason every other
// list of `__()` in this app is: a constant built when the module loads calls
// the translator before the catalogue has arrived.
const lists = computed(() => [
  { key: MINE, label: __('Mine') },
  { key: INBOX, label: __('Inbox') },
])

const rows = computed(() => (showing.value === MINE ? service.mine : service.inbox))

/**
 * Which space the board is in.
 *
 * Read from the workspace rather than written down: OneProject is what a
 * manifest declaring the `oneproject` mark is called here, and a workspace
 * that renamed its space still has one. The tile is dark where there is none —
 * `lib/shell/apps.js` — so this always finds one when the window is open.
 */
const space = computed(
  () => session.spaces.find((one) => one.brand === 'oneproject')?.space_code || '',
)

const doorTo = (row) => (space.value
  ? {
    name: 'Screen',
    params: { spaceCode: space.value },
    query: { screen: 'tasks', at: writeAt(KIND.RECORD, row.name) },
  }
  : null)

const openBoard = () => {
  if (!space.value) return
  router.push({
    name: 'Screen',
    params: { spaceCode: space.value },
    query: { screen: 'tasks', type: 'board' },
  })
}

async function write() {
  const line = said.value.trim()
  if (!line) return
  said.value = ''
  await capture(line)
  // Onto the list it landed on, so the thing that was just typed is visible
  // rather than filed somewhere the reader has to go and check.
  showing.value = INBOX
}

const done = (row) => tick(row.name, true)

onMounted(() => {
  mounted.value = true
  load()
})
</script>
