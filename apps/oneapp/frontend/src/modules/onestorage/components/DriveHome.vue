<template>
  <!--
    What OneCloud opens on.

    It opened on All files, which on a real workspace is fifty rows of folders
    in alphabetical order — a directory listing, which is a thing you consult
    and not a thing you land on. Every file manager on the reference board has
    stopped doing that: Windows 11 opens on Home, Google Drive opens on Home,
    and both answer the same question, which is *what were you doing*.

    Three bands and no fourth. Pinned, because a favourite is somebody saying
    "this one" out loud and it is the only such statement we have. Recent,
    because it is the answer nine times in ten. Shared, which draws nothing at
    all where nobody has shared anything — a heading over an empty list is a
    feature telling you it has nothing.

    No second store and no new endpoint: each band is `fileSource` over one of
    the places the rail used to spend an entry on, which is what §B1 is for —
    the skeleton, the empty state and the failed read are the frame's, here as
    everywhere. What Home *is*, is the argument that three short lists beat
    three destinations.
  -->
  <div data-slot="drive-home" class="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto">
    <!--
      Pinned, as tiles rather than rows.

      A folder is a place, and a place is something you aim a pointer at — a
      row is for comparing, which is not what you do with six things you chose
      on purpose. `auto-fill` for the same reason the Drive's own grid uses it:
      this is a window, and how many fit is a question about the pane and not
      about the screen.

      Its `#empty` is nothing, not an empty state: a workspace where nobody has
      hearted anything should have no Pinned band, rather than a heading over a
      panel explaining what hearts are.
    -->
    <section v-show="likedList?.rows?.length">
      <h2 :class="HEADING">{{ __('Pinned') }}</h2>
      <DataList
        ref="likedList"
        :source="pinned"
        :skeleton="0"
        :page-length="FEW"
        body-class="grid grid-cols-[repeat(auto-fill,minmax(11rem,1fr))] gap-2"
      >
        <template #empty><span /></template>
        <template #row="{ row: one }">
          <Panel
            as="button"
            pad="tight"
            type="button"
            data-slot="drive-home-pin"
            class="flex items-center gap-2 text-start"
            :class="HOVER"
            @click="emit('open', one)"
          >
            <FileFace :file="one" :meta="false" />
          </Panel>
        </template>
      </DataList>
    </section>

    <section>
      <h2 :class="HEADING">{{ __('Recent') }}</h2>
      <!--
        The Drive's own row, not a smaller one. A file here opens the way a
        file opens anywhere, which is the rule this module is built on.

        `columns` is off because a band of eight rows is a glance rather than a
        table to sort, and `dense` because the size and the date are already
        under the name — the row's own owner and date cells would be the same
        two facts a second time, at the other end of the same line.
      -->
      <DataList :source="recent" :skeleton="4" :page-length="FEW">
        <template #row="{ row: one }">
          <FileRow
            :file="one"
            :actions="false"
            :folder-link="false"
            dense
            @open="emit('open', one)"
          />
        </template>
      </DataList>
    </section>

    <section v-show="sharedList?.rows?.length">
      <h2 :class="HEADING">{{ __('Shared with you') }}</h2>
      <DataList
        ref="sharedList"
        :source="shared"
        :skeleton="0"
        :page-length="4"
      >
        <template #empty><span /></template>
        <template #row="{ row: one }">
          <FileRow
            :file="one"
            :actions="false"
            :folder-link="false"
            dense
            shared
            @open="emit('open', one)"
          />
        </template>
      </DataList>
    </section>
  </div>
</template>

<script setup>
import { ref } from 'vue'

import DataList from '@/shared/components/DataList.vue'
import Panel from '@/shared/components/Panel.vue'
import FileFace from '@/modules/onestorage/components/FileFace.vue'
import FileRow from '@/modules/onestorage/components/FileRow.vue'
import { CAN } from '@/shared/lib/capability'
import { fileSource } from '@/shared/lib/list/files'
import { HOVER } from '@/shared/lib/rowstate'
import { __ } from '@/shared/lib/runtime/translate'

/** The three headings, which are the same heading three times. */
const HEADING = 'mb-2 text-p-sm font-medium text-ink-secondary'

/** How many of each. Eight is a glance; a ninth is a list. */
const FEW = 8

const emit = defineEmits(['open'])

/**
 * The two optional bands, so a section with nothing in it draws nothing.
 *
 * `v-show` and not `v-if`: the list has to mount to find out whether it is
 * empty, and a section hidden this way is skipped by the column's own gap —
 * so a workspace where nobody has hearted anything has no Pinned band at all
 * rather than a heading over a panel explaining what hearts are.
 *
 * The rows are read back off the frame rather than counted here. `DataList`
 * exposes them, which is the whole of what a caller needs to know about a
 * list it did not fetch.
 */
const likedList = ref(null)
const sharedList = ref(null)

/**
 * A band: one place, and no box of its own.
 *
 * `fileSource` offers search because most of its callers are a whole screen
 * over one list. Home is three bands, and three search boxes stacked down a
 * landing page — one per heading — is the shape this window spent the evening
 * getting rid of. The box is in the path bar above, once, and on Home it takes
 * you to All files carrying what you typed.
 */
const band = (place, empty = {}) => fileSource({
  place,
  empty,
  can: { [CAN.SEARCH]: false },
})

const pinned = band('favourites')
const recent = band('recents', {
  title: __('Nothing opened yet'),
  description: __('Files you open show up here.'),
})
const shared = band('shared')
</script>
