<template>
  <!--
    What is owed, and how late. One component for both sides — `docs/ONEBOOK.md`
    §4 — because ERPNext's receivable and payable reports return the same row
    and which of the two this is arrives as the `screen` it is mounted as.

    A party per line with its money spread across the ageing buckets, and the
    documents behind a line one click away. That is the order somebody reads it
    in: who, then how late, then which invoice.
  -->
  <div class="mx-auto flex w-full max-w-6xl flex-col gap-4 p-5">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div class="flex flex-wrap items-end gap-3">
        <!-- Wrapped rather than given a width of their own: frappe-ui's
             FormControl passes `class` to the control and not to the field, so
             a width on it leaves the label full-bleed and the row stacks. -->
        <div class="w-40">
          <FormControl
            type="date"
            size="sm"
            data-slot="owing-asof"
            :label="__('As at')"
            :model-value="asof || aged.data?.asof || ''"
            @update:model-value="asof = $event || ''"
          />
        </div>
        <!-- A receivables clerk chases from the date the money was promised;
             an auditor sizing a provision reads from the date it was billed. -->
        <div class="w-40">
          <FormControl
            type="select"
            size="sm"
            data-slot="owing-basis"
            :label="__('Age from')"
            :options="bases"
            :model-value="basis"
            @update:model-value="basis = $event"
          />
        </div>
      </div>

      <dl class="flex flex-wrap gap-6" data-slot="owing-totals">
        <div v-for="one in headline" :key="one.key" class="flex flex-col">
          <dt class="text-p-sm text-ink-muted">{{ one.label }}</dt>
          <dd class="text-xl-semibold tabular-nums" :class="one.tone">{{ one.value }}</dd>
        </div>
      </dl>
    </div>

    <Panel pad="none">
      <LoadingText v-if="aged.loading && !aged.data" class="p-6" :text="__('Loading')" />
      <ErrorMessage
        v-else-if="aged.error"
        class="p-6"
        :message="aged.error.messages?.[0] || aged.error"
      />
      <EmptyState
        v-else-if="!parties.length"
        icon="lucide-circle-check"
        :title="__('Nothing outstanding')"
        :message="settled"
      />
      <div v-else class="overflow-x-auto">
        <!-- eslint-disable-next-line vue/no-restricted-html-elements -- an ageing is a matrix of one party against six buckets with a totals row under it, and ListView draws a list of records with columns: it has no row of sums and no second level of rows under one of its own -->
        <table class="w-full text-sm" data-slot="owing">
          <thead>
            <tr class="border-b border-outline-gray-2">
              <th class="px-4 py-2 text-start font-medium text-ink-muted">
                {{ aged.data?.party_kind || __('Party') }}
              </th>
              <th
                v-for="bucket in buckets"
                :key="bucket.key"
                class="px-4 py-2 text-end font-medium whitespace-nowrap"
                :class="TONE[bucket.key] || TONE.later"
              >
                {{ bucket.label }}
              </th>
              <th class="px-4 py-2 text-end font-medium text-ink-muted">{{ __('Total') }}</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="party in parties" :key="party.party || party.party_label">
              <tr
                class="cursor-pointer border-b border-outline-gray-1"
                :class="[HOVER, opened === (party.party || party.party_label) ? SELECTED : '']"
                data-slot="owing-party"
                @click="toggle(party)"
              >
                <td class="w-64 px-4 py-2">
                  <div class="flex min-w-0 flex-col">
                    <span class="truncate text-ink-primary">{{ party.party_label }}</span>
                    <span class="text-sm whitespace-nowrap text-ink-muted">{{ standing(party) }}</span>
                  </div>
                </td>
                <td
                  v-for="(value, at) in party.buckets"
                  :key="at"
                  class="px-4 py-2 text-end tabular-nums whitespace-nowrap"
                  :class="value ? (TONE[buckets[at]?.key] || TONE.later) : TONE.nothing"
                >
                  {{ value ? number(value, 2) : '—' }}
                </td>
                <td class="px-4 py-2 text-end font-medium tabular-nums whitespace-nowrap">
                  {{ money(party.outstanding, party.currency || currency) }}
                </td>
              </tr>
              <!-- The documents behind that line, already in the payload: an
                   ageing is read by opening the one row somebody is about to ring
                   about, and a round trip per expand is a round trip per row. -->
              <tr v-if="opened === (party.party || party.party_label)" data-slot="owing-documents">
                <td :colspan="buckets.length + 2" class="bg-surface-gray-1 px-4 py-2">
                  <ul class="flex flex-col gap-1">
                    <li
                      v-for="row in documentsFor(party)"
                      :key="row.doctype + row.voucher"
                      class="flex items-baseline justify-between gap-3"
                    >
                      <span class="min-w-0 truncate text-ink-secondary">
                        {{ row.voucher }}
                        <span class="text-ink-muted">· {{ row.doctype }}</span>
                        <span v-if="row.project" class="text-ink-muted">· {{ row.project }}</span>
                      </span>
                      <span class="shrink-0 text-p-sm text-ink-muted">{{ lateness(row) }}</span>
                      <span class="shrink-0 tabular-nums text-ink-primary">
                        {{ money(row.outstanding, row.currency || currency) }}
                      </span>
                    </li>
                  </ul>
                </td>
              </tr>
            </template>
          </tbody>
          <tfoot>
            <tr class="border-t border-outline-gray-2 bg-surface-gray-1 font-medium">
              <td class="px-4 py-2 text-ink-primary">{{ __('Everybody') }}</td>
              <td
                v-for="(value, at) in totals"
                :key="at"
                class="px-4 py-2 text-end tabular-nums whitespace-nowrap"
                :class="value ? (TONE[buckets[at]?.key] || TONE.later) : TONE.nothing"
              >
                {{ value ? number(value, 2) : '—' }}
              </td>
              <td class="px-4 py-2 text-end tabular-nums whitespace-nowrap text-ink-primary">
                {{ money(outstanding, currency) }}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </Panel>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

