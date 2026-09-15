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
      <!--
        Only where there are no column heads to sort from.

        A list sorts by clicking the word at the top of the column, which is
        what every list screen here does and what a person expects of a table.
        A grid has no columns, so it keeps the menu — and the menu is also the
        only home for the two orders that are not columns, `Default` and
        `Kind`. Two controls for one job on one screen is the thing worth
        avoiding; one control on the screen that has no other is not.

        One or the other, never both: `icon` is what makes a Button icon-only
        and `icon-left` is what puts one beside a label, so setting the pair
        drew the arrow twice on a phone.
      -->
      <Dropdown v-if="grid" :options="orderOptions">
        <Button
          variant="ghost"
          data-slot="drive-order"
          :disabled="!can.can(CAN.SORT)"
          :icon-left="isMobile ? undefined : (drive.descending.value
            ? 'lucide-arrow-down-narrow-wide'
            : 'lucide-arrow-up-narrow-wide')"
          :label="isMobile ? undefined : __('Sort')"
          :icon="isMobile
            ? (drive.descending.value
              ? 'lucide-arrow-down-narrow-wide'
              : 'lucide-arrow-up-narrow-wide')
            : undefined"
          :tooltip="can.why(CAN.SORT) || __('Sorted by {0}', [orderName])"
        />
      </Dropdown>

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
    <!--
      A floor under the list, and it is not decoration.

      `Resizer` clamps the pane to a share of `window.innerWidth`, which was a
      fair reading of "45% of the screen" while the Drive was a list and a
      pane. With the assistant open it is a third thing taking 400px of that
      window, and the arithmetic left the list about seventy pixels — enough
      for a tick and a format mark, and nothing at all for the name, which is
      the one thing a file list is for.

      `min-w-[18rem]` makes the list the thing that does not give. The pane is
      a fixed width in a flex row and shrinks when the row overflows, which is
      the right way round: a preview at 500px is a preview, a file list at 70
      is a column of checkboxes.

      The deeper version of this is `Resizer` measuring the window rather than
      the space it is actually in — the same mistake the grid's `auto-fill`
      comment above describes, in a shared component that record panes and both
      editors also use. This floor is the local half of it.
    -->
    <div
      class="flex min-w-[18rem] flex-1 flex-col rounded-6 bg-surface-base p-5"
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
      <!--
        One rounded box around the head, the rows and the total.

        The band's top corners are the box's, clipped — which is how a screen
        gets them too, its `List` sitting inside a rounded card. Doing it on
        the band instead wants `rounded-t-6`, and this product names four
        radii and no half of one: `test_every_radius_is_one_of_the_four_we_named`
        refuses it, correctly. A corner is a property of a container.
      -->
      <div class="flex min-h-0 flex-1 flex-col overflow-hidden rounded-6">
      <ContextMenu :options="rowMenu">
      <DataList
        ref="list"
        v-model:searched="searched"
        :source="source"
        :skeleton="8"
        :page-length="PAGE"
        class="min-h-0 flex-1 overflow-y-auto"
        :body-class="grid
          ? 'grid grid-cols-[repeat(auto-fill,minmax(10.625rem,1fr))] items-start gap-3'
          : 'flex flex-col'"
      >
        <template #header="{ allPicked, toggleAll }">
        <!--
          The search box, over the list rather than up in the page header.
          §B1 leaves the box's place to the caller — `v-model:searched` is the
          frame saying "my box, my place" — and beside Upload and New was the
          wrong place for it: those make things and this narrows them. A list
          screen keeps its box over its rows, and so does this now.
        -->
        <ListSearch
          v-model="searched"
          class="w-full md:w-64"
          :placeholder="__('Search files')"
          @changed="list?.read()"
        />

        <!--
          The grid keeps a line of its own: it has no column heads to hang a
          select-all on, and "everything here" is still a thing to ask of
          thumbnails. The count sits with it rather than below, because a grid
          has no footer rule to sit under.
        -->
        <!-- A squeezed list has no columns under the header either, so it gets
             the compact line rather than a rule captioned with four words for
             cells that are not being drawn. -->
        <div
          v-if="grid || squeezed"
          class="flex w-full items-center gap-2 pb-1 text-xs text-ink-muted"
        >
          <template v-if="can.can(CAN.BULK)">
            <Checkbox
              :model-value="allPicked"
              :aria-label="__('Select everything here')"
              class="ms-2.5"
              @update:model-value="toggleAll"
            />
            <span>{{ counted }}</span>
          </template>
          <template v-else-if="can.why(CAN.BULK)">
            <span>{{ counted }}</span>
            <span class="text-ink-muted">· {{ can.why(CAN.BULK) }}</span>
          </template>
          <span v-else>{{ counted }}</span>
        </div>

        <!--
          The column heads, banded like a screen's.

          `h-9`, `bg-surface-gray-1` and a bottom hairline on `outline-gray-2`
          are `RecordTable`'s `BAND`, which is what a list screen's header
          wears. Copied rather than imported for the reason the values are
          here at all: that band is applied through `[&_[data-slot=…]]`
          selectors onto frappe-ui's `List`, and this list is not one.

          The select-all lives *in* the band, at the head of the column it
          ticks, which is where every screen in this product keeps it — it used
          to float on a line above with the count beside it, which is a shape
          no screen here has.

          Widths match `FileRow`'s cells exactly, and each head hides at the
          same breakpoint as the cell under it. Below `md` the whole row goes:
          only Name would be left, and a header of one word above a list is a
          rule with a caption.
        -->
        <div
          v-else
          data-slot="drive-heads"
          class="hidden h-9 w-full items-center gap-2 border-b border-outline-gray-2 bg-surface-gray-1 pe-2 text-sm text-ink-muted md:flex"
        >
          <Checkbox
            v-if="can.can(CAN.BULK)"
            :model-value="allPicked"
            :aria-label="__('Select everything here')"
            class="ms-2.5"
            @update:model-value="toggleAll"
          />
          <span v-else class="ms-2.5 size-4 shrink-0" />

          <!--
            The heads are frappe-ui's own, which is what a list screen's header
            is made of: a real button, `aria-sort`, an "Order by name" tooltip,
            and an arrow that stays hidden until the pointer is over the column
            it would order. That last part is the difference between a header
            that says how the list is sorted and one that says every column
            could sort it, which is what three permanent glyphs were saying.

            A place that cannot be ordered draws the plain cell rather than a
            button that refuses: a remote mount answers in the host's own order
            and there is nothing there to disable.
          -->
          <ListHeaderCellSort
            v-if="sorts"
            :direction="directionFor('name')"
            class="min-w-0 flex-1 px-2"
            @click="drive.orderBy('name')"
          >
            {{ __('Name') }}
          </ListHeaderCellSort>
          <ListHeaderCell v-else class="min-w-0 flex-1 px-2">
            {{ __('Name') }}
          </ListHeaderCell>

          <div class="flex shrink-0 items-center gap-1">
            <!-- Two: the heart and the download. Neither has a label and both
                 take width, so a header that counts one sits a button left of
                 its own columns. -->
            <span class="size-7 shrink-0" />
            <span class="size-7 shrink-0" />
            <span class="hidden w-36 shrink-0 items-center lg:flex">{{ __('Owner') }}</span>
            <ListHeaderCellSort
              v-if="sorts"
              :direction="directionFor('modified')"
              class="hidden w-28 shrink-0 md:flex"
              @click="drive.orderBy('modified')"
            >
              {{ __('Last changed') }}
            </ListHeaderCellSort>
            <ListHeaderCell v-else class="hidden w-28 shrink-0 md:flex">
              {{ __('Last changed') }}
            </ListHeaderCell>

            <!--
              `align="end"` moves the glyph to the leading side as well as
              right-aligning the words, so "Size" stays flush with the figures
              under it instead of being pushed off the edge by its own arrow.
            -->
            <ListHeaderCellSort
              v-if="sorts"
              align="end"
              :direction="directionFor('size')"
              class="hidden w-20 shrink-0 justify-end md:flex"
              @click="drive.orderBy('size')"
            >
              {{ __('Size') }}
            </ListHeaderCellSort>
            <ListHeaderCell v-else class="hidden w-20 shrink-0 justify-end md:flex">
              {{ __('Size') }}
            </ListHeaderCell>
            <span class="size-7 shrink-0" />
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
          many cards fit *here*. Nothing to recalculate on resize and no
          breakpoint to keep in step with the pane's width.

          The floor is 10.625rem, which is frappe/suite's 170px and is theirs
          rather than ours on purpose: it is the width their card was drawn
          for, and the card is theirs now. It was 12rem while the foot held two
          verbs and a sentence on one line; the verbs have moved onto the
          picture and the sentence under the name, so the card needs the height
          it has and less of the width.

          `items-start` because folders and files are different heights and
          share this grid: without it a row of folder chips stretches each chip
          to the height of the tallest thing in its row, which in a mixed row
          is a card.
        -->
        <!-- Renamed on the way in, both of them. `rows` and `picked` are also
             the names of two computeds in this file, and the slot's `picked` is
             not even the same *kind* of thing as the outer one — a boolean for
             this row against the list of what is chosen. Shadowing that reads
             as the same value twice. -->
        <template #row="{ row: file, index, rows: shown, picked: chosen, toggle }">
          <!--
            Folders, then everything else — the shape every file manager has
            and the one this list was already in without saying so. `ordering`
            puts `FOLDERS_FIRST` ahead of whichever column is sorted, so the
            two runs hold under every order and the heading never lands in the
            middle of one.

            `col-span-full` because in the grid this is a cell in a CSS grid
            and would otherwise take one card's width.
          -->
          <p
            v-if="sectionAt(index, shown)"
            data-slot="drive-section"
            class="col-span-full px-2 pb-1 pt-3 text-xs font-medium uppercase tracking-wide text-ink-muted first:pt-0"
          >{{ sectionAt(index, shown) }}</p>

          <FileRow
            :file="file"
            :place="place"
            :link="routeFor(file)"
            :inline="isMobile ? [] : INLINE"
            :dense="squeezed"
            :grid="grid"
            :shared="place === 'shared'"
            :columns="!grid && !squeezed"
            selectable
            actions
            movable
            :selected="chosen"
            :trashed="place === 'trash'"
            @menu="(options) => (rowMenu = options)"
            @move-into="moveInto"
            @open="open"
            @select="toggle"
            @favourite="drive.favourite"
            @share="startShare"
            @download="downloadOne"
            @copy="copyHere"
            @rename="startRename"
            @move="(one) => startMove([one])"
            @trash="(one) => drive.trash(one)"
            @restore="(one) => drive.restore(one)"
            @destroy="(one) => drive.destroy(one)"
          />
        </template>
      </DataList>

      <!--
        How many, under the rows.

        A screen says "43 of 43" in a footer and this said "3 things" above the
        first one, which put a total where a heading goes and pushed the list
        down a line to do it. Same place now, same job — including the end it
        sits at, because a total that reads right-to-left across an empty rule
        is a total somebody hunts for. The grid keeps its own copy in the line
        above, having no rule to sit under.

        `shrink-0` because the list above it is the part that scrolls.
      -->
      <div
        v-if="!grid"
        data-slot="drive-footer"
        class="flex shrink-0 items-center justify-end gap-2 border-t border-outline-gray-2 px-2 py-2 text-xs text-ink-muted"
      >
        <span>{{ counted }}</span>
        <span v-if="can.why(CAN.BULK)">· {{ can.why(CAN.BULK) }}</span>
      </div>
      </ContextMenu>
      </div>
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
          `hosted`, so the editor draws a bar of its own rather than teleporting
          its title into the shell's header, above the list it is sitting
          beside. The way out is this pane's own Close; neither editor draws
          one, which is what stopped a `.py` pushing `/one/files` and taking
          the list with it.
        -->
        <Doc
          v-else
          :key="looking.name"
          :name="looking.name"
          hosted
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
import { useAiContext } from '@/shared/lib/ai/context'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Alert,
  Button,
  Checkbox,
  ContextMenu,
  Dialog,
  Dropdown,
  FormControl,
  ListHeaderCell,
  ListHeaderCellSort,
  PageHeader,
} from '@/ui'
import Trail from '@/shared/components/Trail.vue'
import { useCrumbs } from '@/shared/composables/useCrumbs'
import { CAN, offers } from '@/shared/lib/capability'
import DataList from '@/shared/components/DataList.vue'
import SelectionBar from '@/modules/onespace/components/screen/bodies/SelectionBar.vue'
import { PAGE, fileSource } from '@/shared/lib/list/files'
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
  downloadUrl, editorFor, isRemote, mountOf, routeFor,
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
    description: __('Upload a file, or make a folder.'),
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
    description: __('Files people share with you appear here.'),
  },
  trash: {
    title: __('The bin is empty'),
    description: __('Deleted files wait thirty days.'),
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
  code: {
    title: __('No code yet'),
    description: __('Make one with New.'),
  },
  templates: {
    title: __('No templates yet'),
    description: __('Mark a file as a template.'),
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
//
// Which makes this list the *gate*, not just the copy — and that is how
// Templates spent several stages quietly showing All files. It is in the rail,
// it highlights when you click it, the crumb says "Files" and the rows are
// everybody's: no error, no empty state, nothing to notice except that the
// answer is wrong. A guard reads `places.js` back against this now.
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
  if (one.folder === (landing().folder || 'Home')) drive.load()
})

