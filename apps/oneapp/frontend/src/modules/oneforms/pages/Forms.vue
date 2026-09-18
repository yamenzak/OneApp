<template>
  <!--
    OneForms: the doors this workspace has opened.

    `docs/ONEFORMS.md`. A form is a page somebody outside can reach that writes
    into a doctype — a lead, an application, a supplier's own bank details —
    and until this module the product had none, so everything that arrived from
    outside arrived as a person re-keying it.

    It is a service rather than a space because a form is not a department:
    OneCRM wants one about leads and OnePeople about applicants, and neither of
    them owns the idea. So this is a window you keep beside what you are doing,
    like OneTask, with a route for when you want the whole page.

    **What it can be made over is the whole of the security**, and it is why
    the New control is a picker rather than a text box: the list is every
    doctype a space you hold already shows you, and nothing else on the site.
  -->
  <PageHeader v-if="!inWindow">
    <Trail :items="crumbs" />
  </PageHeader>

  <div
    class="mx-auto flex min-h-0 w-full max-w-3xl flex-1 flex-col gap-3 p-4"
    data-slot="forms-service"
  >
    <!--
      Making one, at the top and always there — the same argument OneTask's
      capture box makes. A New button that opened a dialog to ask one question
      would be two presses for a list whose whole content is things somebody
      made.
    -->
    <div class="flex shrink-0 flex-wrap items-center gap-2">
      <!-- Searchable rather than a plain Select: a workspace with every space
           enabled offers a hundred-odd doctypes, and a list that long is one
           people scroll past the thing they wanted. -->
      <Combobox
        v-model="over"
        class="min-w-48 flex-1"
        :options="options"
        :placeholder="__('A form over…')"
        data-slot="forms-over"
      />
      <Button
        variant="solid"
        icon-left="lucide-plus"
        :label="__('New form')"
        :disabled="!over"
        :loading="making"
        data-slot="forms-new"
        @click="make"
      />
    </div>

    <DataList
      :source="source"
      class="min-h-0 flex-1 overflow-y-auto"
      :skeleton="3"
      skeleton-class="h-16 w-full"
      body-class="gap-2"
    >
      <template #empty>
        <EmptyState
          icon="lucide-inbox"
          :title="__('No forms yet')"
          :description="offerable.length
            ? __('A form is a page somebody outside can fill in, which lands as a record here.')
            : __('A form is made over something one of your spaces already shows you.')"
        />
      </template>

      <template #row="{ row }">
        <Panel :data-slot="`form-${row.name}`">
          <div class="flex flex-wrap items-center gap-3">
            <Icon
              :name="row.published ? 'lucide-globe' : 'lucide-inbox'"
              class="size-4 shrink-0 text-ink-muted"
              :aria-hidden="true"
            />
            <router-link
              :to="{ name: 'FormBuilder', params: { name: row.name } }"
              class="min-w-0 flex-1"
              :class="LINK"
              data-slot="form-open"
            >
              <span class="block truncate text-sm text-ink-primary">{{ row.title }}</span>
              <span class="block truncate text-xs text-ink-muted">{{ said(row) }}</span>
            </router-link>

            <!-- What the form knows about itself. `responses` is stage 12's:
                 one hidden column on the doctype it is over, because a form
                 that cannot say what it collected is not a form anybody runs a
                 business on. The invitations are beside it because they are a
                 different question — how many were asked, not how many came. -->
            <span class="shrink-0 text-xs text-ink-muted tabular-nums">
              {{ __('{0} in', [row.responses || 0]) }}
              <template v-if="row.invited">
                · {{ __('{0} of {1} answered', [row.answered, row.invited]) }}
              </template>
            </span>

            <Badge
              :theme="row.published ? 'green' : 'gray'"
              variant="subtle"
              :label="row.published ? __('Live') : __('Draft')"
            />

            <Button
              v-if="row.place && row.place.space"
              variant="ghost"
              icon="lucide-arrow-right"
              :label="__('What it collected')"
              :tooltip="__('What it collected, in {0}', [row.place.label])"
              data-slot="form-collected"
              @click="collected(row)"
            />

            <Button
              :label="row.published ? __('Take down') : __('Publish')"
              :loading="working === row.name"
              data-slot="form-publish"
              @click="publish(row)"
            />
            <Button
              variant="ghost"
              icon="lucide-trash-2"
              :label="__('Delete for ever')"
              :tooltip="__('Delete for ever')"
              data-slot="form-forget"
              @click="ask(row)"
            />
          </div>
        </Panel>
      </template>
    </DataList>
  </div>

  <Dialog v-model="asking" :title="__('Delete this form for ever?')">
    <p class="text-p-base text-ink-secondary">
      {{ __('The page stops answering. What it already collected stays where it is.') }}
    </p>
    <template #actions>
      <Button :label="__('Never mind')" @click="asking = false" />
      <Button variant="solid" theme="red" :label="__('Delete for ever')" @click="forget" />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, inject, onMounted, ref, unref } from 'vue'
