<template>
  <!--
    Every file in the workspace, in one place. A rail of places, a path, and a
    list or a grid. What is new is underneath: these are Frappe `File` rows, the
    same ones an attachment is, so nothing here is a second store.
  -->
  <PageHeader>
    <Trail :items="crumbs">
      <!-- The rail, on a phone: the shell draws a sidebar only on a desktop.
           The same list, from the same module, so the two cannot drift. -->
      <template v-if="isMobile" #before>
        <Dropdown :options="placeOptions">
          <Button
            data-slot="drive-places"
            icon-right="lucide-chevron-down"
            variant="ghost"
            :label="placeName"
          />
        </Dropdown>
      </template>
    </Trail>

    <div class="flex shrink-0 items-center gap-2">
      <!-- The frame's search, drawn here: the box belongs beside Upload and
           New rather than over the rows — §B1, `v-model:searched`. -->
      <ListSearch
        v-model="searched"
        :placeholder="__('Search files')"
        @changed="list?.read()"
      />
      <!-- List or grid, remembered: a person who wants thumbnails wants them
           on every folder, not once. -->
      <Button
        :icon="grid ? 'lucide-list' : 'lucide-layout-grid'"
        :label="grid ? __('Show as a list') : __('Show as a grid')"
        :tooltip="grid ? __('Show as a list') : __('Show as a grid')"
        variant="ghost"
        @click="setGrid(!grid)"
      />
      <!--
        Icon-only on a phone. `icon` rather than `icon-left` is what makes a
        Button icon-only; the label stays either way, because it is also the
        accessible name.
      -->
      <Button
        v-if="place === 'trash'"
        :icon="isMobile ? 'lucide-trash-2' : undefined"
        :icon-left="isMobile ? undefined : 'lucide-trash-2'"
        theme="red"
        :label="__('Empty the bin')"
        :tooltip="__('Empty the bin')"
        :disabled="!drive.files.value.length || drive.busy.value"
        @click="emptying = true"
      />
      <!--
        Inside a mount there is nothing to upload into and nothing to make:
        the Drive browses a host and does not write to one. What is useful
        instead is asking the host again, because the commonest question about
        a drop folder is whether today's delivery has landed.
      -->
      <template v-else-if="inRemote">
        <Button
          icon-left="lucide-refresh-cw"
          :label="__('Check again')"
          :tooltip="__('Ask the host again')"
          :loading="loading"
          @click="drive.load()"
        />
        <!-- The mount itself, managed where it is used. A connection that can
             only be paused from the desk is a connection nobody pauses: the
             moment you want to is the moment the host is misbehaving, and the
             person looking at the red dot is here. -->
        <Dropdown :options="mountOptions">
          <Button
            data-slot="drive-mount-menu"
            icon="lucide-ellipsis-vertical"
            variant="ghost"
            :label="__('This connection')"
            :tooltip="__('This connection')"
          />
        </Dropdown>
      </template>
      <template v-else>
        <!--
          Upload. A plain input rather than `FileUploader`: the queue is
          `useUploads`, which outlives this page, and a component that owns
          reactive upload state would end where the page does.
        -->
        <!-- A hidden file input is the file picker itself; `FormControl` draws
             a labelled control and there is nothing here to label. -->
        <!-- eslint-disable-next-line vue/no-restricted-html-elements -->
        <input
          ref="chooser"
          name="drive-upload"
          type="file"
          multiple
          class="hidden"
          @change="chosenFiles"
        >
        <!-- Drawn and refused rather than dropped where there is nowhere to
             put a file — §F1's middle state. In the Records place a directory
             is a query, so the reason is on the control instead of the
             control being missing. -->
        <Button
          :icon="isMobile ? 'lucide-upload' : undefined"
          :icon-left="isMobile ? undefined : 'lucide-upload'"
          :label="__('Upload')"
          :disabled="!can.can(CAN.CREATE)"
          :tooltip="can.why(CAN.CREATE) || __('Upload files')"
          @click="chooser?.click()"
        />
        <!--
          Everything made rather than uploaded, behind one button — a folder
          included. A dropdown rather than a row of buttons, because a
          workspace with an estimator template starts from it far more often
          than from a blank grid, and because "New folder" sitting beside "New"
          was two buttons for one idea: the first thing anybody asks of either
          is "make me something here".
        -->
        <Dropdown :options="makeOptions">
          <Button
            :icon="isMobile ? 'lucide-plus' : undefined"
            :icon-left="isMobile ? undefined : 'lucide-plus'"
            :icon-right="isMobile ? undefined : 'lucide-chevron-down'"
            variant="solid"
            :label="__('New')"
            :disabled="!can.can(CAN.CREATE)"
            :tooltip="can.why(CAN.CREATE) || __('New file')"
            :loading="making"
          />
        </Dropdown>
      </template>
    </div>
  </PageHeader>

  <!-- The rail is the shell's, drawn into its `#sidebar` slot the way Mail's
       is — a page that drew its own would be two rails on one screen. -->
  <div class="flex h-full min-h-0 gap-2">
    <!--
      Drop anywhere in the pane, not only on the list: a person dragging four
      files at an empty folder aims at the empty state.

      The counting, the treatment, the folder that arrives as a zero-byte file
      and the size ceiling are all `v-drop-files` — §D3. What is left here is
      the only part that is the Drive's: where the bytes go, and the two
      places they may not.
    -->
    <div
      class="flex min-w-0 flex-1 flex-col rounded-6 bg-surface-base p-5"
      data-slot="drive-dropzone"
      v-drop-files="{ onFiles: dropped, disabled: place === 'trash' || inRemote }"
    >
      <!-- What the bin is, said where somebody deciding whether to empty it is
           looking: thirty days is the promise the sweep keeps. -->
      <Alert
        v-if="place === 'trash' && drive.files.value.length"
        class="mb-4"
        theme="gray"
        :title="__('Everything here is deleted after thirty days')"
      >
        <template #description>
          {{ __('Until then it can be put back exactly where it was.') }}
        </template>
      </Alert>

      <!--
        The frame is `DataList` over `fileSource` — §B1. The skeleton, the
        empty state, the failed read and the next page are all its; what is
        passed in is the header this list happens to want and the row it
        happens to draw.
      -->
      <ContextMenu :options="rowMenu">
      <DataList
        ref="list"
        v-model:searched="searched"
        :source="source"
        :skeleton="8"
        :page-length="PAGE"
        class="min-h-0 flex-1 overflow-y-auto"
        :body-class="grid
          ? 'grid grid-cols-[repeat(auto-fill,minmax(9rem,1fr))] gap-3'
          : 'flex flex-col'"
      >
        <template #header="{ allPicked, toggleAll }">
        <!--
          The header, which is a row of its own rather than a set of column
          cells: a file's name is a column and everything after it — who,
          when, how big — is one right-hand cluster, so headings over it would
          label nothing. Select-all on the left, the count beside it, and the
          order on the right.

          Drawn over the grid too. The grid has no rows to head, but "biggest
          first" is a question you ask of thumbnails as often as of a list, and
          a control that disappears when you switch view is a control you stop
          trusting.
        -->
        <div class="flex items-center gap-2 pb-1 text-p-xs text-ink-muted">
          <!-- No select-all where the source cannot act in bulk: over a
               mount the rows have no checkbox either, because there is
               nothing this list can do to them. -->
          <template v-if="!grid && can.can(CAN.BULK)">
            <Checkbox
              :model-value="allPicked"
              :aria-label="__('Select everything here')"
              class="ms-2.5"
              @update:model-value="toggleAll"
            />
            <span>{{ counted }}</span>
          </template>
          <!-- Said where the tick would have been, rather than a row of rows
               with no checkboxes and no explanation — §F1. -->
          <template v-else-if="!grid && can.why(CAN.BULK)">
            <span>{{ counted }}</span>
            <span class="text-ink-muted">· {{ can.why(CAN.BULK) }}</span>
          </template>
          <span v-else>{{ counted }}</span>

          <!-- Wrapped, because `Dropdown`'s root is reka's provider and a class
               on it has no element to land on. -->
          <div class="ms-auto">
          <!-- Drawn and disabled on a mount rather than dropped, with the
               reason on it: a control that vanishes is a control somebody
               keeps looking for. §F1. -->
          <Dropdown :options="orderOptions">
            <Button
              variant="ghost"
              size="sm"
              data-slot="drive-order"
              :disabled="!can.can(CAN.SORT)"
              :icon-left="drive.descending.value
                ? 'lucide-arrow-down-narrow-wide'
                : 'lucide-arrow-up-narrow-wide'"
              icon-right="lucide-chevron-down"
              :label="orderName"
              :tooltip="can.why(CAN.SORT) || __('How these are ordered')"
            />
          </Dropdown>
          </div>
        </div>
        </template>

        <!--
          The grid fits the column, not the window — which is why it is a
          `body-class` rather than a wrapper here.

          `md:grid-cols-4 xl:grid-cols-6` counts from the viewport, and the
          list does not have the viewport — it has whatever the pane left it.
          So opening a file on a 1440 screen kept six columns in a 500-pixel
          column and the cards ran into each other, and dragging the resizer
          narrower only made it worse.

          `auto-fill` with a floor asks the question the right way round: how
          many 9rem cards fit *here*. Nothing to recalculate on resize and no
          breakpoint to keep in step with the pane's width.
        -->
        <template #row="{ row: file, picked, toggle }">
          <FileRow
            :file="file"
            :place="place"
            :link="routeFor(file)"
            :inline="isMobile ? [] : INLINE"
            :dense="editing && previewing && !isMobile"
            :grid="grid"
            selectable
            actions
            movable
            :selected="picked"
            :trashed="place === 'trash'"
            @menu="(options) => (rowMenu = options)"
            @move-into="moveInto"
            @open="open"
            @select="toggle"
            @favourite="drive.favourite"
            @share="startShare"
            @copy="copyHere"
            @rename="startRename"
            @move="(one) => startMove([one])"
            @trash="(one) => drive.trash(one)"
            @restore="(one) => drive.restore(one)"
            @destroy="(one) => drive.destroy(one)"
          />
        </template>
      </DataList>
      </ContextMenu>
    </div>

    <!--
      The file you are looking at, beside the list rather than over it.

      A dialog was the wrong shape for a file manager: looking at a photograph
      is how you decide which photograph, and a modal makes that a sequence of
      open-look-close-open rather than a walk down the list. The same pane a
      record opens in, for the same reason and with the same resizer, and the
      same one a mail attachment and a record's Files tab open in since §C2 —
      `FilePane` is where the header and the two verbs live now.

      More of the window than a record pane takes when it holds an editor: a
      record is fields beside a list, and a spreadsheet is the thing you came
      to work in, where 45% of a laptop is four columns.
    -->
    <FilePane
      v-model="previewing"
      :file="looking"
      :max-share="editing ? 0.72 : 0.45"
      :min="editing ? editorFloor() : undefined"
      :shareable="!lookingRemote && !editing"
      :downloadable="!editing"
    >
      <!-- A remote file has no row, so there is nothing to make a link to.
           Copy is the thing that changes that. -->
      <template v-if="lookingRemote" #actions>
        <Button
          icon="lucide-download"
          variant="ghost"
          :label="__('Copy into the Drive')"
          :tooltip="__('Copy into the Drive')"
          :loading="copying"
          @click="copyHere(looking)"
        />
      </template>

      <!--
        A sheet and a document open here rather than on a page of their own,
        and they open editable: the point of a file manager is to work in a
        file without losing the folder you found it in. Cmd-click still opens
        either on its own page, because the row is still a link — see
        `FileRow`.

        `:key` on the name, because both editors load their document once on
        mount: without it, clicking a second sheet would keep the first one on
        screen.
      -->
      <template v-if="mounts">
        <SheetEditor
          v-if="mounts === 'sheet'"
          :key="looking.name"
          :id="looking.name"
          :host-menu="[]"
          hosted
          @close="previewing = false"
        />
        <!--
          `hosted`, so the editor's own way out closes this pane instead of
          routing. Without it a `.py`'s Close button pushed `/one/files` —
          which is what CodeFile's `leave` says must not happen in a pane, and
          did anyway because nothing was passing the message on.
        -->
        <Doc
          v-else
          :key="looking.name"
          :name="looking.name"
          hosted
          @close="previewing = false"
        />
      </template>
    </FilePane>
  </div>

  <!--
    What you can do with what you have chosen, over the list rather than in the
    header: a bar at the top means looking away from the thing you are acting
    on.

    The same `SelectionBar` a record list and a mailbox draw. It used to be a
    `Panel` written out here — a third spelling of a bar that already existed
    twice — and the differences were all accidents: a different count sentence,
    a different gap, a different way of saying "clear". `anchor="screen"`
    is the one real difference, and it is real: this list *is* the scroller, so
    a bar absolute inside it would scroll away with the rows.
  -->
  <SelectionBar
    v-if="chosenCount"
    anchor="screen"
    :count="chosenCount"
    :total="drive.files.value.length"
    @clear="list?.clearChosen()"
    @all="list?.toggleAll()"
  >
    <template v-if="place === 'trash'">
      <Button
        icon-left="lucide-rotate-ccw"
        :label="__('Put it back')"
        :tooltip="__('Put it back')"
        :loading="drive.busy.value"
        @click="drive.restore(picked)"
      />
      <!--
        Icon-only on a phone rather than a shorter word. There are two
        destructive verbs in this product and they are "Move to the bin"
        and "Delete for ever"; abbreviating one of them to "Delete" on a
        narrow screen is how a reader comes to think there are three.
        `icon` and not `icon-left` is what makes a Button icon-only, and
        the label is still the accessible name.
      -->
      <Button
        :icon="isMobile ? 'lucide-trash-2' : undefined"
        :icon-left="isMobile ? undefined : 'lucide-trash-2'"
        theme="red"
        :label="__('Delete for ever')"
        :tooltip="__('Delete for ever')"
        :loading="drive.busy.value"
        @click="drive.destroy(picked)"
      />
    </template>
    <template v-else>
      <Button
        icon-left="lucide-folder-input"
        :label="__('Move')"
        :loading="drive.busy.value"
        @click="startMove(picked)"
      />
      <Button
        :icon="isMobile ? 'lucide-trash-2' : undefined"
        :icon-left="isMobile ? undefined : 'lucide-trash-2'"
        theme="red"
        :label="__('Move to the bin')"
        :tooltip="__('Move to the bin')"
        :loading="drive.busy.value"
        @click="drive.trash(picked)"
      />
    </template>
  </SelectionBar>

  <FileShare v-model="sharing" :file="looking" />

  <!-- Which language, for `New > Code`. One dialog per surface that draws the
       New menu, because the menu is where the question is asked. -->
  <LanguagePicker v-model="choosingLanguage" @pick="newText($event.key)" />
  <ImportSheet v-model="importing" :folder="folder" />
  <ShareOverDav
    v-model="sharingOverDav"
    :folder="folder"
    :folder-label="folderLabel"
  />
  <FolderPicker v-model="moving" :moving="toMove" @chosen="intoFolder" />

  <Dialog v-model="naming" :title="__('New folder')">
    <template #default>
      <FormControl v-model="folderName" :label="__('Name')" @keyup.enter="makeFolder" />
    </template>
    <template #actions>
      <Button
        variant="solid"
        :label="__('Make it')"
        :loading="drive.busy.value"
        @click="makeFolder"
      />
    </template>
  </Dialog>

  <Dialog v-model="renaming" :title="__('Rename')">
    <template #default>
      <FormControl v-model="newName" :label="__('Name')" @keyup.enter="finishRename" />
    </template>
    <template #actions>
      <Button
        variant="solid"
        :label="__('Rename')"
        :loading="drive.busy.value"
        @click="finishRename"
      />
    </template>
  </Dialog>

  <!-- The one that does not come back gets a question in front of it. -->
  <Dialog v-model="emptying" :title="__('Empty the bin')">
    <template #default>
      <p class="text-p-base text-ink-secondary">
        {{ __('Everything in the bin is deleted for good. This cannot be undone.') }}
      </p>
    </template>
    <template #actions>
      <Button
        variant="solid"
        theme="red"
        :label="__('Delete for ever')"
        :loading="drive.busy.value"
        @click="finishEmpty"
      />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Alert,
  Button,
  Checkbox,
  ContextMenu,
  Dialog,
  Dropdown,
  FormControl,
  PageHeader,
} from '@/ui'
import Trail from '@/shared/components/Trail.vue'
import { useCrumbs } from '@/shared/composables/useCrumbs'
import { CAN, offers } from '@/shared/lib/capability'
import DataList from '@/shared/components/DataList.vue'
import SelectionBar from '@/modules/onespace/components/screen/bodies/SelectionBar.vue'
import { PAGE, fileSource } from '@/shared/lib/list/files'
import FileSurface from '@/modules/onestorage/components/FileSurface.vue'
import ListSearch from '@/modules/onespace/components/screen/views/ListSearch.vue'
import FileRow from '@/modules/onestorage/components/FileRow.vue'
import FileShare from '@/modules/onestorage/components/FileShare.vue'
import FolderPicker from '@/modules/onestorage/components/FolderPicker.vue'
import FilePane from '@/modules/onestorage/components/FilePane.vue'
import SheetEditor from '@/modules/onesheet/components/editor/index.vue'
import Doc from '@/modules/onedoc/pages/Doc.vue'
import ImportSheet from '@/modules/onesheet/components/ImportSheet.vue'
import ShareOverDav from '@/modules/onestorage/components/ShareOverDav.vue'
import { openSettings } from '@/modules/onespace/lib/shell/settings'
import { workspace } from '@/shared/lib/workspace'
import { useDrive } from '@/shared/composables/useDrive'
import { useNewFile } from '@/shared/composables/useNewFile'
import LanguagePicker from '@/modules/onecode/components/LanguagePicker.vue'
import { useUploads } from '@/shared/composables/useUploads'
import {
  editorFor, isRemote, mountOf, routeFor,
} from '@/modules/onestorage/lib/files'
import { useIsMobile } from '@/modules/onespace/lib/shell/breakpoint'
import { __ } from '@/shared/lib/runtime/translate'
import { PLACES, labelOf } from '@/modules/onestorage/components/places'
import { recall, remember } from '@/shared/lib/url/remember'

