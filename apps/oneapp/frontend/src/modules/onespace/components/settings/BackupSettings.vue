<template>
  <!--
    What is kept, and going back to one of them.

    The list is the easy half. The hard half is the dialog: a restore is the
    only thing in this product a customer can do to themselves that destroys
    work, and the difference between a feature and an incident is whether the
    number of records about to disappear was in front of them before they
    pressed it. So nothing here is a confirmation in the usual sense — no "are
    you sure". It is a count, and then a sentence saying which part of it cannot
    be undone by restoring forward again.
  -->
  <SettingsHeader
    :title="__('Backups')"
    :description="__('Copies of this workspace, and going back to one of them.')"
    :class="PANEL_HEADER"
  >
    <template #actions>
      <Button
        icon-left="lucide-download"
        :label="__('Back up now')"
        :loading="backingUp"
        @click="backUpNow"
      />
    </template>
  </SettingsHeader>

  <SettingsBody :class="PANEL_BODY">
    <LoadingText v-if="loading" class="py-8" :text="__('Loading')" />

    <Alert v-else-if="error" theme="red" :title="__('Backups could not be read')">
      <template #description>{{ error }}</template>
    </Alert>

    <Alert
      v-else-if="!data.ok"
      theme="amber"
      :title="__('This workspace has no storage yet')"
    >
      <template #description>
        {{ __("Backups are written to your workspace's object storage, and it has not been set up. Nothing is being kept.") }}
      </template>
    </Alert>

    <div v-else class="flex min-w-0 flex-col gap-6 py-4">
      <p class="text-p-sm text-ink-secondary">{{ schedule }}</p>

      <!--
        The one thing about this list that looks wrong and is not. A set holds a
        database dump and a config and no file archive, because the files are
        already objects in the same bucket — restoring does not fetch them, it
        leaves them where they are.
      -->
      <p v-if="data.files_in_bucket" class="text-p-xs text-ink-muted">
        {{ __('Files are not in these copies. They are kept as they are, and a restore matches them back up with the records that own them.') }}
      </p>

      <section v-if="data.points?.length" class="flex min-w-0 flex-col gap-2">
        <h3 class="text-p-sm font-medium text-ink-primary">{{ __('Go back to') }}</h3>
        <ul class="flex flex-col">
          <li
            v-for="point in data.points"
            :key="point.stamp"
            data-slot="restore-point"
            class="flex min-w-0 items-center gap-3 border-b border-outline-gray-1 py-2.5"
          >
            <Icon name="lucide-history" class="size-4 shrink-0 text-ink-muted" />
            <span class="min-w-0 flex-1 truncate text-sm text-ink-primary">
              {{ when(point.when) }}
            </span>
            <span class="shrink-0 text-p-xs tabular-nums text-ink-muted">
              {{ size(point.bytes) }}
            </span>
            <Badge
              v-if="!point.restorable"
              theme="amber"
              :label="__('Incomplete')"
            />
            <Button
              v-else
              :label="__('Restore')"
              :tooltip="__('Go back to {0}', [when(point.when)])"
              @click="open(point)"
            />
          </li>
        </ul>
      </section>

      <EmptyState
        v-else
        icon="lucide-history"
        :title="__('Nothing kept yet')"
        :description="__('The first copy is taken at the next scheduled time, or now if you ask for one.')"
      />
    </div>
  </SettingsBody>

  <!--
    The whole point of this screen. Opened before anything happens, filled from
    the site's own database, and it counts rather than warns.
  -->
  <Dialog v-model="showing" :title="__('Go back to {0}', [when(chosen?.when)])">
    <template #default>
      <LoadingText v-if="counting" class="py-6" :text="__('Working out what changes')" />

      <ErrorMessage v-else-if="countError" :message="countError" />

      <div v-else-if="plan" class="flex flex-col gap-4">
        <p class="text-p-sm text-ink-secondary">{{ headline }}</p>

        <section v-if="plan.records?.length" class="flex flex-col gap-1.5">
          <div
            v-for="row in plan.records.slice(0, 8)"
            :key="row.doctype"
            data-slot="restore-count"
            class="flex min-w-0 items-center gap-3"
          >
            <span class="min-w-0 flex-1 truncate text-sm text-ink-secondary">
              {{ row.doctype }}
            </span>
            <span class="w-28 shrink-0 text-end text-p-xs tabular-nums text-ink-secondary">
              {{ __('{0} new', [row.made]) }}
            </span>
            <span class="w-32 shrink-0 text-end text-p-xs tabular-nums text-ink-secondary">
              {{ __('{0} changed', [row.changed]) }}
            </span>
          </div>
        </section>

        <!--
          Separated from the counts above rather than listed with them, because
          it is a different kind of loss: a record restored away can be typed
          again, and these bytes are gone.
        -->
        <Alert
          v-if="plan.files?.count"
          theme="red"
          :title="__('Files that will be deleted')"
        >
          <template #description>{{ filesNote }}</template>
        </Alert>

        <Alert
          v-if="plan.unrecoverable_files"
          theme="amber"
          :title="__('Files that cannot come back')"
        >
          <template #description>{{ goneNote }}</template>
        </Alert>

        <Checkbox
          v-model="understood"
          :label="__('I understand this cannot be undone')"
        />
      </div>
    </template>

    <template #actions>
      <Button
        variant="solid"
        theme="red"
        :label="__('Restore this workspace')"
        :disabled="!understood || counting || !plan"
        :loading="starting"
        @click="restore"
      />
      <Button :label="__('Cancel')" @click="showing = false" />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  Alert,
  Badge,
  Button,
  Checkbox,
  dayjsLocal,
  Dialog,
  ErrorMessage,
  Icon,
  LoadingText,
  SettingsBody,
  SettingsHeader,
  toast,
} from '@/ui'
import EmptyState from '@/shared/components/EmptyState.vue'
import { PANEL_BODY, PANEL_HEADER } from '@/modules/onespace/components/settings/geometry'
import { workspace } from '@/shared/lib/workspace'
import { errorText } from '@/shared/lib/runtime/errors'
import { __ } from '@/shared/lib/runtime/translate'

