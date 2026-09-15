<template>
  <!--
    What a file *is*, under the picture of it.

    The details pane drew a thumbnail, a name and "Document · 6.3 KB", which is
    the row you clicked said twice — and then a large white rectangle. Every
    file manager on the reference board puts the facts there, because the pane
    is the only place in a file manager with room for a sentence, and because
    the questions people actually open one to answer are *where is this*, *who
    put it here* and *what is it attached to*.

    Nothing here is fetched. Every one of these is already on the row — the
    list read them to draw itself — so this band costs a render and no request.
    `reading.FIELDS` is the list, and the one thing it does not carry is a
    person's name, which `_shape` resolves into `owner_person` for the same
    reason the row's avatar needs it.

    Rows that have no answer are not drawn. A blank beside a label is a fact
    that failed to load, which is a different statement from not having one.
  -->
  <dl data-slot="file-facts" class="flex flex-col gap-2 text-p-sm">
    <div v-for="one in facts" :key="one.label" class="flex gap-3">
      <dt class="w-24 shrink-0 text-ink-muted">{{ one.label }}</dt>
      <!-- The two dates say "8 hours ago" and keep the exact moment in a
           tooltip, which is where `format.js` says to put it. A `title`
           attribute would be a second tooltip mechanism in a product that
           already has one. -->
      <dd class="min-w-0 flex-1 truncate text-ink-secondary">
        <Tooltip v-if="one.exact" :text="one.exact">
          <span>{{ one.value }}</span>
        </Tooltip>
        <template v-else>{{ one.value }}</template>
      </dd>
    </div>
  </dl>
</template>

<script setup>
import { computed } from 'vue'

import { Tooltip } from '@/ui'

import { labelForKind } from '@/modules/onestorage/lib/files'
import { sizeText } from '@/shared/lib/files/size'
import { ago, moment } from '@/shared/lib/runtime/format'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  /** The row, as any file list has it. */
  file: { type: Object, required: true },
})

/**
 * Where it is, said the way a person would say it.
 *
 * A folder's id *is* its path — `Home/Drawings/Revisions` — so this is a
 * split and not a walk. `Home` comes off the front because it is the root and
 * naming the root is telling somebody they are in a file system.
 */
const where = computed(() => {
  const parts = String(props.file.folder || '').split('/').filter(Boolean)
  if (parts[0] === 'Home') parts.shift()
  return parts.join(' / ')
})

const facts = computed(() => {
  const file = props.file
  const said = [
    [__('Kind'), file.is_folder ? __('Folder') : labelForKind(file.custom_kind)],
    [__('Size'), file.is_folder ? '' : sizeText(file.file_size, { blank: '' })],
    [__('Where'), where.value],
    // The record it belongs to, which is the question this pane is opened to
    // answer more often than any other — `docs/DRIVE.md` §13. Said rather than
    // linked: which *screen* to open a Quotation on is a question about a
    // space, and OneCloud is not inside one.
    [__('On'), file.attached_to_doctype
      ? `${file.attached_to_doctype} · ${file.attached_to_name}`
      : ''],
    [__('Owner'), file.owner_person?.label || ''],
    // `ago` is the house rule — under a week relative, over a week a date —
    // and it is what the row under the name already says, so the pane agrees
    // with the list rather than restating it in a different notation. The
    // exact moment goes in the tooltip, which is where `format.js` says to put
    // it.
    [__('Added'), file.creation ? ago(file.creation) : '', moment(file.creation)],
    [__('Last changed'), file.modified ? ago(file.modified) : '', moment(file.modified)],
    // Only when it is, because "Private: no" is a sentence nobody wants and
    // "Private: yes" is the default. What is worth saying is the exception.
    [__('Visible to'), file.is_private ? '' : __('Anybody with the link')],
  ]
  return said
    .filter(([, value]) => value)
    .map(([label, value, exact]) => ({ label, value, exact: exact || undefined }))
})
</script>