import { useRouter } from 'vue-router'

import { Badge, Button, Combobox, Dialog, Icon, PageHeader } from '@/ui'

import DataList from '@/shared/components/DataList.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import Panel from '@/shared/components/Panel.vue'
import Trail from '@/shared/components/Trail.vue'
import { useCrumbs } from '@/shared/composables/useCrumbs'
import { staticSource } from '@/shared/lib/list/source'
import { workspace } from '@/shared/lib/workspace'
import { WINDOW_BAR } from '@/modules/onespace/lib/desk/windows'
import { notifyError } from '@/shared/lib/runtime/notify'
import { nameOf } from '@/shared/lib/brand/naming'
import { NARROW } from '@/modules/onespace/lib/screen/narrowing'
import { __ } from '@/shared/lib/runtime/translate'

//: Hoisted, because a string compared or bound inside a `:class` is a class
//: name Tailwind's JIT never sees.
const LINK = 'hover:underline'

const router = useRouter()
const rows = ref([])
const offerable = ref([])
const loading = ref(false)
const making = ref(false)
const working = ref('')
const over = ref('')
const asking = ref(false)
const pending = ref(null)

const bar = inject(WINDOW_BAR, null)
const mounted = ref(false)
const inWindow = computed(() => (mounted.value ? unref(bar) || '' : ''))

//: The column `oneforms/counting.py` stamps on whatever a form makes. Named
//: here as well because the link is built in the browser; the server builds
//: the same one in `counting.where` for anything that is not a router push.
const MARK = 'custom_web_form'

// The mark's own name, never typed — `MARKS[id].name` is the one place a
// product name is written down.
const crumbs = useCrumbs({ label: nameOf('oneforms'), route: { name: 'Forms' } })

const source = computed(() =>
  staticSource({ rows: rows.value, key: (row) => row.name, loading: loading.value }),
)

/** What a doctype reads as in the picker: the thing, and where it lives. */
const options = computed(() =>
  offerable.value.map((one) => ({
    label: `${one.label} · ${one.space_label}`,
    value: one.doctype,
  })),
)

/** The line under a form's name: what it makes, and who may reach it. */
const said = (row) => {
  const who = row.anonymous
    ? __('Anyone')
    : row.key_required
      ? __('By invitation')
      : __('Signed in')
  return [row.doc_type, who, `/${row.route}`].filter(Boolean).join(' · ')
}

/**
 * What came in — the space's own screen, narrowed to this form.
 *
 * Not a responses table. The screen has views, actions and columns somebody
 * already knows, and `narrow` is how a URL asks one for a filter — the same
 * parameter a record's tab uses. `oneforms/counting.py` writes the link.
 */
const collected = (row) =>
  router.push({
    name: 'Screen',
    params: { spaceCode: row.place.space },
    query: { screen: row.place.screen, [NARROW]: `${MARK}:${row.name}` },
  })

const read = async () => {
  loading.value = true
  try {
    const answer = await workspace.formsMine()
    rows.value = answer?.rows || []
    offerable.value = answer?.offerable || []
  } catch (error) {
    notifyError(error)
  } finally {
    loading.value = false
  }
}

const make = async () => {
  if (!over.value) return
  making.value = true
  try {
    // The value rather than the option: `Combobox` hands back whichever shape
    // it was given, and the server takes a doctype name.
    await workspace.formMake(over.value?.value || over.value, '')
    over.value = ''
    await read()
  } finally {
    making.value = false
  }
}

const publish = async (row) => {
  working.value = row.name
  try {
    await workspace.formPublish(row.name, !row.published)
    await read()
  } finally {
    working.value = ''
  }
}

const ask = (row) => {
  pending.value = row
  asking.value = true
}

const forget = async () => {
  asking.value = false
  const row = pending.value
  if (!row) return
  await workspace.formForget(row.name)
  await read()
}

onMounted(() => {
  mounted.value = true
  read()
})
</script>