// What an empty place means, which is different in each: an empty bin is good
// news and an empty folder is an invitation.
const EMPTY = {
  home: {
    title: __('Nothing here yet'),
    description: __('Upload a file, or make a folder to put files in.'),
  },
  recents: {
    title: __('Nothing opened yet'),
    description: __('Files you open show up here.'),
  },
  favourites: {
    title: __('No favourites'),
    description: __('Heart a file to keep it here.'),
  },
  shared: {
    title: __('Nothing shared with you'),
    description: __('Files other people share with you appear here.'),
  },
  trash: {
    title: __('The bin is empty'),
    description: __('Deleted files wait here for thirty days.'),
  },
  records: {
    title: __('No files on any record'),
    description: __('Files attached to records appear here.'),
  },
  documents: {
    title: __('No documents yet'),
    description: __('Make one with New.'),
  },
  workbooks: {
    title: __('No workbooks yet'),
    description: __('Make one with New.'),
  },
  // Not in the rail. `?place=all` is the flat view of everything this person
  // can see — what the file picker asks for.
  all: { title: __('No files yet'), description: __('Upload a file to start.') },
}

const route = useRoute()
const router = useRouter()
// The header is a breadcrumb, a search box and two buttons. On a phone that is
// more than 412px holds, so the buttons lose their words and keep their
// tooltips.
const isMobile = useIsMobile()

