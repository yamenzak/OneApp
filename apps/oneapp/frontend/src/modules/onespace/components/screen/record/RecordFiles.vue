<template>
  <!-- `relative` for the selection bar, which floats over these rows rather
       than over the window: this tab is not the scroller, the record pane is,
       so the bar belongs to the pane it is about — §C2. -->
  <div class="relative flex flex-col gap-3 pt-4">
    <!--
      What is filed against this record, drawn by the Drive's own row.

      Not a list that looks like the Drive's: the same component over the same
      query with one more `where`. A file attached to a record has
      `attached_to_doctype` and a file in a folder has `folder`, and it can have
      both — which is what makes this a filter rather than a second store, and
      what stops this tab being the one that never got the new column.
    -->
    <div v-if="canWrite" class="flex gap-2">
      <Button
        class="flex-1"
        icon-left="lucide-paperclip"
        :label="__('Attach a file')"
        @click="picking = true"
      />
      <!--
        The same New menu the Drive has, pointed at this record. A document or
        a sheet made here is attached rather than filed in a folder, which is
        what makes "the project's scope of works" a query — see `useNewFile`.
      -->
      <!--
        Not until the doctype has arrived. `where()` reads `doctype`, which
        `reload` fills a round trip later — so pressing New the moment the tab
        opens made a document attached to nothing, silently and permanently.
        A disabled button for the half-second it takes is the honest answer;
        the alternative is a file the record does not have.
      -->
      <Dropdown :options="newOptions">
        <Button
          icon-left="lucide-plus"
          :label="__('New')"
          :tooltip="__('New file')"
          :loading="making"
          :disabled="!doctype"
        />
      </Dropdown>
    </div>
    <FilePicker
      v-model="picking"
      multiple
      :attached-to="{ doctype, docname: name }"
      @picked="reload"
    />

    <!-- Which language, for `New > Code`. The same dialog the Drive draws,
         because it is the same menu asking the same question. -->
    <LanguagePicker v-model="choosingLanguage" @pick="newText($event.key)" />

    <!--
      The frame is `DataList` over `fileSource` — §B1. The same source the
      Drive reads, with the record on it: `place: 'record'` is `listing`'s own
      filter for "attached to this one", so this tab and the Drive are two
      readings of one query rather than two lists that have to be kept in
      step.
    -->
    <DataList
      ref="list"
      :source="source"
      :skeleton="3"
      :page-length="PAGE"
    >
      <template #row="{ row: file, picked, toggle }">
      <FileRow
        :file="file"
        :link="linkFor(file)"
        :selectable="canWrite"
        :selected="picked"
        actions
        :can-write="canWrite"
        @select="toggle"
        @open="look"
        @favourite="favourite"
        @share="share"
        @rename="startRename"
        @trash="remove"
      />
      </template>
    </DataList>

    <!--
      Two files chosen and both in the bin in one go.

      Nothing here is new: the ticks are the frame's, the bar is the one a
      record list and a mailbox draw, and the verb is the same `driveTrash` the
      row menu calls. That is what B1 was for — this tab had no bulk at all,
      and it did not need a feature to get one.
    -->
    <SelectionBar
      v-if="chosenCount"
      :count="chosenCount"
      :total="list?.rows?.length || 0"
      @clear="list?.clearChosen()"
      @all="list?.toggleAll()"
    >
      <Button
        icon-left="lucide-trash-2"
        theme="red"
        :label="__('Move to the bin')"
        :tooltip="__('Move to the bin')"
        :loading="binning"
        @click="removeChosen"
      />
    </SelectionBar>

    <ErrorMessage :message="error" />

    <!-- Beside the list, not over it — §C2. A file filed against a record is
         the subject of the list you are looking at, which is the same answer
         the Drive already gave; it was a dialog here only because this tab was
         written before the pane existed. -->
    <FilePane v-model="previewing" :file="chosen" />
    <FileShare v-model="sharing" :file="chosen" />

    <Dialog v-model="renaming" :title="__('Rename')">
      <template #default>
        <FormControl v-model="newName" :label="__('Name')" @keyup.enter="finishRename" />
      </template>
      <template #actions>
        <Button variant="solid" :label="__('Rename')" @click="finishRename" />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, inject, ref } from 'vue'
