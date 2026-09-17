<template>
  <!--
    A payslip, as the person paid reads one.

    The one record in OnePeople that is a *document* rather than a working state —
    nobody edits a payslip, they check it — and the form is the worst possible
    shape for checking: forty fields across five sections, with the two things
    it is actually made of drawn as spreadsheet grids at the bottom. What it
    says is "this much, less this much, leaves this", and the two lists of
    components are the argument for each half.

    So: the period and the net, then earnings and deductions side by side with
    the totals under them, then the days the pay was worked out over — because
    the question after "why is this less than last month" is almost always
    "how many days did they count".

    Nothing is fetched. Every number here is on the record already, child
    tables included, which is why this page has no loader and no permission of
    its own: reading the payslip is what entitles you to read what is on it.
  -->
  <RecordPage name="payslip">
    <RecordHead
      :eyebrow="eyebrow"
      eyebrow-slot="payslip-period"
      :title="title"
      title-slot="payslip-who"
      :badge="badge"
      :states="states"
    >
      <p v-if="worked" data-slot="payslip-days" class="text-sm text-ink-secondary">
        {{ worked }}
      </p>

      <!-- What lands in the account. The one number anybody opens this for. -->
      <template #aside>
        <RecordTally name="payslip-net" :value="net" :caption="__('net')" />
      </template>
    </RecordHead>

    <FactRow :facts="facts" slot-name="payslip-facts" />

    <!--
      The two halves, side by side on anything wider than a phone. Side by side
      rather than stacked because they are a subtraction: a column of earnings
      above a column of deductions reads as two lists, and the point is that
      one is taken from the other.
    -->
    <div class="grid grid-cols-1 gap-px bg-surface-gray-2 md:grid-cols-2">
      <div
        v-for="side in sides"
        :key="side.key"
        :data-slot="`payslip-${side.key}`"
        class="flex flex-col gap-2 bg-surface-base px-4 py-4 md:px-6"
      >
        <p class="text-xs text-ink-muted">{{ side.label }}</p>

        <ul v-if="side.rows.length" class="flex flex-col">
          <li
            v-for="row in side.rows"
            :key="row.key"
            data-slot="payslip-line"
            class="flex items-baseline gap-3 border-b border-outline-gray-1 py-1.5 last:border-b-0"
          >
            <span class="min-w-0 flex-1 truncate text-sm text-ink-secondary">
              {{ row.label }}
            </span>
            <span class="shrink-0 text-sm tabular-nums text-ink-primary">
              {{ row.amount }}
            </span>
          </li>
        </ul>
        <p v-else class="text-sm text-ink-gray-4">{{ side.empty }}</p>

        <div class="mt-1 flex items-baseline gap-3 border-t border-outline-gray-2 pt-2">
          <span class="min-w-0 flex-1 truncate text-xs text-ink-muted">
            {{ side.total }}
          </span>
          <span class="shrink-0 text-base-medium tabular-nums text-ink-primary">
            {{ side.sum }}
          </span>
        </div>
      </div>
    </div>
  </RecordPage>
</template>

<script setup>
import { computed } from 'vue'

import FactRow from '@/modules/onespace/components/people/FactRow.vue'
import RecordHead from '@/modules/onespace/components/screen/records/RecordHead.vue'
import RecordPage from '@/modules/onespace/components/screen/records/RecordPage.vue'
import RecordTally from '@/modules/onespace/components/screen/records/RecordTally.vue'
import { cellText } from '@/modules/onespace/lib/screen/cells'
import { fieldSpec } from '@/modules/onespace/lib/screen/fields'
import { date as onDate, money } from '@/shared/lib/runtime/format'
import { session } from '@/modules/onespace/lib/shell/session'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  record: { type: Object, required: true },
  spec: { type: Object, default: () => ({}) },
  showcase: { type: Object, default: () => ({}) },
  title: { type: String, default: '' },
  compact: { type: Boolean, default: false },
  revision: { type: Number, default: 0 },
  canWrite: { type: Boolean, default: false },
})

defineEmits(['open'])