// The place and the folder are in the URL, so a folder is somewhere you can
// send a colleague. A place that is not one of these is a typo, and a typo must
// not be a blank page: `EMPTY[place]` is read unconditionally by the template.
const place = computed(() =>
  Object.hasOwn(EMPTY, route.query.place) ? route.query.place : 'home',
)
const folder = computed(() => route.query.folder || '')

/**
 * Looking at a folder on somebody else's server.
 *
 * Not a sixth place: the rail's places are `where` clauses on one table and a
 * mount is a socket, so it arrives as a `?folder=` like any other folder and
 * the server decides. What changes here is only the chrome — nothing on a
 * mount can be uploaded to, moved, binned, hearted or shared, because there
 * is no row to do any of it to. See `onestorage/remote.py`.
 */
const inRemote = computed(() => isRemote(folder.value))

// The frame, and what it is looking at. `rows` is the frame's accumulated
// list — every page it has read — which is the set a selection is over and the
// set a drag moves.
const list = ref(null)
const searched = ref('')
const rows = computed(() => list.value?.rows || [])
const loading = computed(() => !!list.value?.loading)

// What is ticked is the frame's — §B1. Read back here because the bar and the
// count sentence are drawn on this page rather than inside it: this list is
// the scroller, so the bar has to be fixed to the window.
const picked = computed(() => list.value?.picked || [])
const chosenCount = computed(() => list.value?.chosen?.size || 0)

