<template>
  <!--
    A financial statement: the trial balance, the profit and loss, the balance
    sheet. One component for all three because they are one shape — accounts
    down the side in the chart's own order, a column per period, and the totals
    ERPNext appends. Which of the three is the `screen` this is mounted as,
    which is why there are three keys in the registry and one file here.

    A `component` screen rather than a view type, and the reason is not
    laziness: a view type is an alternate rendering of the rows a screen has
    already narrowed to, and a statement is a different aggregation with its
    own filters over rows no screen lists. `docs/ONEBOOK.md` §1.

    No PageHeader — a screen renders inside the shell's own header, which the
    space and the screen name already fill. The two controls that change what
    is on the page live with the content.
  -->
  <div class="mx-auto flex max-w-4xl flex-col gap-4 p-5">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div class="flex min-w-0 flex-col">
        <p data-slot="statement-company" class="truncate text-base-medium text-ink-primary">
          {{ report.data?.company || '' }}
        </p>
        <!-- What the numbers are of. A statement with no period on it is a
             screenshot somebody will misfile. -->
        <p data-slot="statement-period" class="text-p-sm text-ink-muted">
          {{ caption }}
        </p>
      </div>

      <div class="flex shrink-0 items-center gap-2">
        <!-- The year, and nothing else about the company: one workspace has
             one company (`docs/WORKSPACE-SETTINGS.md`), so offering a company
             picker would be offering a choice of one. -->
        <FormControl
          v-if="years.length > 1"
          type="select"
          size="sm"
          data-slot="statement-year"
          :options="years"
          :model-value="year"
          :aria-label="__('Fiscal year')"
          @update:model-value="pick('year', $event)"
        />
        <!-- Only where the report has periods. A trial balance's columns are
             opening, movement and closing — cutting it monthly would be a
             different report, and ERPNext's own does not offer it either. -->
        <FormControl
          v-if="periods.length"
          type="select"
          size="sm"
          data-slot="statement-periodicity"
          :options="periods"
          :model-value="periodicity"
          :aria-label="__('Periods')"
          @update:model-value="pick('periodicity', $event)"
        />
      </div>
    </div>

    <Panel pad="none">
      <LoadingText v-if="report.loading" class="p-6" />
      <ErrorMessage v-else-if="report.error" :message="report.error.messages?.[0] || report.error" class="p-6" />
      <!--
        A set of books with nothing posted into it. Said plainly rather than as
        an empty table, because the two look identical and mean opposite
        things: one is a workspace that has not started, the other is a screen
        that is broken.
      -->
      <p v-else-if="!rows.length" data-slot="statement-empty" class="p-6 text-sm text-ink-muted">
        {{ __('Nothing has been posted in this period.') }}
      </p>
      <!-- eslint-disable-next-line vue/no-restricted-html-elements -- ListView is a list of records with columns and this is none of those: the rows are an indented tree, some are section gaps, some are totals, and "Total Income (Credit)" is not a document anybody can open. Faking records to satisfy the rule would be worse than the rule; MatrixBody.vue makes the same call. -->
      <table v-else data-slot="statement" class="w-full text-sm">
        <thead>
          <tr class="border-b border-outline-gray-2">
            <th class="px-4 py-2 text-start font-medium text-ink-muted">{{ __('Account') }}</th>
            <th
              v-for="column in columns"
              :key="column.key"
              class="px-4 py-2 text-end font-medium text-ink-muted whitespace-nowrap"
            >
              {{ column.label }}
            </th>
          </tr>
        </thead>
        <tbody>
          <template v-for="(row, at) in rows" :key="at">
            <!-- ERPNext's own section break, and the only thing separating
                 income from expenses on a profit and loss. -->
            <tr v-if="row.kind === 'gap'" data-slot="statement-gap">
              <td :colspan="columns.length + 1" class="h-3" />
            </tr>
            <tr
              v-else
              :data-slot="SLOTS[row.kind] || SLOTS.account"
              class="border-b border-outline-gray-1 last:border-b-0"
              :class="TONE[row.kind] || ''"
            >
              <!-- The indent is the chart's, not ours: it is what makes a
                   statement readable as a tree rather than as a flat list of
                   four hundred accounts with similar names. -->
              <td
                class="px-4 py-1.5 text-ink-primary"
                :style="{ paddingInlineStart: `${16 + row.indent * 16}px` }"
              >
                <span :class="row.is_group ? GROUP : ''">{{ row.label }}</span>
              </td>
              <td
                v-for="(value, column) in row.values"
                :key="column"
                data-slot="statement-value"
                class="px-4 py-1.5 text-end tabular-nums whitespace-nowrap"
                :class="value ? 'text-ink-primary' : 'text-ink-gray-4'"
              >
                {{ value ? money(value, row.currency) : '—' }}
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </Panel>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

import { ErrorMessage, FormControl, LoadingText } from '@/ui'
import Panel from '@/shared/components/Panel.vue'
import { useResource } from '@/shared/lib/runtime/resource'
import { money } from '@/shared/lib/runtime/format'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  spaceCode: { type: String, default: '' },
  screen: { type: String, default: '' },
})

/**
 * The two per-row lookups, hoisted out of `:class` and `:data-slot`.
 *
 * Not tidiness. `test_design_tokens.py` reads every class name out of the
 * template, and a ternary comparing a string puts the compared value in front
 * of it as a class that emits no CSS. The same trap caught `align === 'start'`
 * in `docs/CLEANUP.md` stage 6, and a map is the fix in both places.
 */
const SLOTS = { account: 'statement-row', total: 'statement-total' }
const TONE = { total: 'bg-surface-gray-1 font-medium' }
const GROUP = 'text-ink-secondary'

// Which of the three. The screen's own slug is the kind, so the manifest and
// the endpoint's allowlist are the same three words and a fourth statement is
// a screen plus a row in `REPORTS`.
const kind = computed(() => props.screen || 'trial-balance')

const year = ref('')
const periodicity = ref('Yearly')

// `params` as a getter and `refetch`, which is `useCall`'s own way of saying
// "re-run when these change" — so picking a year or a periodicity needs no
// handler beyond setting the ref, and switching between the three screens
// refetches because `kind` is in here too.
const report = useResource('oneapp.onebook.statements.statement', {
  params: () => ({
    kind: kind.value,
    fiscal_year: year.value,
    periodicity: periodicity.value,
  }),
  refetch: true,
  immediate: true,
})

// The server decides which year and which periodicity it actually used —
// asked for nothing, it answers with the year today is in. Reading them back
// rather than assuming keeps the pickers showing what is on screen.
watch(() => report.data, (data) => {
  if (!data) return
  year.value = data.fiscal_year || ''
  if (data.periodicity) periodicity.value = data.periodicity
})

function pick(what, value) {
  if (what === 'year') year.value = value
  else periodicity.value = value
}

const rows = computed(() => report.data?.rows || [])
const columns = computed(() => report.data?.columns || [])
const years = computed(() => report.data?.years || [])
const periods = computed(() => report.data?.periods || [])

const caption = computed(() => {
  const data = report.data
  if (!data) return ''
  return data.periodicity
    ? `${data.fiscal_year} · ${__(data.periodicity)}`
    : data.fiscal_year
})
</script>
