<template>
  <!--
    What is stored, and where the weight is.

    The quota was enforced at upload time and shown nowhere, which is the worst
    of both: a refusal with no way to have seen it coming. So this answers the
    three questions somebody asks in the order they ask them — how much is left,
    what sort of thing is using it, and which file in particular.

    The last one is the only actionable answer. "Photographs" is not something a
    person can do anything about; "this 24 MB bitmap nobody has opened since
    March" is.
  -->
  <SettingsHeader
    title="Storage"
    description="What this workspace is keeping, and how much room is left."
    :class="PANEL_HEADER"
  >
    <template #actions>
      <Button icon-left="lucide-folder" label="Open the files" @click="toDrive" />
    </template>
  </SettingsHeader>

  <SettingsBody :class="PANEL_BODY">
    <LoadingText v-if="loading" class="py-8" text="Loading" />

    <Alert v-else-if="error" theme="red" title="Storage could not be measured">
      <template #description>{{ error }}</template>
    </Alert>

    <div v-else class="flex min-w-0 flex-col gap-6 py-4">
      <UsageBar
        v-if="storage.workspace"
        label="Storage"
        :usage="storage.workspace"
        format="bytes"
      />

      <!--
        Two figures, and the screen says why they differ. The meter is the
        workspace's real usage, off the control plane, and counts files nobody
        in particular can open; the breakdown is what *this reader* may see. A
        breakdown that summed to the meter would be a breakdown that leaked
        what it could not show.
      -->
      <p class="text-p-xs text-ink-gray-5">
        The breakdown below covers the {{ storage.files }}
        {{ storage.files === 1 ? 'file' : 'files' }} you can see, which is
        {{ bytes(storage.visible) }}. The meter above is the whole workspace,
        including files on records you cannot open.
      </p>

      <section v-if="storage.by_kind?.length" class="flex min-w-0 flex-col gap-2">
        <h3 class="text-p-sm font-medium text-ink-gray-8">By kind</h3>
        <div
          v-for="row in storage.by_kind"
          :key="row.kind"
          data-slot="storage-kind"
          class="flex min-w-0 items-center gap-3"
        >
          <Icon :name="ICONS[row.kind] || ICONS.Other" class="size-4 shrink-0 text-ink-gray-5" />
          <span class="w-24 shrink-0 text-p-sm text-ink-gray-7">{{ row.kind }}</span>
          <!--
            Against the largest kind and not against the quota: the shape worth
            seeing here is which of these is the big one, and every bar being 2%
            of a 20 GB plan shows nothing at all.

            Wrapped in a plain div because the flex maths has to happen on
            something that will shrink. A component root with its own width is a
            flex item that refuses to, and the panel grows to fit it — which is
            how a settings dialog ends up wider than itself with its numbers
            clipped off the right edge.
          -->
          <div class="min-w-0 flex-1">
            <Progress class="w-full" size="sm" :value="share(row.bytes)" />
          </div>
          <span class="w-20 shrink-0 text-right text-p-sm tabular-nums text-ink-gray-6">
            {{ row.label }}
          </span>
        </div>
      </section>

      <section v-if="storage.by_folder?.length" class="flex min-w-0 flex-col gap-2">
        <h3 class="text-p-sm font-medium text-ink-gray-8">By folder</h3>
        <div
          v-for="row in storage.by_folder"
          :key="row.folder"
          data-slot="storage-folder"
          class="flex min-w-0 items-center gap-3"
        >
          <Icon name="lucide-folder" class="size-4 shrink-0 text-ink-gray-5" />
          <span class="min-w-0 flex-1 truncate text-p-sm text-ink-gray-7">{{ row.folder }}</span>
          <span class="w-20 shrink-0 text-right text-p-sm tabular-nums text-ink-gray-6">
            {{ row.label }}
          </span>
        </div>
      </section>

      <section v-if="storage.biggest?.length" class="flex min-w-0 flex-col gap-2">
        <h3 class="text-p-sm font-medium text-ink-gray-8">The biggest</h3>
        <div
          v-for="row in storage.biggest"
          :key="row.name"
          data-slot="storage-biggest"
          class="flex min-w-0 items-center gap-3"
        >
          <Icon :name="ICONS[row.kind] || ICONS.Other" class="size-4 shrink-0 text-ink-gray-5" />
          <span class="min-w-0 flex-1 truncate text-p-sm text-ink-gray-7">
            {{ row.file_name }}
          </span>
          <span class="shrink-0 text-p-xs text-ink-gray-5">{{ row.folder }}</span>
          <span class="w-20 shrink-0 text-right text-p-sm tabular-nums text-ink-gray-6">
            {{ row.label }}
          </span>
        </div>
      </section>

      <EmptyState
        v-if="!storage.files"
        icon="lucide-hard-drive"
        title="Nothing stored yet"
        description="Files uploaded anywhere in this workspace show up here."
      />
    </div>
  </SettingsBody>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Alert,
  Button,
  Icon,
  LoadingText,
  Progress,
  SettingsBody,
  SettingsHeader,
} from '@/ui'
import EmptyState from '../EmptyState.vue'
import UsageBar from '../UsageBar.vue'
import { PANEL_BODY, PANEL_HEADER } from './geometry'
import { workspace } from '../../lib/workspace'
import { settings } from '../../lib/settings'
import { errorText } from '../../lib/errors'

// The same glyphs the Drive draws, because they are the same kinds.
const ICONS = {
  Folder: 'lucide-folder',
  Image: 'lucide-image',
  PDF: 'lucide-file-text',
  Video: 'lucide-video',
  Audio: 'lucide-music',
  Document: 'lucide-file',
  Other: 'lucide-file-question',
}

const router = useRouter()

const storage = ref({})
const loading = ref(true)
const error = ref('')

const largest = computed(() =>
  Math.max(1, ...(storage.value.by_kind || []).map((one) => one.bytes || 0)),
)

const share = (size) => Math.round(((size || 0) / largest.value) * 100)

const bytes = (size) => {
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let value = size || 0
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  return `${value < 10 && unit ? value.toFixed(1) : Math.round(value)} ${units[unit]}`
}

const toDrive = () => {
  settings.open = false
  router.push({ name: 'Drive' })
}

onMounted(async () => {
  try {
    storage.value = (await workspace.driveStorage()) || {}
  } catch (raised) {
    error.value = errorText(raised)
  } finally {
    loading.value = false
  }
})
</script>