const drive = useDrive({
  rows,
  reread: () => list.value?.read(),
  folder,
  route,
  router,
})

/**
 * Where the rows come from — §B1.
 *
 * `fileSource` over `listing`, which is the same query a record's Files tab
 * and the attach picker read. The sort is handed in rather than asked for by
 * the frame: until `DoctypeSource` brings a sort control, the order is this
 * page's own dropdown and its own URL key — §C4.
 *
 * What it cannot do on a mount it *refuses*, with the reason, which is what
 * the header above prints beside the count and on the disabled order button.
 */
const source = computed(() => fileSource({
  place: place.value,
  folder: folder.value,
  // The refs and not their values, deliberately. A new source is a fresh
  // list, and the frame empties the search box when it gets one — so a source
  // that was rebuilt every time somebody sorted would clear what they had
  // typed. Place and folder *are* a fresh list; an order is not.
  sort: drive.sort,
  descending: drive.descending,
  can: can.value.declared(),
  empty: emptyFace.value,
  // The breadcrumb is not a row, so it comes off the answer rather than out
  // of the list.
  onAnswer: drive.walked,
}))

// --------------------------------------------------------------------------
// Getting files in
// --------------------------------------------------------------------------

const uploads = useUploads()
const chooser = ref(null)

// A finished upload lands in a folder somebody may be looking at. Re-reading
// the place rather than pushing a row in: the server decided the name, the size
// and whether the quota allowed it at all.
uploads.onFinished((one) => {
  if (one.folder === (folder.value || 'Home')) drive.load()
})

