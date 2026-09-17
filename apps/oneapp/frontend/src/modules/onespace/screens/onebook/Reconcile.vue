<template>
  <!--
    The bank feed, turned into a reconciliation.

    Two lists side by side, and that is the whole shape: the statement on the
    left, and on the right what the books think the selected line is — ranked,
    because a bank line carries a date, an amount, a reference and sometimes a
    name, and a payment carries the same four with none of them guaranteed to
    agree. `oneapp/onebook/reconcile.py` has the argument for calling ERPNext's
    ranking rather than writing a second opinion about it.

    A `component` screen rather than a view type, and more clearly so than the
    statements: the right-hand list is a function of the row selected in the
    left-hand one, which is not a rendering of rows a screen narrowed to.
  -->
  <div class="flex flex-col gap-4 p-5">
    <!-- What the account is and what it says. The three numbers are the
         comparison a reconciliation *is*: what the books think is there, what
         the statement moved, and how much of it is still unaccounted for. -->
    <Panel ground="sunken" pad="loose" data-slot="reconcile-band">
      <div class="flex flex-wrap items-end justify-between gap-4">
        <div class="flex flex-wrap items-end gap-3">
          <FormControl
            v-if="accountOptions.length > 1"
            type="select"
            size="sm"
            data-slot="reconcile-account"
            :label="__('Account')"
            :options="accountOptions"
            :model-value="account"
            @update:model-value="account = $event"
          />
          <p v-else class="text-base-medium text-ink-primary" data-slot="reconcile-account">
            {{ accountOptions[0]?.label || __('No bank account yet') }}
          </p>
          <FormControl
            type="date"
            size="sm"
            data-slot="reconcile-since"
            :label="__('From')"
            :model-value="since"
            @update:model-value="since = $event || ''"
          />
          <FormControl
            type="date"
            size="sm"
            data-slot="reconcile-until"
            :label="__('To')"
            :model-value="until"
            @update:model-value="until = $event || ''"
          />
          <Checkbox
            :model-value="settled"
            :label="__('Show what is done')"
            data-slot="reconcile-settled"
            @update:model-value="settled = Boolean($event)"
          />
        </div>

        <dl class="flex flex-wrap gap-6" data-slot="reconcile-totals">
          <div v-for="one in totals" :key="one.key" class="flex flex-col">
            <dt class="text-p-sm text-ink-muted">{{ one.label }}</dt>
            <dd class="text-base-medium tabular-nums text-ink-primary">{{ one.value }}</dd>
          </div>
        </dl>
      </div>
    </Panel>

    <div class="grid gap-4 lg:grid-cols-2">
      <!-- The statement. -->
      <Panel pad="none" data-slot="reconcile-feed">
        <LoadingText v-if="feed.loading && !feed.data" class="p-6" :text="__('Loading')" />
        <ErrorMessage
          v-else-if="feed.error"
          class="p-6"
          :message="feed.error.messages?.[0] || feed.error"
        />
        <EmptyState
          v-else-if="!lines.length"
          icon="lucide-landmark"
          :title="__('Nothing left on this statement')"
          :message="__('Every line in this range has been accounted for.')"
        />
        <ul v-else class="divide-y divide-outline-gray-1">
          <li v-for="row in lines" :key="row.name">
            <!-- eslint-disable-next-line vue/no-restricted-html-elements -- a row that selects rather than navigates: <Button> is a control with a label and this is a two-line record summary, which is what ListView draws and ListView cannot host the open state this pane is entirely about -->
            <button
              type="button"
              class="flex w-full items-start gap-3 px-4 py-3 text-start"
              :class="rowState({ open: row.name === chosen })"
              :aria-current="row.name === chosen ? 'true' : undefined"
              data-slot="reconcile-line"
              @click="chosen = row.name"
            >
              <div class="flex min-w-0 flex-1 flex-col">
                <span class="truncate text-sm text-ink-primary">
                  {{ row.description || __('No description') }}
                </span>
                <span class="text-p-sm text-ink-muted">
                  {{ row.date }}<template v-if="row.reference"> · {{ row.reference }}</template>
                </span>
              </div>
              <div class="flex shrink-0 flex-col items-end">
                <span class="text-sm tabular-nums" :class="WAY[row.direction] || ''">
                  {{ sign(row) }}{{ money(row.amount, row.currency) }}
                </span>
                <span v-if="row.allocated" class="text-p-sm text-ink-muted">
                  {{ __('{0} matched', [money(row.allocated, row.currency)]) }}
                </span>
              </div>
            </button>
          </li>
        </ul>
      </Panel>

      <!-- And what it could be. -->
      <Panel pad="none" data-slot="reconcile-matches">
        <EmptyState
          v-if="!chosen"
          icon="lucide-git-compare"
          :title="__('Pick a line')"
          :message="__('Choose something on the statement and this is what the books think it is.')"
        />
        <LoadingText v-else-if="found.loading && !found.data" class="p-6" :text="__('Looking')" />
        <ErrorMessage
          v-else-if="found.error"
          class="p-6"
          :message="found.error.messages?.[0] || found.error"
        />
        <template v-else>
          <div class="flex items-center justify-between gap-3 border-b border-outline-gray-1 px-4 py-3">
            <p class="text-sm text-ink-secondary">{{ standing }}</p>
            <Checkbox
              v-if="!tied.length"
              :model-value="exact"
              :label="__('Exact amounts only')"
              data-slot="reconcile-exact"
              @update:model-value="exact = Boolean($event)"
            />
          </div>

          <!-- Already matched: what to, and the way back. -->
          <template v-if="tied.length">
            <ul class="divide-y divide-outline-gray-1">
              <li
                v-for="one in tied"
                :key="one.doctype + one.name"
                class="flex items-center justify-between gap-3 px-4 py-3"
                data-slot="reconcile-tied"
              >
                <div class="flex min-w-0 flex-col">
                  <span class="truncate text-sm text-ink-primary">{{ one.name }}</span>
                  <span class="text-p-sm text-ink-muted">{{ one.doctype }}</span>
                </div>
                <span class="shrink-0 text-sm tabular-nums text-ink-primary">
                  {{ money(one.amount, line?.currency) }}
                </span>
              </li>
            </ul>
            <div class="flex justify-end px-4 py-3">
              <Button
                :label="__('Unmatch')"
                :loading="working"
                data-slot="reconcile-unmatch"
                @click="undo"
              />
            </div>
          </template>

          <!-- Or not yet: the ranking. -->
          <EmptyState
            v-else-if="!candidates.length"
            icon="lucide-search"
            :title="__('Nothing in the books looks like this')"
            :message="__('A bank charge or a transfer nobody recorded. Raise it in the ledger and come back.')"
          />
          <template v-else>
            <ul class="divide-y divide-outline-gray-1">
              <li
                v-for="one in candidates"
                :key="one.doctype + one.name"
                class="flex items-start justify-between gap-3 px-4 py-3"
                data-slot="reconcile-candidate"
              >
                <Checkbox
                  v-model="one.ticked"
                  :label="one.name"
                />
                <div class="flex shrink-0 flex-col items-end">
                  <span class="text-sm tabular-nums text-ink-primary">
                    {{ money(one.amount, one.currency) }}
                  </span>
                  <span class="text-p-sm text-ink-muted">
                    {{ one.doctype }}<template v-if="one.reference"> · {{ one.reference }}</template>
                  </span>
                  <!-- How much of it agreed. ERPNext counts the amount, the
                       reference and the party and adds one, so four is
                       everything and one is "same direction, some amount". -->
                  <span class="text-p-sm" :class="STRENGTH[one.rank] || STRENGTH.weak">
                    {{ strength(one.rank) }}
                  </span>
                </div>
              </li>
            </ul>
            <div class="flex justify-end px-4 py-3">
              <Button
                variant="solid"
                :label="__('This is it')"
                :loading="working"
                :disabled="!ticked.length"
                data-slot="reconcile-match"
                @click="commit"
              />
            </div>
          </template>
        </template>
      </Panel>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

