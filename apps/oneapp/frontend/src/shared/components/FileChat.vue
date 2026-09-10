<template>
  <!--
    The conversation about a file, beside the file.

    Not the notes inside it. A sheet already has threads on cells and they are
    the right place for "this rate is wrong"; this is the other thing people
    want, which is "are these March's rates or April's?" — a question about
    the whole workbook, asked by somebody who would have to pick an arbitrary
    cell to attach it to.

    Frappe's `Comment` on the `File` row, so an `@` notifies the person named
    and the remark turns up in the same feed as one on a record —
    `onestorage/chatting.py` says why that mattered more than the storage did.

    Live over the same room the editor is in: a note posted in one browser
    lands in the other without a reload, and the room is shared rather than
    joined twice (`shared/lib/live/room.js`).
  -->
  <aside
    class="flex w-80 shrink-0 flex-col border-s border-outline-gray-1 bg-surface-base"
    :aria-label="__('Notes')"
    data-slot="file-chat"
  >
    <div class="flex shrink-0 items-center justify-between gap-2 border-b border-outline-gray-1 px-4 py-3">
      <p class="text-p-base font-medium text-ink-gray-8">{{ __('Notes') }}</p>
      <Button
        variant="ghost"
        icon="lucide-x"
        :label="__('Close notes')"
        :tooltip="__('Close')"
        @click="emit('close')"
      />
    </div>

    <FadedScroll ref="scroller" class="min-h-0 flex-1">
      <div v-if="loading" class="space-y-3 p-4">
        <Skeleton class="h-12 w-full" />
        <Skeleton class="h-12 w-full" />
      </div>

      <p v-else-if="!said.length" class="p-4 text-p-sm text-ink-gray-5">
        {{ __('Nothing said about this yet. Notes here are about the whole file — type @ to bring somebody in.') }}
      </p>

      <ul v-else class="space-y-3 p-4">
        <li v-for="one in said" :key="one.name" class="flex gap-2" data-slot="note">
          <Avatar :label="one.name_of" shape="circle" size="sm" class="mt-0.5 shrink-0" />
          <div class="min-w-0 flex-1">
            <div class="flex items-baseline gap-2">
              <span class="truncate text-p-sm font-medium text-ink-gray-8">{{ one.name_of }}</span>
              <span class="shrink-0 text-p-xs text-ink-gray-5">{{ when(one.at) }}</span>
              <Button
                v-if="one.mine"
                variant="ghost"
                size="sm"
                icon="lucide-trash-2"
                class="ms-auto shrink-0"
                :label="__('Remove this note')"
                :tooltip="__('Remove')"
                @click="remove(one)"
              />
            </div>
            <!-- `textContent`, not `v-html`. A note is written by somebody in
                 this workspace and rendering it as markup would be the same
                 mistake the mail reader exists to avoid. Frappe stores an
                 `@` mention as an anchor, so the tags are stripped rather
                 than shown. -->
            <p class="whitespace-pre-wrap break-words text-p-sm text-ink-gray-7">{{ plain(one.content) }}</p>
          </div>
        </li>
      </ul>
    </FadedScroll>

    <form class="shrink-0 border-t border-outline-gray-1 p-3" @submit.prevent="send">
      <FormControl
        v-model="draft"
        type="textarea"
        :rows="2"
        :placeholder="__('Say something about this file')"
        :disabled="busy"
        @keydown.enter.exact.prevent="send"
      />
      <div class="mt-2 flex items-center justify-between gap-2">
        <span class="text-p-xs text-ink-gray-5">{{ __('Enter to send') }}</span>
        <Button
          variant="solid"
          size="sm"
          :label="__('Send')"
          :loading="busy"
          :disabled="!draft.trim()"
          @click="send"
        />
      </div>
      <p v-if="failed" class="mt-2 text-p-xs text-ink-red-3">{{ failed }}</p>
    </form>
  </aside>
</template>

<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'

import { Avatar, Button, FormControl, Skeleton, dayjsLocal } from '@/ui'
import FadedScroll from '@/shared/components/FadedScroll.vue'
import { joinRoom } from '@/shared/lib/live/room'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'

// One event each way. A note is small enough to carry whole, so a peer
// appends what arrived rather than refetching the thread — which is the
// difference between one message and one message plus a round trip per
// person in the room.
const SAID = 'note_said'
const UNSAID = 'note_unsaid'

const props = defineProps({
  /** The File this is about. */
  name: { type: String, required: true },
})

const emit = defineEmits(['close', 'count'])

const said = ref([])
const draft = ref('')
const loading = ref(true)
const busy = ref(false)
const failed = ref('')
const scroller = ref(null)

let room = null

/** Frappe stores a mention as an anchor; nothing here renders markup. */
function plain(html) {
  const box = document.createElement('div')
  box.innerHTML = html || ''
  return box.textContent || ''
}

const when = (at) => dayjsLocal(at).fromNow()

function bottom() {
  nextTick(() => {
    const el = scroller.value?.$el || scroller.value
    const box = el?.querySelector?.('[data-faded-scroll]') || el
    if (box) box.scrollTop = box.scrollHeight
  })
}

function add(one) {
  if (!one?.name || said.value.some((each) => each.name === one.name)) return
  said.value = [...said.value, one]
  emit('count', said.value.length)
  bottom()
}

function drop(name) {
  said.value = said.value.filter((one) => one.name !== name)
  emit('count', said.value.length)
}

async function load() {
  loading.value = true
  try {
    const answer = await workspace.driveNotes(props.name)
    said.value = answer?.notes || []
    emit('count', said.value.length)
    bottom()
  } finally {
    loading.value = false
  }
}

async function send() {
  const text = draft.value.trim()
  if (!text || busy.value) return
  busy.value = true
  failed.value = ''
  try {
    const added = await workspace.driveSay(props.name, text)
    draft.value = ''
    add(added)
    // Not to ourselves — the relay never echoes — so this is the other
    // people in the room, and they get the note rather than a nudge to go
    // and fetch it.
    room?.publish(SAID, added)
  } catch (raised) {
    failed.value = raised?.messages?.[0] || __('Could not send that')
  } finally {
    busy.value = false
  }
}

async function remove(one) {
  await workspace.driveUnsay(one.name)
  drop(one.name)
  room?.publish(UNSAID, { name: one.name })
}

const heard = (payload) => add(payload)
const forgotten = (payload) => drop(payload?.name)

async function connect() {
  const seat = await joinRoom('file', props.name)
  if (!seat) return
  room = seat
  seat.on(SAID, heard)
  seat.on(UNSAID, forgotten)
}

function part() {
  if (!room) return
  room.off(SAID, heard)
  room.off(UNSAID, forgotten)
  room.leave()
  room = null
}

watch(() => props.name, () => {
  part()
  load()
  connect()
}, { immediate: true })

onBeforeUnmount(part)
</script>