/**
 * Where an uploaded file goes from here.
 *
 * Two shapes, because the top of a record's room is not a folder. The levels
 * above a room are a query and the room itself is addressed by the record, so
 * a file dropped there is *attached* rather than filed — which is what it
 * would have been if somebody had dropped it on the record's own Files tab,
 * and is the whole point of the room being a place.
 *
 * A folder *inside* a room is an ordinary folder again: its id is real, the
 * file is filed into it, and the server takes the room off the folder on the
 * way in (`file.py`). So a room needs no special case below its own top.
 */
function landing() {
  if (room.value) {
    return { folder: '', attachTo: { doctype: room.value.doctype, docname: room.value.docname } }
  }
  return { folder: folder.value || 'Home' }
}

function chosenFiles(event) {
  uploads.add([...(event.target.files || [])], landing())
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
  uploads.add(files, landing())
}

/** A row dropped on a folder row. */
function moveInto(target, names) {
  const moving = drive.files.value.filter((one) => names.includes(one.name))
  if (moving.length) drive.move(moving, target.name)
}

// One menu for the whole list, filled by whichever row was end-clicked —
// frappe-ui's own pattern, and why there is not a menu instance per row.
const rowMenu = ref([])

/**
 * Where in the Records tree this is, as its parts.
 *
 * `Quotation`, then `QTN-0001`, then any folders under it. The first two are a
 * doctype and a primary key; everything after them is a real `File` row whose
 * id *is* this path — `onestorage/file.py` names the top of a room after the
 * room, so nothing has to be looked up to turn one into the other.
 */
