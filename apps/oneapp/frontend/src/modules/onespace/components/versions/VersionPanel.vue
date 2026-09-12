<template>
  <!--
    Earlier drafts of one file, whether that file is a workbook or a document.

    One panel for both, because `shared/versions.py` is one module for
    both: the rows are the same five columns and the only thing that differs is
    which store the payload goes back to. `kind` carries that, and nothing else
    in here knows what a version contains.

    Grouped by the server against the reader's own midnight. Doing it here
    would mean a panel left open overnight regrouping itself under the cursor.
  -->
  <aside
    class="flex w-80 shrink-0 flex-col border-s border-outline-gray-1 bg-surface-base"
    :aria-label="__('Version history')"
  >
    <div class="flex shrink-0 items-center justify-between gap-2 border-b border-outline-gray-1 px-4 py-3">
      <p class="text-p-base font-medium text-ink-primary">{{ __('Version history') }}</p>
      <Button
        variant="ghost"
        icon="lucide-x"
        :label="__('Close history')"
        :tooltip="__('Close')"
        @click="emit('close')"
      />
    </div>

    <div class="shrink-0 border-b border-outline-gray-1 p-3">
      <Button
        class="w-full"
        icon-left="lucide-bookmark-plus"
        :label="__('Save this version')"
        :loading="saving"
        :disabled="!canWrite"
        @click="askFor(null)"
      />
      <p v-if="error" class="mt-2 text-p-xs text-ink-red-3">{{ error }}</p>
    </div>

    <FadedScroll class="min-h-0 flex-1 p-3">
      <!--
        The frame is `DataList` — §B1. A row here is a *day*, not a version:
        the grouping is the server's and the section is what this panel draws
        per row.
      -->
      <DataList
        :source="source"
        :skeleton="6"
        skeleton-class="h-10 w-full"
        body-class="gap-3"
      >
        <template #row="{ row: group }">
        <section class="flex flex-col gap-1">
          <p class="px-1 text-p-xs font-medium uppercase tracking-wide text-ink-muted">
            {{ group.label }}
          </p>
          <!--
            The row is a container rather than the control, which is the one
            shape `<Row>` cannot collapse: a menu button inside a `<button>`
            is invalid markup, so the version stays a `Button` and the menu
            stays beside it. What `<Row>` brings is the leading edge on the
            current version and the pad, both of which were spelled here.
          -->
          <Row
            v-for="one in group.versions"
            :key="one.name"
            edge="rounded"
            pad="tight"
            align="start"
            :open="one.current"
          >
            <Button
              variant="ghost"
              class="!h-auto w-full !justify-start !px-2 !py-1.5"
              :label="__('Look at {0}', [named(one)])"
              @click="emit('preview', one)"
            >
              <span class="w-full min-w-0 text-start">
                <span class="flex items-center gap-1 truncate text-sm text-ink-primary">
                  {{ named(one) }}
                  <Badge v-if="one.current" theme="green" :label="__('Current')" size="sm" />
                </span>
                <span class="block truncate text-xs font-normal text-ink-muted">
                  {{ said(one) }}
                </span>
              </span>
            </Button>
            <template #trail>
              <Dropdown :options="menu(one)">
                <Button
                  variant="ghost"
                  icon="lucide-more-horizontal"
                  :label="__('What to do with this version')"
                  :tooltip="__('What to do with this version')"
                />
              </Dropdown>
            </template>
          </Row>
        </section>
        </template>
      </DataList>
    </FadedScroll>
  </aside>

  <!-- One dialog for both, because naming this moment and naming an older one
       ask the same question and take the same answer. `renaming` is which. -->
  <Dialog v-model="naming" :title="renaming ? __('Name this version') : __('Save this version')">
    <template #default>
      <FormControl
        v-model="title"
        type="text"
        :label="__('What this version is')"
        :placeholder="__('Signed off by the client')"
        @keyup.enter="keep"
      />
      <p class="mt-2 text-p-xs text-ink-muted">
        {{ __('A named version is never thinned out. The automatic ones are, once they are old enough to be too many.') }}
      </p>
    </template>
    <template #actions>
      <Button variant="solid" :label="__('Save')" :loading="saving" @click="keep" />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