function chosenFiles(event) {
  uploads.add([...(event.target.files || [])], { folder: folder.value || 'Home' })
  // Reset, so choosing the same file twice fires twice.
  event.target.value = ''
}

/**
 * Files from the desktop, into whatever folder is open.
 *
 * The two places they may not go are declared on the directive rather than
 * checked here: the bin, and a mount — which is read-only through the Drive,
 * and used to upload into whatever folder the URL happened to name, which
 * there is not a folder.
 */
function dropped(files) {
  uploads.add(files, { folder: folder.value || 'Home' })
}

/** A row dropped on a folder row. */
function moveInto(target, names) {
  const moving = drive.files.value.filter((one) => names.includes(one.name))
  if (moving.length) drive.move(moving, target.name)
}

// One menu for the whole list, filled by whichever row was end-clicked —
// frappe-ui's own pattern, and why there is not a menu instance per row.
const rowMenu = ref([])

const placeName = computed(() => labelOf(place.value))
const placeOptions = computed(() =>
  PLACES.map((one) => ({
    label: one.label,
    icon: one.icon,
    route: { name: 'Drive', query: { place: one.value } },
  })),
)

// One root, then the place, then the folders — §C1. The phone case that used
// to drop the "Files" crumb is gone: frappe-ui collapses the trail to its
// last two with an ellipsis menu when it runs out of room, which is a better
// answer than a surface deciding for itself which of its crumbs is expendable.
const crumbs = useCrumbs(
  () => ({ label: __('Files'), route: { name: 'Drive', query: { place: place.value } } }),
  () => drive.path.value.map((one) => ({
    label: one.label,
    route: { name: 'Drive', query: { place: 'home', folder: one.name } },
  })),
)