const recordPath = computed(() => (
  place.value === 'records' ? folder.value.split('/').filter(Boolean) : []
))

/**
 * Whether this is a record's room rather than one of the two queries above it.
 *
 * A room is a place: it has rows, it takes a folder, it sorts. The levels
 * above are a `group by` wearing a directory's shape and have nothing to make
 * in them, which is what `can` says out loud.
 */
const inRoom = computed(() => recordPath.value.length >= 2)

/**
 * The record a new folder would belong to, where there is no parent folder to
 * make it inside.
 *
 * Only at the top of a room. One folder deeper there *is* a parent, its id is
 * the path, and the server takes the room off it — which is also what keeps a
 * subfolder from being a quiet way out of the permission the room hangs off.
 */
const room = computed(() => (
  recordPath.value.length === 2
    ? { doctype: recordPath.value[0], docname: recordPath.value[1] }
    : null
))

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
/**
 * Where you are, said out loud.
 *
 * Two entries and not one: the first *becomes* the house — `useCrumbs` reads
 * it that way — and the second is the place inside it. Passing only the first
 * left the trail as a house glyph and nothing else, so this was the one page
 * in the product that did not say where it was. The rail said it, in a chip
 * nobody reads as a title, and the header said nothing at all.
 *
 * It is also what a folder's path hangs off: at the root of Recents the trail
 * is `⌂ / Recent`, and three folders into Home it is `⌂ / All files / … `.
 */
