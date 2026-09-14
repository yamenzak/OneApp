<template>
  <!--
    The employee's own page.

    Every other screen in OneHR is written for the person who *administers*
    people — the directory, the attendance board, the payroll run — and the
    person each of those rows is about had, until this, nowhere to stand.
    `docs/HORILLA.md` §3.1 is the same finding read off a competitor: half the
    entries in an HR rail have two readers and only one of them was served.

    One page, no navigation. Somebody asking how much leave they have left
    should not have to know the answer lives in a doctype called Leave
    Allocation. So every block is here and the server sends all of them in one
    call — `oneapp/onehr/me.py` — because eight calls is eight spinners and a
    page that assembles itself in front of the reader.

    Blocks that have nothing to say are absent rather than empty. A workspace
    that does not run payroll should not have a payslips card with a dash in
    it every day for a year.
  -->
  <div class="mx-auto flex w-full max-w-5xl flex-col gap-4 p-4">
    <LoadingText v-if="loading && !loaded" :text="__('Loading')" />

    <!--
      The two ways there is no page. Both are ordinary states of a real site
      and each has its own sentence — a workspace without HRMS, and a login
      nobody linked to a record, which is a field on the person's own Employee
      and the one thing an officer can fix in a minute.
    -->
    <EmptyState
      v-else-if="!employee"
      icon="lucide-user-round"
      :title="reason === 'no-hrms'
        ? __('This workspace does not keep HR records')
        : __('Your login is not linked to an employee record')"
      :description="reason === 'no-hrms'
        ? __('There is nothing here until it does.')
        : __('Ask whoever looks after people to set the User ID on your record.')"
    />

    <template v-else>
      <!--
        The band: who you are, where you are now, and the one control this
        whole page exists to put one click away.
      -->
      <Panel ground="sunken" pad="loose" data-slot="me-band">
        <div class="flex flex-col gap-4 md:flex-row md:items-center">
          <div class="shrink-0">
            <img
              v-if="employee.image"
              :src="employee.image"
              :alt="employee.employee_name"
              class="size-16 rounded-full object-cover ring-1 ring-outline-gray-2"
            >
            <div
              v-else
              class="flex size-16 items-center justify-center rounded-full bg-surface-gray-2 text-2xl text-ink-muted ring-1 ring-outline-gray-2"
              aria-hidden="true"
            >{{ initial }}</div>
          </div>

          <div class="flex min-w-0 flex-1 flex-col gap-1">
            <div class="flex min-w-0 flex-wrap items-center gap-2">
              <h1
                data-slot="me-name"
                class="min-w-0 truncate text-xl-semibold text-ink-primary"
              >{{ employee.employee_name }}</h1>
              <Badge
                v-if="presence"
                data-slot="me-presence"
                :theme="look.theme"
                variant="subtle"
                :label="presenceLabel"
              />
            </div>
            <p class="truncate text-sm text-ink-secondary">{{ subtitle }}</p>
          </div>

          <!--
            Checking in. Which way it points is the server's answer, not the
            button's — `checkin.py` reads where you are and writes the opposite,
            so a page left open since this morning cannot file the wrong one.
            Absent, not disabled, where there is no direction to offer: nobody
            needs a greyed-out button explaining that today is a holiday.
          -->
          <Button
            v-if="direction"
            data-slot="me-checkin"
            variant="solid"
            :loading="filing"
            :icon-left="direction === 'IN' ? 'lucide-log-in' : 'lucide-log-out'"
            :label="direction === 'IN' ? __('Check in') : __('Check out')"
            @click="checkIn"
          />
        </div>
      </Panel>

      <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
        <!--
          What you are owed and how you have been, in one card. They are read
          together — "have I got the days, and am I in credit" is one question —
          and the two components are the person record's own.
        -->
        <Panel
          v-if="balance.length || days.length"
          data-slot="me-time"
          class="md:col-span-2"
        >
          <h2 class="mb-3 text-base-semibold text-ink-primary">{{ __('Your time') }}</h2>
          <div class="flex flex-col gap-5 md:flex-row md:items-start md:gap-10">
            <DayStrip :days="days" :weeks="weeks" />
            <LeaveBalance :balance="balance" :label="__('Leave left')" />
          </div>
        </Panel>

        <!-- What is coming up: your approved leave and everybody's days off,
             in one list because they answer the same question. -->
        <Panel v-if="upcoming.length" data-slot="me-upcoming">
          <h2 class="mb-3 text-base-semibold text-ink-primary">{{ __('Coming up') }}</h2>
          <ul class="flex flex-col gap-2">
            <li
              v-for="(one, at) in upcoming"
              :key="`${one.kind}-${one.date}-${at}`"
              class="flex items-center gap-2.5 text-sm"
            >
              <Icon
                :name="one.kind === 'leave' ? 'lucide-palmtree' : 'lucide-calendar-off'"
                class="size-4 shrink-0 text-ink-muted"
              />
              <span class="min-w-0 flex-1 truncate text-ink-primary">{{ one.label }}</span>
              <span class="shrink-0 text-xs tabular-nums text-ink-secondary">
                {{ span(one) }}
              </span>
            </li>
          </ul>
        </Panel>

        <!-- Everything you have asked for lately, across the four doors you
             file at, newest first. One list rather than four. -->
        <Panel v-if="requests.length || leaveSpec.can_create" data-slot="me-requests">
          <div class="mb-3 flex items-center gap-2">
            <h2 class="text-base-semibold text-ink-primary">{{ __('What you asked for') }}</h2>
            <!--
              And the one thing this page is opened to *do* rather than read.
              The form opens here instead of on the Leave screen: a person who
              has just read that they have eighteen days left is a person about
              to ask for some, and sending them to a list first is the four
              clicks `docs/HORILLA.md` §3.4 is about, one door along.

              `CreateDialog` over the Leave screen's own spec, so the fields,
              the validation and the permission are that screen's — and
              `employee` arrives filled in, because there is exactly one it
              could be.
            -->
            <Button
              v-if="leaveSpec.can_create"
              class="ms-auto"
              data-slot="me-ask"
              variant="subtle"
              icon-left="lucide-plus"
              :label="__('Ask for leave')"
              @click="asking = true"
            />
          </div>

          <CreateDialog
            v-if="leaveSpec.can_create"
            v-model="asking"
            :spec="leaveSpec"
            :space-code="spaceCode"
            screen="leave"
            :preset="{ employee: employee.name }"
            @created="load"
          />

          <ul class="flex flex-col gap-2">
            <li
              v-for="one in requests"
              :key="`${one.doctype}-${one.name}`"
              class="flex items-center gap-2.5 text-sm"
            >
              <span class="min-w-0 flex-1 truncate text-ink-primary">{{ one.subject }}</span>
              <Badge v-if="one.state" variant="subtle" :label="one.state" theme="gray" />
            </li>
          </ul>
        </Panel>

        <Panel v-if="goals.length" data-slot="me-goals">
          <h2 class="mb-3 text-base-semibold text-ink-primary">{{ __('Your goals') }}</h2>
          <!--
            The same row as a leave type below: words, a bar, a number. Two
            blocks on one page measuring two different things should not each
            have invented their own way of drawing a measure — and a title with
            a 2px rule under it reads as an underline rather than as progress,
            which is what the first draft of this looked like.
          -->
          <ul class="flex flex-col gap-2">
            <li v-for="one in goals" :key="one.name" class="flex items-center gap-3">
              <span class="w-40 shrink-0 truncate text-xs text-ink-secondary" :title="one.subject">
                {{ one.subject }}
              </span>
              <Progress class="min-w-0 flex-1" size="md" :value="share(one.progress)" />
              <span class="w-10 shrink-0 text-end text-xs tabular-nums text-ink-secondary">
                {{ __('{0}%', [String(Math.round(one.progress))]) }}
              </span>
            </li>
          </ul>
        </Panel>

        <!--
          Your own payslips, submitted ones only. Absent rather than empty
          where pay is not this reader's to see, which on most workspaces is
          everybody but the payroll seat and the person the slip is about —
          `onehr/own.py` is the one rule that makes the second half of that
          sentence true without widening a grant.
        -->
        <Panel v-if="payslips.length" data-slot="me-payslips">
          <h2 class="mb-3 text-base-semibold text-ink-primary">{{ __('Your payslips') }}</h2>
          <ul class="flex flex-col gap-2">
            <li
              v-for="one in payslips"
              :key="one.name"
              class="flex items-center gap-2.5 text-sm"
            >
              <span class="min-w-0 flex-1 truncate text-ink-primary">{{ period(one) }}</span>
              <span class="shrink-0 tabular-nums text-ink-secondary">
                {{ money(one.net, one.currency) }}
              </span>
            </li>
          </ul>
        </Panel>

        <!--
          Who you will speak to today, and where each of them is. Your manager,
          the people who answer to the same one, and the people who answer to
          you — one list, because a page about your own day does not need three
          headings to say "these are your people".
        -->
        <Panel v-if="team.length" data-slot="me-team" class="md:col-span-2">
          <h2 class="mb-3 text-base-semibold text-ink-primary">{{ __('Your people') }}</h2>
          <ul class="flex flex-wrap gap-x-6 gap-y-3">
            <li
              v-for="one in team"
              :key="one.name"
              class="flex min-w-0 items-center gap-2.5"
            >
              <Avatar
                :label="one.employee_name"
                :image="one.image || undefined"
                shape="circle"
                size="lg"
              />
              <div class="flex min-w-0 flex-col">
                <span class="truncate text-sm text-ink-primary">{{ one.employee_name }}</span>
                <span class="flex items-center gap-1.5 text-xs text-ink-muted">
                  <span class="size-1.5 rounded-full" :class="dot(one)" />
                  <span class="truncate">{{ mateLabel(one) }}</span>
                </span>
              </div>
            </li>
          </ul>
        </Panel>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import { Avatar, Badge, Button, Icon, LoadingText, Progress } from '@/ui'