/** How many facts a band carries. `showcase.FACTS`, and the same four. */
const FACTS = 4

/** How many lines a side draws. A salary structure with more components than
 *  this is one whose payslip is a report, and the form below has all of them. */
const LINES = 20

/** HRMS's own names. */
const FROM = 'start_date'
const TO = 'end_date'
const EARNINGS = 'earnings'
const DEDUCTIONS = 'deductions'
const GROSS = 'gross_pay'
const TAKEN = 'total_deduction'
const NET = 'net_pay'
const DAYS = 'total_working_days'
const PAID_DAYS = 'payment_days'
const UNPAID = 'leave_without_pay'
const STRUCTURE = 'salary_structure'
const PAID_BY = 'mode_of_payment'
const COMPONENT = 'salary_component'
const AMOUNT = 'amount'
const CURRENCY = 'currency'

const formats = computed(() => session.formats || {})
const columns = computed(() => props.spec?.all_columns || props.spec?.columns || [])
const states = computed(() => props.spec?.states || [])

const column = (fieldname) => columns.value.find((one) => one.fieldname === fieldname)
const linked = (fieldname) => props.record?._links?.[fieldname]

const text = (fieldname) => {
  const value = props.record?.[fieldname]
  if (value === null || value === undefined || value === '') return ''
  const found = column(fieldname)
  return found ? cellText(found, value, formats.value, linked(fieldname)) : String(value)
}

const badge = computed(
  () => String(props.record?.[props.spec?.status_field || 'status'] || ''),
)

const eyebrow = computed(() => {
  const from = props.record?.[FROM]
  const to = props.record?.[TO]
  if (!from) return ''
  return to ? `${onDate(from)} – ${onDate(to)}` : onDate(from)
})

/**
 * Money, in this slip's own currency.
 *
 * Off the record rather than off the session: a workspace paying somebody in
 * another currency writes it on the slip, and formatting it as the workspace's
 * own would be a number that is wrong by an exchange rate.
 */
const paid = (value) => {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return ''
  return money(amount, props.record?.[CURRENCY] || '')
}

const net = computed(() => paid(props.record?.[NET]) || '—')

/** How many days the pay was worked out over, which is the answer to almost
 *  every "why is this less than last month". */
const worked = computed(() => {
  const days = Number(props.record?.[DAYS]) || 0
  const paid = Number(props.record?.[PAID_DAYS]) || 0
  if (!days) return ''
  const unpaid = Number(props.record?.[UNPAID]) || 0
  const said = __('{0} of {1} days paid', [String(paid), String(days)])
  return unpaid ? `${said} · ${__('{0} unpaid', [String(unpaid)])}` : said
})

const lines = (field) => {
  const rows = props.record?.[field]
  if (!Array.isArray(rows)) return []
  return rows.slice(0, LINES).map((row, at) => ({
    key: row.name || `${at}`,
    label: String(row[COMPONENT] || ''),
    amount: paid(row[AMOUNT]),
  })).filter((row) => row.label)
}

const sides = computed(() => [
  {
    key: 'earnings',
    label: __('Earnings'),
    rows: lines(EARNINGS),
    empty: __('Nothing itemised.'),
    total: __('Gross'),
    sum: paid(props.record?.[GROSS]) || '—',
  },
  {
    key: 'deductions',
    label: __('Deductions'),
    rows: lines(DEDUCTIONS),
    empty: __('Nothing deducted.'),
    total: __('Deducted'),
    sum: paid(props.record?.[TAKEN]) || '—',
  },
])

const facts = computed(() => {
  const found = [
    {
      field: STRUCTURE,
      label: column(STRUCTURE)?.label || __('Salary structure'),
      text: text(STRUCTURE),
      icon: fieldSpec(column(STRUCTURE)).icon,
    },
    {
      field: PAID_BY,
      label: __('Paid by'),
      text: String(props.record?.[PAID_BY] || ''),
      icon: 'lucide-wallet',
    },
  ]
  return found.filter((one) => one.text).slice(0, FACTS)
})
</script>