const crumbs = useCrumbs(
  () => [
    { label: __('Files'), route: { name: 'Drive', query: { place: place.value } } },
    { label: placeName.value, route: { name: 'Drive', query: { place: place.value } } },
  ],
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
  { key: '', label: __('Default'), icon: 'lucide-sparkles' },
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

/** Whether this place can be ordered at all, which decides what a head is. */
const sorts = computed(() => can.value.can(CAN.SORT))

/**
 * One head's direction, or `null` for the columns that are not in force.
 *
 * `ListHeaderCellSort` reads both its glyph and its `aria-sort` off this, so a
 * screen reader and a pointer are told the same thing from one place.
 */
const directionFor = (key) => (
  drive.sort.value !== key ? null : drive.descending.value ? 'desc' : 'asc'
)

/**
 * The file itself, through the door that checks who is asking.
 *
 * `r2.download` is the endpoint whose permission check is the whole reason it
 * exists — objects are never publicly reachable — so this is a window on it
 * and not a link to a bucket. The same call `FilePane` makes, because a row
 * and the pane it opens must not have two ideas about what downloading is.
 */
const downloadOne = (file) => window.open(downloadUrl(file.name), '_blank')

/**
 * The heading this row starts, if it starts one.
 *
 * A boundary and not a property: the first row of the list opens whichever
 * section it belongs to, and a file opens `Files` only where the row above it
 * was a folder. Everything else answers nothing and draws nothing.
 *
 * Silent when a place has no folders in it — Recents, Favourites and the bin
 * are one run of files, and a lone `Files` heading over a list that has no
 * other kind in it is a label for nothing.
 */
function sectionAt(index, rows) {
  const file = rows?.[index]
  if (!file || !rows?.some((one) => one.is_folder)) return ''
  if (file.is_folder) return index === 0 ? __('Folders') : ''
  return index === 0 || rows[index - 1]?.is_folder ? __('Files') : ''
}

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
  : place.value === 'records' && !inRoom.value
    ? {
      [CAN.SEARCH]: true,
      // A directory made out of a query has nothing to make in it and no
      // order but the one the query came back in. Said rather than left
      // absent — §F1's middle state — because a control that vanishes in one
      // place is a control people stop trusting everywhere.
      //
      // The two levels above a room only. A room itself is a place with real
      // rows in it, and both of these work there — see `inRoom`.
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
  // A room is a place you can put things, so an empty one says so. The
  // Records place's own copy — "files attached to records appear here" — is
  // about the *tree*, and reading it inside a folder you just made is being
  // told where files come from while standing in the place you would put one.
  if (inRoom.value) {
    return {
      icon: 'lucide-folder-open',
      title: __('Nothing here yet'),
      description: __('Upload a file, or make a folder.'),
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

/**
 * Whether the list is sharing its width with the pane.
 *
 * `editing` was standing in for this and is a narrower question: it is true
 * only when the pane mounts an *editor*, so a previewed photograph left the
 * list drawing owner, date and size columns in the hundred pixels the pane had
 * left it — and what actually happened is that the name, which is the one
 * thing a file list is for, came out as nothing at all.
 *
 * Any open pane squeezes the list. Not on a phone, where the pane is the whole
 * screen and there is no list beside it to squeeze.
 */
const squeezed = computed(() => previewing.value && !isMobile.value)

const lookingRemote = computed(() => isRemote(looking.value?.name))

/**
 * What the assistant is about while the Drive is open.
 *
 * The file in the pane, when there is one, and nothing otherwise. A *place* is
 * not a context worth declaring: "Favourites" tells a model nothing it could
 * not find out with one tool call, and claiming it would only stop the panel
 * offering to talk about the workspace, which is the more useful answer while
 * you are looking at a list.
 *
 * A file on a mounted host is not one either — the server drops it, because
 * there is no `File` row behind it and no tool that could read one.
 */
useAiContext(() => (
  looking.value && !lookingRemote.value
    ? { file: looking.value.name, label: looking.value.file_name, kind: looking.value.custom_kind }
    : null
))

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
  // First, and no longer a button of its own. Everything that puts a file in
  // this place is behind one control now — uploading one, making one, and
  // connecting a folder full of them are three answers to "put something
  // here", and they were spread across two buttons and a menu.
  {
    label: __('Upload files'),
    icon: 'lucide-upload',
    onClick: () => chooser.value?.click(),
  },
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
  await drive.newFolder(title, room.value)
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
