<template>
  <!--
    Taking the register: one day, everybody on it, Present already chosen.

    The counterpart of `Home.vue`. That page is the one screen in OnePeople written
    for the person a record is about; this is the one written for the person
    who has to write forty records before lunch, and neither is a list.

    The whole design is in the default. Marking attendance a record at a time
    means answering "who was here" forty-nine times to find out about the one
    who was not, so the roll arrives with everybody Present and the work is
    turning off the exceptions. Three kinds of row are not a choice at all —
    somebody on approved leave, somebody whose own holiday list has the day
    off, somebody already marked — and each says why rather than being missing,
    because a register with names quietly absent from it is a register nobody
    can check against the room.

    Nothing here decides a permission or invents a way to write: the roll is
    `get_list` on Employee as the reader, and the writes go through HRMS's own
    `mark_attendance`. See `oneapp/onehr/roster.py`.
  -->
  <div class="mx-auto flex w-full max-w-4xl flex-col gap-4 p-4">
    <!-- The day, and what is left to do to it. -->
    <Panel ground="sunken" pad="loose" data-slot="roster-band">
      <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div class="flex min-w-0 flex-col gap-1">
          <h2 class="text-xl-semibold text-ink-primary">{{ __('Mark the day') }}</h2>
          <p class="text-sm text-ink-secondary">{{ standing }}</p>
        </div>
        <div class="flex shrink-0 items-center gap-2">
          <Button
            icon-left="lucide-chevron-left"
            :label="__('Previous day')"
            variant="ghost"
            :disabled="loading"
            data-slot="roster-back"
            @click="step(-1)"
          />
          <FormControl
            type="date"
            :model-value="on"
            class="w-40"
            data-slot="roster-date"
            @update:model-value="pick"
          />
          <Button
            icon-left="lucide-chevron-right"
            :label="__('Next day')"
            variant="ghost"
            :disabled="loading"
            data-slot="roster-forward"
            @click="step(1)"
          />
        </div>
      </div>
    </Panel>

    <LoadingText v-if="loading && !loaded" :text="__('Loading')" />

    <EmptyState
      v-else-if="!people.length"
      icon="lucide-users"
      :title="__('Nobody to mark')"
      :description="__('This workspace has no active employees, or none you can see.')"
    />

    <template v-else>
      <!--
        The row. A face, who they are, and either the five statuses or the
        sentence saying why this one is settled.
      -->
      <Panel pad="none">
        <ul class="divide-y divide-outline-gray-1">
          <li
            v-for="row in people"
            :key="row.employee"
            :data-slot="'roster-row'"
            :data-fixed="row.fixed || ''"
            class="flex flex-col gap-2 px-4 py-3 md:flex-row md:items-center md:gap-4"
          >
            <div class="flex min-w-0 flex-1 items-center gap-3">
              <Avatar
                :image="row.image"
                :label="row.label"
                shape="circle"
                size="lg"
              />
              <div class="flex min-w-0 flex-col">
                <span class="truncate text-base-medium text-ink-primary">{{ row.label }}</span>
                <span v-if="row.detail" class="truncate text-xs text-ink-muted">
                  {{ row.detail }}
                </span>
              </div>
            </div>

            <!--
              Settled. The verdict and why it is not yours to change here —
              and for a day already marked, the way through to the record that
              is the only place it can be.
            -->
            <div
              v-if="row.fixed"
              class="flex shrink-0 flex-wrap items-center gap-2"
              data-slot="roster-settled"
            >
              <StateBadge v-if="row.status" :label="row.status" :states="states" />
              <span class="text-xs text-ink-muted">{{ row.because }}</span>
              <Button
                v-if="row.attendance"
                variant="ghost"
                icon-left="lucide-arrow-up-right"
                :label="__('Open')"
                @click="open(row.attendance)"
              />
            </div>

            <!--
              Markable. Five buttons rather than a menu: the whole point is
              that changing one is a single press, and a Select is a press to
              open and a press to choose.
            -->
            <div v-else class="flex shrink-0 flex-wrap items-center gap-1" data-slot="roster-pick">
              <Button
                v-for="status in statuses"
                :key="status"
                :variant="row.status === status ? 'solid' : 'subtle'"
                :label="__(status)"
                :data-status="status"
                :data-chosen="row.status === status ? 'yes' : 'no'"
                @click="row.status = status"
              />
              <!--
                Late is a mark on a day that was otherwise worked, so it is
                offered only beside the two statuses that mean somebody was.
                Pre-pressed where the clock already says so, which is the one
                thing a register taken from memory always gets wrong.
              -->
              <Button
                v-if="row.status === 'Present' || row.status === 'Work From Home'"
                :variant="row.late ? 'solid' : 'subtle'"
                icon-left="lucide-clock-alert"
                :label="__('Late')"
                data-slot="roster-late"
                :data-chosen="row.late ? 'yes' : 'no'"
                @click="row.late = !row.late"
              />
            </div>
          </li>
        </ul>
      </Panel>

      <div class="flex flex-wrap items-center justify-between gap-2">
        <p class="text-xs text-ink-muted">{{ counted }}</p>
        <Button
          variant="solid"
          icon-left="lucide-check"
          :label="__('Mark {0}', [String(markable.length)])"
          :loading="saving"
          :disabled="!markable.length"
          data-slot="roster-save"
          @click="save"
        />
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { Avatar, Button, FormControl, LoadingText } from '@/ui'
import EmptyState from '@/shared/components/EmptyState.vue'
import Panel from '@/shared/components/Panel.vue'
import StateBadge from '@/modules/onespace/components/screen/fields/StateBadge.vue'
import { workspace } from '@/shared/lib/workspace'
import { notifyError, notifySuccess } from '@/shared/lib/runtime/notify'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  spaceCode: { type: String, required: true },
  screen: { type: String, default: '' },
  spec: { type: Object, default: () => ({}) },
})