import { Button, Dialog, Dropdown, ErrorMessage, FormControl } from '@/ui'
import DataList from '@/shared/components/DataList.vue'
import { CAN } from '@/shared/lib/capability'
import { PAGE, fileSource } from '@/shared/lib/list/files'
import SelectionBar from '@/modules/onespace/components/screen/bodies/SelectionBar.vue'
import FilePicker from '@/modules/onestorage/components/FilePicker.vue'
import FilePane from '@/modules/onestorage/components/FilePane.vue'
import FileRow from '@/modules/onestorage/components/FileRow.vue'
import FileShare from '@/modules/onestorage/components/FileShare.vue'
import { workspace } from '@/shared/lib/workspace'
import { errorText } from '@/shared/lib/runtime/errors'
import { routeFor } from '@/modules/onestorage/lib/files'
import { useNewFile } from '@/shared/composables/useNewFile'
import LanguagePicker from '@/modules/onecode/components/LanguagePicker.vue'
import { RETURN_TO, returnQuery } from '@/modules/onespace/lib/screen/returnTo'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  name: { type: String, default: '' },
  canWrite: { type: Boolean, default: false },
})

const emit = defineEmits(['count'])

const doctype = ref('')
const error = ref('')
const list = ref(null)

/**
 * What is filed against this record — §B1.
 *
 * The `record` door on `fileSource`, which is `spaceview.attachments`: the
 * doctype behind a screen and the filter behind an Attachment Gallery are
 * both decided on the server, and neither is a thing the browser may send.
 *
 * Paging, and — where this person may write — bulk. The list is what one
 * record has, which is a handful and is already in the order things arrived;
 * a search box over it would be a control for a problem this tab does not
 * have. Bulk is a different matter: a scope of works arrives as eleven
 * drawings and two of them are the wrong revision.
 */
const source = computed(() => fileSource({
  can: { [CAN.BULK]: props.canWrite },
  record: {
    spaceCode: props.spaceCode,
    screen: props.screen,
    name: props.name,
  },
  empty: {
    icon: 'lucide-paperclip',
    title: __('No files'),
    description: __('Nothing is filed against this one yet.'),
  },
  // The doctype arrives with the rows — `New` cannot be pressed before it
  // does, which is what the disabled button above is for — and the count is
  // the record's, not the page's.
  onAnswer: (found) => {
    doctype.value = found.doctype || ''
    emit('count', found.total ?? (found.files || []).length)
  },
}))

const reload = () => list.value?.read()

// The record this tab belongs to, so an editor opened from here can come back.
const came = inject(RETURN_TO, null)

// A file made here belongs to the record rather than to a folder. `doctype` is
// filled by the reload below, so this reads it rather than closing over it.
const { making, options: newOptions, choosingLanguage, newText, loadTemplates } = useNewFile(
  () => ({ doctype: doctype.value, docname: props.name }),
)

// Whether the picker is open, and which file the dialogs are about.
const picking = ref(false)
const previewing = ref(false)
const sharing = ref(false)
const renaming = ref(false)
const chosen = ref(null)
const newName = ref('')

/**
 * A sheet, a document or a text file opens in its editor; everything else is
 * looked at where it is. Same rule as the Drive, out of the same function —
 * and with the record on it, so the editor's trail leads back here.
 */
const linkFor = (file) => {
  const route = routeFor(file)
  return route ? { ...route, query: returnQuery(came?.value) } : null
}

// The row is a link where there is somewhere to go, so this only ever runs for
// the files that are looked at rather than opened.
const look = (file) => {
  chosen.value = file
  previewing.value = true
}

const share = (file) => {
  chosen.value = file
  sharing.value = true
}

const startRename = (file) => {
  chosen.value = file
  newName.value = file.file_name || ''
  renaming.value = true
}

const run = async (work) => {
  error.value = ''
  try {
    await work()
    await reload()
  } catch (raised) {
    error.value = errorText(raised)
  }
}

const favourite = (file) => run(() => workspace.driveFavourite(file.name, !file.liked))

const finishRename = async () => {
  const title = newName.value.trim()
  if (!title) return
  await run(() => workspace.driveRename(chosen.value.name, title))
  if (!error.value) renaming.value = false
}

// The bin and not a delete. Taking a file off a record used to remove the row
// outright, which meant a misplaced click on the wrong record's Files tab was
// unrecoverable — and the bin exists precisely so that it is not.
const remove = (file) => run(() => workspace.driveTrash([file.name]))

// The same verb over everything ticked. The frame drops the rows that are gone
// on the re-read `run` ends with, so the bar empties itself.
const chosenCount = computed(() => list.value?.chosen?.size || 0)
const binning = ref(false)
const removeChosen = async () => {
  const names = (list.value?.picked || []).map((one) => one.name)
  if (!names.length) return
  binning.value = true
  try {
    await run(() => workspace.driveTrash(names))
  } finally {
    binning.value = false
  }
}

loadTemplates()
</script>