import { Button, Checkbox, ErrorMessage, FormControl, LoadingText } from '@/ui'
import EmptyState from '@/shared/components/EmptyState.vue'
import Panel from '@/shared/components/Panel.vue'
import { callMethod, useResource } from '@/shared/lib/runtime/resource'
import { rowState } from '@/shared/lib/rowstate'
import { money } from '@/shared/lib/runtime/format'
import { notifyError, notifySuccess } from '@/shared/lib/runtime/notify'
import { __ } from '@/shared/lib/runtime/translate'

defineProps({
  spaceCode: { type: String, default: '' },
  screen: { type: String, default: '' },
})

/**
 * The per-row lookups, hoisted out of `:class`.
 *
 * `test_design_tokens.py` reads every class name out of the template, and a
 * ternary comparing a string puts the compared value in front of it as a class
 * that emits no CSS. Statement.vue has the same maps for the same reason.
 *
 * The selected line's own treatment is not here: it is `rowState({ open })`,
 * which is the leading edge every list in this product uses for "the one open
 * in the pane beside it" — `lib/rowstate.js`, and `docs/UNIFICATION.md` §B4.
 */
const WAY = { in: 'text-ink-green-3', out: 'text-ink-primary' }
const STRENGTH = {
  4: 'text-ink-green-3',
  3: 'text-ink-green-3',
  2: 'text-ink-amber-3',
  weak: 'text-ink-muted',
}