import { Badge, Button, Dialog, Dropdown, FormControl } from '@/ui'
import DataList from '@/shared/components/DataList.vue'
import FadedScroll from '@/shared/components/FadedScroll.vue'
import Row from '@/shared/components/Row.vue'
import { staticSource } from '@/shared/lib/list/source'
import { useSaving } from '@/shared/composables/useSaving'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'
import { ago, moment } from '@/shared/lib/runtime/format'

const props = defineProps({
  file: { type: String, required: true },
  // 'Sheet' or 'Doc' — which store a restore writes back to.
  kind: { type: String, required: true },
  canWrite: { type: Boolean, default: false },
  // Bumped by the host after it saves, so the list follows the work rather
  // than needing a refresh button beside it.
  revision: { type: Number, default: 0 },
})

const emit = defineEmits(['close', 'preview', 'restored'])

const groups = ref([])
const naming = ref(false)
const renaming = ref(null)
const title = ref('')

const { saving, error, attempt } = useSaving()
const { saving: loading, attempt: attemptLoad } = useSaving(error)

/**
 * The days this file has versions on, and what this panel can do with them
 * — §B1.
 *
 * Nothing but draw them. The order is the server's and it is the only order
 * a history has; searching a list whose rows are dates would be searching for
 * a date, which the grouping already answers.
 */
const source = computed(() => staticSource({
  rows: groups.value,
  key: (group) => group.label,
  // The rows are fetched, not held: without this the frame would read the
  // empty array it starts with as "no versions" and say so for as long as the
  // read takes.
  loading: loading.value,
  empty: {
    icon: 'lucide-history',
    title: __('No earlier versions yet'),
    description: __('One is kept the first time this is saved, and every few minutes of work after that.'),
  },
}))

// What a version is called. A named one says its name; an unnamed one says
// when it was taken — here rather than stored on the row, because a stored
// timestamp is one the reader's browser can never convert into their own
// timezone or their workspace's date format. See `docs/UNIFICATION.md` §D1.
const named = (one) => one.title || moment(one.at)

const said = (one) => [
  one.by,
  one.at ? ago(one.at) : '',
  one.saves ? __('{0} changes', [one.saves]) : '',
].filter(Boolean).join(' · ')

async function load() {
  const answer = await attemptLoad(() => workspace.fileHistory(props.file, props.kind))
  groups.value = answer?.groups || []
}

function askFor(one) {
  renaming.value = one
  title.value = one?.title || ''
  naming.value = true
}

async function keep() {
  const one = renaming.value
  const named = await attempt(async () => {
    if (one) await workspace.fileNameVersion(one.name, props.kind, title.value)
    else await workspace.fileKeepVersion(props.file, props.kind, title.value)
    return true
  })
  if (!named) return
  naming.value = false
  renaming.value = null
  title.value = ''
  await load()
}

function menu(one) {
  return [
    { label: __('Preview'), icon: 'lucide-eye', onClick: () => emit('preview', one) },
    {
      label: __('Restore this version'),
      icon: 'lucide-rotate-ccw',
      condition: () => props.canWrite,
      onClick: async () => {
        await attempt(() => workspace.fileRestoreVersion(one.name, props.kind))
        emit('restored', one)
        await load()
      },
    },
    {
      // Naming an automatic version is also what keeps it: the pruner only
      // ever reaches the ones nobody named.
      label: one.manual ? __('Rename') : __('Keep this one'),
      icon: 'lucide-bookmark',
      condition: () => props.canWrite,
      onClick: () => askFor(one),
    },
    {
      label: __('Remove'),
      icon: 'lucide-trash-2',
      condition: () => props.canWrite && one.manual,
      onClick: async () => {
        await attempt(() => workspace.fileForgetVersion(one.name, props.kind))
        await load()
      },
    },
  ]
}

watch(() => [props.file, props.revision], load, { immediate: true })
</script>