const data = ref({})
const loading = ref(true)
const error = ref('')
const backingUp = ref(false)

const showing = ref(false)
const chosen = ref(null)
const plan = ref(null)
const counting = ref(false)
const countError = ref('')
const understood = ref(false)
const starting = ref(false)

const when = (value) => (value ? dayjsLocal(value).format('D MMM YYYY, HH:mm') : '')

// Bytes as a person reads them. The server formats the file total inside the
// preview, because that number sits in a sentence; this one is a column.
const size = (bytes) => {
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let value = bytes || 0
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  return `${value >= 10 || unit === 0 ? Math.round(value) : value.toFixed(1)} ${units[unit]}`
}

const schedule = computed(() => {
  const perDay = data.value.per_day || 0
  const days = data.value.retention_days || 0
  if (!perDay) {
    return __('Your plan does not include automatic backups. You can still take one whenever you want.')
  }
  // The window can be missing for one sync on a workspace whose plan has just
  // been read for the first time, and "kept for 0 days" is a sentence nobody
  // should ever be shown about their backups.
  if (!days) {
    return perDay === 1
      ? __('A copy is taken once a day.')
      : __('A copy is taken {0} times a day.', [perDay])
  }
  return perDay === 1
    ? __('A copy is taken once a day and kept for {0} days.', [days])
    : __('A copy is taken {0} times a day and each is kept for {1} days.', [perDay, days])
})

const headline = computed(() => {
  const made = plan.value?.made || 0
  const changed = plan.value?.changed || 0
  if (!made && !changed) {
    return __('Nothing has changed since then, so this would put the workspace back as it is.')
  }
  return __(
    'Everything after {0} goes: {1} records made since then are deleted, and {2} that were edited go back to how they were.',
    [when(plan.value?.when), made, changed],
  )
})

const filesNote = computed(() =>
  __(
    '{0} files uploaded since then — {1} — are deleted from storage, because no record will be left that owns them. This part cannot be undone by restoring forward again.',
    [plan.value?.files?.count, plan.value?.files?.label],
  ),
)

const goneNote = computed(() =>
  __(
    '{0} files were deleted since then. Their records come back and the files do not: those were removed for good when the bin emptied.',
    [plan.value?.unrecoverable_files],
  ),
)

const load = async () => {
  loading.value = true
  try {
    data.value = (await workspace.backupPoints()) || {}
  } catch (raised) {
    error.value = errorText(raised)
  } finally {
    loading.value = false
  }
}

const backUpNow = async () => {
  backingUp.value = true
  try {
    await workspace.backUpNow()
    // Not reloaded: it is a queued job, and the list would come back unchanged
    // and read as the button having done nothing.
    toast.success(__('Taking a copy now. It appears here when it lands.'))
  } catch (raised) {
    toast.error(errorText(raised))
  } finally {
    backingUp.value = false
  }
}

const open = async (point) => {
  chosen.value = point
  plan.value = null
  countError.value = ''
  understood.value = false
  showing.value = true
  counting.value = true
  try {
    plan.value = await workspace.restorePreview(point.stamp)
  } catch (raised) {
    countError.value = errorText(raised)
  } finally {
    counting.value = false
  }
}

const restore = async () => {
  starting.value = true
  try {
    await workspace.restoreWorkspace(chosen.value.stamp)
    showing.value = false
    toast.success(
      __('Restoring. The workspace goes offline for a few minutes and comes back at that moment.'),
    )
  } catch (raised) {
    countError.value = errorText(raised)
  } finally {
    starting.value = false
  }
}

onMounted(load)
</script>