/*
 * What a place can be put in order by, and what each is called.
 *
 * Four, and not every column the server would allow: a sort control is a list
 * you read every time you open it, and the fifth entry is the one that makes
 * you read rather than recognise. Kind is in it because "show me the sheets"
 * is a real question in a folder of forty attachments, and grouping by it is
 * the nearest thing to an answer this list has.
 *
 * The empty key is the place's own — Home leads with folders and then names,
 * Recents with what was opened last — and it is first, because "however this
 * place normally is" is where most people want to be.
 */
const ORDERS = [
  { key: '', label: __('However this place is'), icon: 'lucide-sparkles' },
  { key: 'name', label: __('Name'), icon: 'lucide-case-sensitive' },
  { key: 'modified', label: __('Last changed'), icon: 'lucide-clock' },
  { key: 'size', label: __('Size'), icon: 'lucide-hard-drive' },
  { key: 'kind', label: __('Kind'), icon: 'lucide-shapes' },
]

const orderName = computed(
  () => ORDERS.find((one) => one.key === drive.sort.value)?.label || ORDERS[0].label,
)

const orderOptions = computed(() => ORDERS.map((one) => ({
  label: one.label,
  icon: one.icon,
  // Ticked rather than only bolded: a menu of five where one is in force is a
  // menu that has to say which, and the arrow on the button says only which
  // way round it is.
  selected: one.key === drive.sort.value,
  onClick: () => drive.orderBy(one.key),
})))

const counted = computed(() => {
  const shown = drive.files.value.length
  const chosenNow = chosenCount.value
  if (chosenNow) return __('{0} of {1} chosen', [chosenNow, shown])
  // Whole sentences rather than a number glued to a word: the plural and the
  // "and there is more" are one phrase in some languages and two in others.
  if (list.value?.more) {
    return shown === 1
      ? __('1 thing, more below')
      : __('{0} things, more below', [shown])
  }
  return shown === 1 ? __('1 thing') : __('{0} things', [shown])
})

// What the folder somebody is in is called, for the share dialog's sentence
// about what a key reaches. The breadcrumb already knows.
const folderLabel = computed(
  () => drive.path.value[drive.path.value.length - 1]?.label || __('the whole Drive'),
)

/**
 * What this place can do, and why not where it cannot — §F1.
 *
 * A mount was four `inRemote` checks scattered through the template, each
 * one an omission with its reason in a code comment rather than on screen.
 * Declared here instead, once, in the vocabulary every list surface will use
 * when §B1 lands: a reason means the control is drawn and disabled and says
 * why, which is the difference between "the Drive has no sorting" and "this
 * host answers in its own order".
 */
const can = computed(() => offers(inRemote.value
  ? {
    [CAN.SEARCH]: true,
    [CAN.SORT]: __('This host answers in its own order.'),
    [CAN.BULK]: __('The Drive reads a host, it does not write to one.'),
    // Not refused, absent: the toolbar offers Check again in New's place,
    // which is a better answer than a disabled button — §F1's third state.
  }
  : place.value === 'records'
    ? {
      [CAN.SEARCH]: true,
      // A directory made out of a query has nothing to make in it and no
      // order but the one the query came back in. Said rather than left
      // absent — §F1's middle state — because a control that vanishes in one
      // place is a control people stop trusting everywhere.
      [CAN.SORT]: __('The record list\'s own order.'),
      [CAN.BULK]: true,
      [CAN.CREATE]: __('Attach a file to a record.'),
    }
    : {
      [CAN.SEARCH]: true,
      [CAN.SORT]: true,
      [CAN.BULK]: true,
      [CAN.CREATE]: true,
    }))