import CreateDialog from '@/modules/onespace/components/screen/record/CreateDialog.vue'
import DayStrip from '@/modules/onespace/components/people/DayStrip.vue'
import LeaveBalance from '@/modules/onespace/components/people/LeaveBalance.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import Panel from '@/shared/components/Panel.vue'
import { presenceLook, presenceSince } from '@/modules/onespace/lib/screen/presence'
import { date as onDate, money } from '@/shared/lib/runtime/format'
import { workspace } from '@/shared/lib/workspace'
import { notifyError } from '@/shared/lib/runtime/notify'
import { __ } from '@/shared/lib/runtime/translate'

const { spaceCode } = defineProps({
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  /** The resolved screen. Nothing here reads it — the page is about the
   *  reader, not about a doctype — and it is declared because the host
   *  passes it to every custom screen. */
  spec: { type: Object, default: () => ({}) },
})

/** How a colleague's dot is tinted. The pill's own themes, one step down. */
const DOTS = {
  green: 'bg-surface-green-5',
  amber: 'bg-surface-amber-5',
  blue: 'bg-surface-blue-5',
  red: 'bg-surface-red-5',
  gray: 'bg-surface-gray-5',
}

/** How somebody is related to the reader, in words. */
const HOW = {
  manager: () => __('Your manager'),
  peer: () => __('Alongside you'),
  report: () => __('Reports to you'),
}

