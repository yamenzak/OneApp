<template>
  <!--
    What is waiting on you, across every space.

    The record header has always offered a workflow's transitions, which is
    right and is only half an answer: it serves somebody who already knows
    which record to open. An approver's actual question is the other one, and
    until now the product had nowhere to ask it — while the framework had been
    writing a `Workflow Action` row per approver on every transition the whole
    time.

    **Act from here.** Approving three expense claims should not be three
    record pages. The verbs are the record's own — `docflow._transitions`, the
    same call the header makes — and pressing one calls the endpoint the header
    calls, with the space and screen the server placed the row in. There is no
    second write path, which is the whole reason this is a screen and not a
    feature.

    **The title is a link and the verbs are not.** Reading the thing you are
    approving is the common case for anything that is not obvious from its
    name, and it must not be something you reach by nearly pressing Approve.
  -->
  <div class="mx-auto flex w-full max-w-4xl flex-col gap-4 p-4">
    <DataList
      :source="source"
      :skeleton="4"
      skeleton-class="h-14 w-full"
      body-class="gap-1"
    >
      <template #empty>
        <EmptyState
          icon="lucide-inbox"
          :title="__('Nothing is waiting on you')"
          :description="__('Anything needing your approval turns up here, from every space.')"
        />
      </template>

      <template #row="{ row }">
        <Panel :data-slot="`waiting-${row.doctype}-${row.name}`">
          <div class="flex flex-wrap items-center gap-3">
            <Icon :name="row.icon" class="size-4 shrink-0 text-ink-muted" :aria-hidden="true" />

            <component
              :is="row.placed ? 'router-link' : 'span'"
              :to="row.placed ? routeFor(row) : undefined"
              class="min-w-0 flex-1 text-sm text-ink-primary"
              :class="row.placed ? LINK : ''"
              :data-slot="row.placed ? 'waiting-open' : 'waiting-unplaced'"
            >
              <span class="block truncate">{{ row.title }}</span>
              <span class="block truncate text-xs text-ink-muted">
                {{ said(row) }}
              </span>
            </component>

            <Badge v-if="row.state" variant="subtle" :label="row.state" />

            <span v-if="row.verbs.length" class="flex shrink-0 items-center gap-2">
              <Button
                v-for="verb in row.verbs"
                :key="verb.action"
                :variant="verb.cancels ? 'subtle' : 'solid'"
                :theme="verb.cancels ? 'red' : 'gray'"
                :label="verb.action"
                :loading="running === key(row, verb)"
                :data-slot="verb.cancels ? 'waiting-refuse' : 'waiting-act'"
                @click="press(row, verb)"
              />
            </span>
          </div>
        </Panel>
      </template>
    </DataList>

    <!--
      Anything that cancels asks first, and the question is the state's own
      `doc_status` rather than the word on the button: "Reject" and "Return to
      draft" read the same and one of them unwrites a ledger.
    -->
    <Dialog v-model="confirming" :title="pending?.verb?.action || __('Cancel this record')">
      <p class="text-p-base text-ink-secondary">
        {{ __('This cancels the record. What it wrote is unwritten.') }}
      </p>
      <template #actions>
        <Button :label="__('Never mind')" @click="confirming = false" />
        <Button
          variant="solid"
          theme="red"
          :label="pending?.verb?.action"
          @click="run(pending.row, pending.verb)"
        />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import { Badge, Button, Dialog, Icon } from '@/ui'

import DataList from '@/shared/components/DataList.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import Panel from '@/shared/components/Panel.vue'
import { staticSource } from '@/shared/lib/list/source'
import { workspace } from '@/shared/lib/workspace'
import { notifyError, notifySuccess } from '@/shared/lib/runtime/notify'
import { date as onDate } from '@/shared/lib/runtime/format'
import { __ } from '@/shared/lib/runtime/translate'
import { KIND, withAt } from '@/shared/lib/url/at'

//: Hoisted, because a string compared inside a `:class` is a class name
//: Tailwind's JIT never sees — `tests/token_audit.py` reads for exactly this.
const LINK = 'hover:underline'

const rows = ref([])
const loading = ref(false)
const running = ref('')
const confirming = ref(false)
const pending = ref(null)

const source = computed(() =>
  staticSource({
    rows: rows.value,
    key: (row) => `${row.doctype}/${row.name}`,
    loading: loading.value,
  }),
)

/** One row and one verb, as a key the spinner can be pinned to. */
const key = (row, verb) => `${row.doctype}/${row.name}/${verb.action}`

/** Where it is and when it arrived, on one line under the title. */
const said = (row) =>
  [row.placed ? `${row.label} · ${row.space_label}` : __('Not in a space you can open'),
   row.since ? onDate(row.since) : '']
    .filter(Boolean)
    .join(' · ')

/** The record, on the screen the server placed it in. */
const routeFor = (row) => ({
  name: 'Screen',
  params: { spaceCode: row.space },
  query: withAt({ screen: row.screen }, KIND.RECORD, row.name),
})

const read = async () => {
  loading.value = true
  try {
    rows.value = (await workspace.waitingOnMe())?.rows || []
  } catch (error) {
    notifyError(error)
  } finally {
    loading.value = false
  }
}

const press = (row, verb) => {
  if (!verb.cancels) return run(row, verb)
  pending.value = { row, verb }
  confirming.value = true
}

const run = async (row, verb) => {
  confirming.value = false
  running.value = key(row, verb)
  try {
    await workspace.workflowAction(row.space, row.screen, row.name, verb.action)
    notifySuccess(__('Done'))
    // Re-read rather than drop the row: a transition can put the document into
    // a state that is waiting on this same person again, and a list that
    // removed it would be telling them their turn is over when it is not.
    await read()
  } catch (error) {
    notifyError(error)
  } finally {
    running.value = ''
  }
}

onMounted(read)
</script>