const router = useRouter()

/** Where a marked day is opened. The attendance screen's own record view —
 *  `lib/screen/recordViews.js`, `day` — which is the page that answers why a
 *  verdict is the verdict. */
const DAYS = 'attendance'

/** A day, in milliseconds. The arrows step by one and the control is a date
 *  input, so both speak `YYYY-MM-DD`. */
const DAY = 86_400_000

const on = ref('')
const people = ref([])
const statuses = ref([])
const loading = ref(false)
const loaded = ref(false)
const saving = ref(false)

/** The colours a status draws in, which are the *screen's* and not this page's:
 *  green for a day worked is the same green on the grid, the record and here. */
const states = computed(() => props.spec?.states || [])

const markable = computed(() => people.value.filter((one) => !one.fixed))
const settled = computed(() => people.value.filter((one) => one.fixed))

const standing = computed(() => {
  if (!loaded.value) return __('Everybody on one page, with the exceptions already filled in.')
  if (!people.value.length) return ''
  const left = markable.value.length
  if (!left) return __('Every one of them is settled. There is nothing to mark.')
  return __('{0} to mark. {1} already settled.',
            [String(left), String(settled.value.length)])
})

const counted = computed(() => {
  const late = markable.value.filter((one) => one.late).length
  const away = markable.value.filter((one) => one.status === 'Absent').length
  if (!late && !away) return __('Everybody present.')
  const parts = []
  if (away) parts.push(__('{0} absent', [String(away)]))
  if (late) parts.push(__('{0} late', [String(late)]))
  return parts.join(' · ')
})

const pick = (value) => { on.value = String(value || '') }

const step = (days) => {
  const [y, m, d] = String(on.value || '').split('-').map(Number)
  if (!y || !m || !d) return
  const when = new Date(new Date(y, m - 1, d).getTime() + days * DAY)
  const pad = (n) => String(n).padStart(2, '0')
  on.value = `${when.getFullYear()}-${pad(when.getMonth() + 1)}-${pad(when.getDate())}`
}

const open = (name) => {
  router.push({ query: { screen: DAYS, at: `record:${name}` } })
}

const load = async () => {
  loading.value = true
  try {
    const found = await workspace.rollCall(on.value)
    on.value = found?.on || on.value
    statuses.value = found?.statuses || []
    // A fresh object per row: these are what the controls write into, and
    // reusing the server's dicts would make a reload a silent undo of an
    // unsaved change rather than the deliberate one it is.
    people.value = (found?.people || []).map((one) => ({ ...one }))
    loaded.value = true
  } catch (raised) {
    notifyError(raised)
    people.value = []
  } finally {
    loading.value = false
  }
}

const save = async () => {
  saving.value = true
  try {
    const answer = await workspace.markDay(
      on.value,
      markable.value.map((one) => ({
        employee: one.employee, status: one.status, late: !!one.late,
      })),
    )
    notifySuccess(
      answer?.skipped
        ? __('{0} marked, {1} were already marked by somebody else.',
             [String(answer.written), String(answer.skipped)])
        : __('{0} marked.', [String(answer?.written ?? 0)]),
    )
    await load()
  } catch (raised) {
    notifyError(raised)
  } finally {
    saving.value = false
  }
}

watch(on, load, { immediate: true })
</script>