const loading = ref(false)
const loaded = ref(false)
const filing = ref(false)
const asking = ref(false)
const found = ref({})

/**
 * The Leave screen, as that screen describes itself.
 *
 * Fetched rather than declared, and it is the permission as well as the shape:
 * `can_create` is the server's answer to whether this reader may file one, so a
 * seat that cannot gets no button rather than a dialog that fails at the end.
 */
const leaveSpec = ref({})

const employee = computed(() => found.value.employee || null)
const reason = computed(() => found.value.reason || '')
const presence = computed(() => found.value.presence || null)
const days = computed(() => found.value.history?.days || [])
const balance = computed(() => found.value.history?.balance || [])
const weeks = computed(() => found.value.history?.weeks || 0)
const requests = computed(() => found.value.requests || [])
const payslips = computed(() => found.value.payslips || [])
const goals = computed(() => found.value.goals || [])
const team = computed(() => found.value.team || [])
const upcoming = computed(() => found.value.upcoming || [])

/** Which way the control points, or nothing at all. The server's answer. */
const direction = ref('')

const look = computed(() => presenceLook(presence.value))

/**
 * The pill's words: the state, and the time it started where there is one.
 *
 * The same sentence the person record draws, because it is the same fact —
 * "In · 09:41" rather than "In", the hour being most of what anybody wants
 * from it.
 */