// What an empty list means here. A mount has its own answer — "nothing here
// yet, upload a file" is advice you cannot take on somebody else's server.
const emptyFace = computed(() => {
  if (inRemote.value) {
    return {
      icon: 'lucide-server',
      title: __('This folder is empty'),
      description: __('Nothing on the host at this path right now.'),
    }
  }
  const ICON = {
    trash: 'lucide-trash-2',
    records: 'lucide-boxes',
    documents: 'lucide-file-text',
    workbooks: 'lucide-table',
  }
  return {
    icon: ICON[place.value] || 'lucide-folder-open',
    ...EMPTY[place.value],
  }
})

// The URL first, then the browser's memory — the same split the order has.
// A link that says `?as=grid` arrives as a grid whoever opens it; a visit
// that says nothing gets what this person last chose. Sending somebody a
// folder of drawings and having it arrive as a list of filenames because
// *their* browser prefers lists is the thing this fixes.
// `docs/UNIFICATION.md` §C4.
const grid = ref(
  route.query.as ? route.query.as === 'grid' : recall('drive.grid') === '1',
)
function setGrid(wanted) {
  grid.value = wanted
  remember('drive.grid', wanted ? '1' : '0')
  // `replace`: switching to thumbnails is not a place to go back to. And the
  // list is the default, so it is an absent key rather than `as=list`.
  const query = { ...route.query }
  if (wanted) query.as = 'grid'
  else delete query.as
  router.replace({ query })
}
// Which file the dialogs are about. One ref, because only one of them is open.
const looking = ref(null)
const previewing = ref(false)

/*
 * The kinds the pane opens rather than the router.
 *
 * A sheet and a document, because both have an editor that fits a column and
 * because opening one is the commonest thing anybody does in a file manager —
 * walking away from the list to do it is what makes a file manager feel like a
 * detour. Everything else either has no editor of ours or is a place with an
 * address, and both of those still navigate.
 */
// The kinds that open in the pane instead of on their own page — and only on
// a desktop. On a phone the pane is a full-screen overlay, so opening a sheet
// in it buys nothing the page does not already give and costs the URL and the
// back button. So there the row stays what it looks like: a link.
//
// Kinds and not editors, because this is what a `FileRow` has: `editorFor`
// answers from a whole file and the row is deciding before it opens one. `Code`
// carries every `.py` and `.sql`; the text kinds a `.txt` and a `.log`, which
// `custom_kind` calls Document — so the pane takes a Document only when
// `editorFor` says there is an editor behind it, which `mounts` below settles.
const INLINE = ['Sheet', 'Doc', 'Code', 'Document']

// Wider when the pane holds an editor. Four hundred and eighty pixels is a
// preview; it is not a spreadsheet, and a person who has to drag the resizer
// before they can read a row has been handed a chore rather than a feature.
//
// As the pane's *minimum* rather than by setting its width: the Resizer takes
// the remembered width on mount, so anything written before that is overwritten
// a frame later. A floor is declarative, survives the mount, and still lets
// somebody drag wider.
//
// A share of the window and not 860 flat. 860 on a 1280 laptop leaves the list
// 180 pixels — every name truncated to nothing, which is a file manager you
// cannot pick the next file from. Half the window, up to 860: six columns on a
// laptop and a proper grid on a large screen, and the list stays a list.
//: What the list keeps whatever is open beside it. Below this a row is dates
//: and a truncation, and picking the next file — the only reason the list is
//: still on screen — stops working.
const LIST_FLOOR = 420

const editorFloor = () => {
  const half = Math.max(560, window.innerWidth * 0.5)
  // The sidebar is outside this pane's window share, so the room to leave the
  // list is measured off what the content column actually has.
  const spare = window.innerWidth - LIST_FLOOR - 260
  return Math.round(Math.max(480, Math.min(860, half, spare)))
}

// Which editor the pane mounts, from the one function that decides it. A
// Document whose bytes nothing can edit — a `.docx` — comes back null and gets
// the previewer, which is the whole reason this is not `INLINE.includes`.
const mounts = computed(() => {
  const editor = editorFor(looking.value)
  return editor === 'sheet' ? 'sheet' : (editor ? 'doc' : '')
})

const editing = computed(() => !!mounts.value)

const lookingRemote = computed(() => isRemote(looking.value?.name))

// Which mount the page is inside, and what can be done to it from here.
// `connections` and not `mounts`: `mounts` above is which editor the pane
// mounts, and two things called the same word in one file is one of them
// getting read as the other.
const here = computed(() => mountOf(folder.value))
const connections = ref([])
const loadConnections = async () => {
  connections.value = (await workspace.driveMounts().catch(() => null)) || []
}

