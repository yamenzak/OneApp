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
    :title="__('Storage')"
    :description="__('What this workspace is keeping, and how much room is left.')"
    :class="PANEL_HEADER"
  >
    <template #actions>
      <Button icon-left="lucide-folder" :label="__('Open the files')" @click="toDrive" />
    </template>
  </SettingsHeader>

  <SettingsBody :class="PANEL_BODY">
    <LoadingText v-if="loading" class="py-8" :text="__('Loading')" />

    <Alert v-else-if="error" theme="red" :title="__('Storage could not be measured')">
      <template #description>{{ error }}</template>
    </Alert>

    <div v-else class="flex min-w-0 flex-col gap-6 py-4">
      <UsageBar
        v-if="storage.workspace"
        :label="__('Storage')"
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
      <p class="text-p-xs text-ink-muted">{{ breakdown }}</p>

      <!--
        The one thing a storage meter has to say and almost never does. Deleting
        a gigabyte and watching the number stay put is correct — the object
        survives so the delete can be undone — and is indistinguishable from a
        bug unless the screen says it out loud, with the way to act on it
        beside it.
      -->
      <p
        v-if="storage.bin?.files"
        data-slot="storage-bin"
        class="text-p-xs text-ink-muted"
      >
        {{ binNote }}
      </p>
      <router-link
        v-if="storage.bin?.files"
        :to="{ name: 'Drive', query: { place: 'trash' } }"
        class="text-p-xs text-ink-secondary underline underline-offset-2 hover:text-ink-primary"
        @click="settings.open = false"
      >
        {{ __('Empty the bin to get that back now') }}
      </router-link>

      <section v-if="storage.by_kind?.length" class="flex min-w-0 flex-col gap-2">
        <h3 class="text-p-sm font-medium text-ink-primary">{{ __('By kind') }}</h3>
        <div
          v-for="row in storage.by_kind"
          :key="row.kind"
          data-slot="storage-kind"
          class="flex min-w-0 items-center gap-3"
        >
          <Icon :name="iconForKind(row.kind)" class="size-4 shrink-0 text-ink-muted" />
          <span class="w-24 shrink-0 text-p-sm text-ink-secondary">{{ labelForKind(row.kind) }}</span>
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
          <span class="w-20 shrink-0 text-end text-p-sm tabular-nums text-ink-secondary">
            {{ row.label }}
          </span>
        </div>
      </section>

      <section v-if="storage.by_folder?.length" class="flex min-w-0 flex-col gap-2">
        <h3 class="text-p-sm font-medium text-ink-primary">{{ __('By folder') }}</h3>
        <div
          v-for="row in storage.by_folder"
          :key="row.folder"
          data-slot="storage-folder"
          class="flex min-w-0 items-center gap-3"
        >
          <Icon name="lucide-folder" class="size-4 shrink-0 text-ink-muted" />
          <span class="min-w-0 flex-1 truncate text-sm text-ink-secondary">{{ row.folder }}</span>
          <span class="w-20 shrink-0 text-end text-p-sm tabular-nums text-ink-secondary">
            {{ row.label }}
          </span>
        </div>
      </section>

      <section v-if="storage.biggest?.length" class="flex min-w-0 flex-col gap-2">
        <h3 class="text-p-sm font-medium text-ink-primary">{{ __('The biggest') }}</h3>
        <div
          v-for="row in storage.biggest"
          :key="row.name"
          data-slot="storage-biggest"
          class="flex min-w-0 items-center gap-3"
        >
          <Icon :name="iconForKind(row.kind)" class="size-4 shrink-0 text-ink-muted" />
          <span class="min-w-0 flex-1 truncate text-sm text-ink-secondary">
            {{ row.file_name }}
          </span>
          <span class="shrink-0 text-p-xs text-ink-muted">{{ row.folder }}</span>
          <span class="w-20 shrink-0 text-end text-p-sm tabular-nums text-ink-secondary">
            {{ row.label }}
          </span>
        </div>
      </section>

      <EmptyState
        v-if="!storage.files"
        icon="lucide-hard-drive"
        :title="__('Nothing stored yet')"
        :description="__('Files uploaded anywhere in this workspace show up here.')"
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
import EmptyState from '@/shared/components/EmptyState.vue'
import UsageBar from '@/modules/onespace/components/UsageBar.vue'
import { PANEL_BODY, PANEL_HEADER } from '@/modules/onespace/components/settings/geometry'
import { workspace } from '@/shared/lib/workspace'
import { settings } from '@/modules/onespace/lib/shell/settings'
import { errorText } from '@/shared/lib/runtime/errors'
// The same glyphs the Drive draws, because they are the same kinds.
import { iconForKind, labelForKind } from '@/modules/onestorage/lib/files'
import { __ } from '@/shared/lib/runtime/translate'


const router = useRouter()

const storage = ref({})
const loading = ref(true)
const error = ref('')

const largest = computed(() =>
  Math.max(1, ...(storage.value.by_kind || []).map((one) => one.bytes || 0)),
)

const share = (size) => Math.round(((size || 0) / largest.value) * 100)

// One sentence per count rather than a plural glued on: "file" and "files" are
// one word in English and several elsewhere.
//
// Both say the same second thing, and it is the one that makes the two numbers
// agree: the same file on two records is one file here, because it is stored
// once and charged once. Said because it is the difference between a breakdown
// a reader can add up and one that reads as a bug.
const breakdown = computed(() =>
  storage.value.files === 1
    ? __(
        'The breakdown below covers the one file you can see, which is {0}. The same file on two records is one file here, because it is stored once — and the meter above is the whole workspace, including files on records you cannot open.',
        [storage.value.visible_label],
      )
    : __(
        'The breakdown below covers the {0} files you can see, which is {1}. The same file on two records is one file here, because it is stored once — and the meter above is the whole workspace, including files on records you cannot open.',
        [storage.value.files, storage.value.visible_label],
      ),
)

const binNote = computed(() => {
  const bin = storage.value.bin || {}
  return bin.files === 1
    ? __(
        'The bin is holding {0} across one file, which still counts. It is removed for good {1} days after it went there.',
        [bin.label, bin.days],
      )
    : __(
        'The bin is holding {0} across {1} files, which still counts. Each is removed for good {2} days after it went there.',
        [bin.label, bin.files, bin.days],
      )
})

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