const presenceLabel = computed(() => {
  const one = presence.value
  if (!one) return ''
  const extra = presenceSince(one) || one.detail || ''
  return extra ? `${look.value.label} · ${extra}` : look.value.label
})

/** A job title and where it sits, as one quiet line under the name. */
const subtitle = computed(() => {
  const one = employee.value
  if (!one) return ''
  return [one.designation, one.department_name, one.reports_to_name
    ? __('Reports to {0}', [one.reports_to_name])
    : ''].filter(Boolean).join(' · ')
})

/** The first character of a name, by grapheme — an initial, not a code unit. */
const initial = computed(() => {
  const name = employee.value?.employee_name || ''
  if (!name) return ''
  const segments = new Intl.Segmenter(undefined, { granularity: 'grapheme' })
  return [...segments.segment(name)][0]?.segment?.toUpperCase() || ''
})

/** One day, or a run of them. Through `lib/runtime/format`, the one clock. */
const span = (one) =>
  one.until && one.until !== one.date
    ? __('{0} – {1}', [onDate(one.date), onDate(one.until)])
    : onDate(one.date)

const period = (one) => span({ date: one.from, until: one.until })

const dot = (one) => DOTS[presenceLook(one.presence).theme] || DOTS.gray

/** A percentage, clamped. A goal at 140% is a typo, not a bar off the end. */
const share = (value) => Math.min(Math.max(Number(value) || 0, 0), 100)

/** How they are related, and where they are, in one line. */
const mateLabel = (one) => {
  const how = HOW[one.how]?.() || ''
  const where = presenceLook(one.presence).label
  return how ? `${how} · ${where}` : where
}

const load = async () => {
  loading.value = true
  try {
    found.value = (await workspace.myHr()) || {}
    if (!found.value.employee) return
    // After the page, and only where there is somebody to file for. Two more
    // requests on a page that has already drawn itself, rather than two more
    // spinners in front of one that has not.
    const [now, leave] = await Promise.all([
      found.value.can_check_in ? workspace.checkInDirection() : null,
      workspace.screenSpec(spaceCode, 'leave').catch(() => ({})),
    ])
    direction.value = now?.direction || ''
    leaveSpec.value = leave || {}
  } finally {
    loaded.value = true
    loading.value = false
  }
}

/**
 * File one, then take the server's word for what happened.
 *
 * The presence that comes back is read *after* the write, so the pill and the
 * button cannot disagree with each other for as long as a second request would
 * take — which is the window in which somebody presses Check in twice.
 */
const checkIn = async () => {
  if (filing.value) return
  filing.value = true
  try {
    const answer = await workspace.checkIn()
    found.value = { ...found.value, presence: answer?.presence || found.value.presence }
    direction.value = (await workspace.checkInDirection())?.direction || ''
  } catch (error) {
    notifyError(error)
  } finally {
    filing.value = false
  }
}

onMounted(load)
</script>