import { ErrorMessage, FormControl, LoadingText } from '@/ui'
import EmptyState from '@/shared/components/EmptyState.vue'
import Panel from '@/shared/components/Panel.vue'
import { useResource } from '@/shared/lib/runtime/resource'
// The two fills, from the one file that decides them — `lib/rowstate.js`.
// `rowState()` itself is not used here: it carries `relative` and an `OPEN`
// leading edge drawn as a `before:` pseudo-element, and a `<tr>` is not a box
// that positions one. A table row that is open is a filled row.
import { HOVER, SELECTED } from '@/shared/lib/rowstate'
import { money, number } from '@/shared/lib/runtime/format'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  spaceCode: { type: String, default: '' },
  screen: { type: String, default: '' },
})

/**
 * The per-column tone, hoisted out of `:class`.
 *
 * `test_design_tokens.py` reads every class name out of the template, and a
 * ternary comparing a string leaves the compared value in front of it as a
 * class that emits no CSS — Statement.vue and Reconcile.vue carry the same
 * maps for the same reason.
 *
 * `range0` is what is not due yet and reads calm; everything after it is late
 * and darkens as it ages. That gradient *is* the screen.
 */
const TONE = {
  range0: 'text-ink-muted',
  range1: 'text-ink-primary',
  range2: 'text-ink-amber-3',
  range3: 'text-ink-amber-3',
  range4: 'text-ink-red-3',
  range5: 'text-ink-red-3',
  later: 'text-ink-red-3',
  nothing: 'text-ink-gray-4',
}

// Which side. The screen's own slug is the kind, so the manifest and the
// endpoint's allowlist are the same two words.
const KINDS = { 'owed-to-us': 'receivable', 'owed-by-us': 'payable' }
const kind = computed(() => KINDS[props.screen] || 'receivable')

const asof = ref('')
const basis = ref('Due Date')
const opened = ref('')

const aged = useResource('oneapp.onebook.owing.owing', {
  params: () => ({ kind: kind.value, asof: asof.value, basis: basis.value }),
  refetch: true,
  immediate: true,
})

const parties = computed(() => aged.data?.parties || [])
const buckets = computed(() => aged.data?.buckets || [])
const totals = computed(() => aged.data?.totals || [])
const currency = computed(() => aged.data?.currency || '')
const outstanding = computed(() => aged.data?.outstanding || 0)
const bases = computed(() => aged.data?.bases || ['Due Date'])

const headline = computed(() => {
  const data = aged.data
  if (!data) return []
  const late = data.late || 0
  return [
    { key: 'all', label: __('Outstanding'),
      value: money(data.outstanding || 0, currency.value), tone: 'text-ink-primary' },
    { key: 'late', label: __('Past due'),
      value: money(late, currency.value),
      tone: late ? TONE.later : 'text-ink-primary' },
  ]
})

const settled = computed(() =>
  kind.value === 'payable'
    ? __('Every bill is settled.')
    : __('Every invoice has been paid.'),
)

// `party` is empty on a document nobody named — a payroll accrual sits on a
// payable account with no supplier — so the label is the key there.
const documentsFor = (party) =>
  (aged.data?.rows || []).filter(
    (one) => (one.party || one.party_label) === (party.party || party.party_label),
  )

/**
 * The line under a party's name.
 *
 * The oldest age only where something is actually late: on a ledger where
 * everything is inside terms it is noise, and "1 days" under a name is the
 * kind of thing somebody notices before they notice the numbers.
 */
const standing = (party) => {
  const open = __('{0} open', [String(party.documents)])
  if (party.oldest <= 0) return open
  const age = party.oldest === 1
    ? __('oldest 1 day')
    : __('oldest {0} days', [String(party.oldest)])
  return `${open} · ${age}`
}

const lateness = (row) => {
  if (row.age === 1) return __('1 day late')
  if (row.age > 0) return __('{0} days late', [String(row.age)])
  if (row.age === -1) return __('due tomorrow')
  if (row.age < 0) return __('due in {0} days', [String(-row.age)])
  return __('due today')
}

const toggle = (party) => {
  const key = party.party || party.party_label
  opened.value = opened.value === key ? '' : key
}
</script>