const mountOptions = computed(() => {
  const paused = connections.value.find((one) => one.name === here.value)?.status === 'Paused'
  return [
    {
      label: paused ? __('Start reading again') : __('Pause this connection'),
      icon: paused ? 'lucide-play' : 'lucide-pause',
      onClick: async () => {
        await workspace.drivePauseMount(here.value, !paused)
        await loadConnections()
        drive.load()
      },
    },
    {
      // Into the settings dialog rather than a dialog of the Drive's own —
      // §C2. Configuring a mount is the same act as configuring anything else
      // in this workspace, and it now happens where the rest of it does.
      label: __('Connection settings'),
      icon: 'lucide-settings-2',
      onClick: () => openSettings('connections'),
    },
    {
      label: __('Disconnect'),
      icon: 'lucide-unplug',
      onClick: async () => {
        await workspace.driveDisconnect(here.value)
        router.push({ name: 'Drive', query: { place: 'home' } })
      },
    },
  ]
})

/**
 * Bring a file across, into the folder the person came from.
 *
 * `Home` and not the mount: the mount is where the file is, and where it is
 * going is the Drive. Somewhere more specific would need a folder picker, and
 * the file is a move away once it is here.
 */
async function copyHere(file) {
  copying.value = true
  try {
    await workspace.driveCopyHere(file.name)
  } finally {
    copying.value = false
  }
}

const sharing = ref(false)
const naming = ref(false)
const renaming = ref(false)
const moving = ref(false)
const emptying = ref(false)
const sharingOverDav = ref(false)
const copying = ref(false)
const folderName = ref('')
const newName = ref('')
const toMove = ref([])
const importing = ref(false)

// Anything with an address is a link and navigates itself — a folder, a sheet,
// a document, a text file. What is left is the files that are looked at rather
// than opened, and looking is what this does: the download is one button
// further in, which is the right way round.
function open(file) {
  looking.value = file
  previewing.value = true
}

// The only things in this product that are made rather than uploaded, shared
// with the record's Files tab. Importing a spreadsheet is the Drive's alone:
// it opens a dialog this page owns.
const { making, options: newOptions, choosingLanguage, newText, loadTemplates } = useNewFile(
  () => ({ folder: folder.value || '' }),
  () => [{
    label: __('Import a spreadsheet'),
    icon: 'lucide-file-up',
    onClick: () => { importing.value = true },
  }],
)

/**
 * The New menu, with a folder at the top of it.
 *
 * A folder is the Drive's alone — a record's Files tab has folders nowhere to
 * put them — so it is added here rather than in `useNewFile`, which both
 * surfaces share. Ungrouped and first, which the Menu turns into a group of
 * its own with a rule under it: a folder is not something you write and not
 * something you calculate, and giving it a heading of its own for one row is
 * more furniture than the row is worth.
 */
const makeOptions = computed(() => [
  {
    label: __('New folder'),
    icon: 'lucide-folder-plus',
    onClick: () => { naming.value = true },
  },
  ...newOptions.value,
  // Last, and deliberately in this menu rather than beside the rail's
  // Connected heading: everything that brings files into the Drive is behind
  // one button, and an FTP server is one more way of bringing them in.
  {
    group: __('Elsewhere'),
    options: [
      {
        label: __('Connect a folder'),
        icon: 'lucide-server',
        onClick: () => openSettings('connections'),
      },
      // The mirror of it, in the same group and for the same reason: both are
      // about this Drive and somewhere else, and a person looking for one
      // finds the other.
      {
        label: __('Share over WebDAV'),
        icon: 'lucide-share-2',
        onClick: () => { sharingOverDav.value = true },
      },
    ],
  },
])

function startShare(file) {
  looking.value = file
  sharing.value = true
}

function startRename(file) {
  looking.value = file
  newName.value = file.file_name || ''
  renaming.value = true
}

function startMove(what) {
  toMove.value = what
  moving.value = true
}

async function intoFolder(into) {
  await drive.move(toMove.value, into)
  list.value?.clearChosen()
}

async function makeFolder() {
  const title = folderName.value.trim()
  if (!title) return
  await drive.newFolder(title)
  if (!drive.error.value) {
    naming.value = false
    folderName.value = ''
  }
}

async function finishRename() {
  const title = newName.value.trim()
  if (!title || !looking.value) return
  await drive.rename(looking.value, title)
  if (!drive.error.value) renaming.value = false
}

async function finishEmpty() {
  await drive.emptyBin()
  emptying.value = false
}

// No first read here either: the frame does it when it gets its source.
onMounted(() => {
  loadTemplates()
  loadConnections()
})
</script>