const account = ref('')
const since = ref('')
const until = ref('')
const settled = ref(false)
const exact = ref(false)
const chosen = ref('')
const working = ref(false)

const where = useResource('oneapp.onebook.reconcile.accounts', { immediate: true })

const accountOptions = computed(() =>
  (where.data?.accounts || []).map((one) => ({
    label: one.account_name || one.name, value: one.name,
  })),
)

// The first account, chosen for them: this screen cannot ask anything until it
// has one, and a picker with one option is a question with one answer.
watch(() => where.data, (data) => {
  if (!account.value) account.value = data?.accounts?.[0]?.name || ''
})

const feed = useResource('oneapp.onebook.reconcile.feed', {
  params: () => ({
    bank_account: account.value,
    since: since.value,
    until: until.value,
    settled: settled.value ? 1 : 0,
  }),
  // Not `refetch`, which would re-ask on every keystroke in a date box *and*
  // once more from the watcher below. One trigger: the watcher.
  //
  // And nothing to ask until an account is picked — asking anyway is a 417 on
  // the first paint of every workspace that has not set one up.
  immediate: false,
})

watch([account, since, until, settled], () => {
  if (account.value) feed.reload()
}, { immediate: true })

const lines = computed(() => feed.data?.rows || [])
const line = computed(() => lines.value.find((one) => one.name === chosen.value) || null)

// A line that is no longer on the list — matched, and the list has refreshed
// without it — is not a line this pane can be about.
watch(lines, (rows) => {
  if (chosen.value && !rows.some((one) => one.name === chosen.value)) chosen.value = ''
})

const found = useResource('oneapp.onebook.reconcile.matches', {
  params: () => ({
    transaction: chosen.value,
    since: since.value,
    until: until.value,
    exact: exact.value ? 1 : 0,
  }),
  immediate: false,
})

watch([chosen, exact], () => {
  candidates.value = []
  if (chosen.value) found.reload()
})

// A fresh object per row, with the tick on it — the controls write into these,
// so reusing the server's dicts would make a re-ask a silent undo.
const candidates = ref([])
watch(() => found.data, (data) => {
  candidates.value = (data?.matches || []).map((one) => ({ ...one, ticked: false }))
})

const tied = computed(() => found.data?.tied || [])
const ticked = computed(() => candidates.value.filter((one) => one.ticked))

const totals = computed(() => {
  const data = feed.data
  if (!data) return []
  const currency = data.account?.currency || lines.value[0]?.currency || ''
  return [
    { key: 'balance', label: __('In the books'),
      value: data.balance == null ? '—' : money(data.balance, currency) },
    { key: 'movement', label: __('The statement moved'),
      value: money(data.movement, currency) },
    { key: 'outstanding', label: __('Not accounted for'),
      value: money(data.outstanding, currency) },
  ]
})

const standing = computed(() => {
  if (!line.value) return ''
  if (tied.value.length) return __('Matched. This is what it was settled against.')
  if (!candidates.value.length) return __('No candidate in these books.')
  return __('Best match first.')
})

const sign = (one) => (one.direction === 'out' ? '−' : '')

// ERPNext's rank counts the amount, the reference and the party and adds one.
const strength = (rank) => {
  if (rank >= 3) return __('Amount and reference agree')
  if (rank === 2) return __('One thing agrees')
  return __('Same direction only')
}

const commit = async () => {
  working.value = true
  try {
    const answer = await callMethod('oneapp.onebook.reconcile.match', {
      transaction: chosen.value,
      vouchers: JSON.stringify(
        ticked.value.map((one) => ({ doctype: one.doctype, name: one.name })),
      ),
    }, { silent: true })
    notifySuccess(__('Matched against {0}.', [String(answer?.count ?? 0)]))
    feed.reload()
    found.reload()
  } catch (raised) {
    notifyError(raised)
  } finally {
    working.value = false
  }
}

const undo = async () => {
  working.value = true
  try {
    await callMethod('oneapp.onebook.reconcile.unmatch',
                     { transaction: chosen.value }, { silent: true })
    notifySuccess(__('Unmatched.'))
    feed.reload()
    found.reload()
  } catch (raised) {
    notifyError(raised)
  } finally {
    working.value = false
  }
}
</script>
