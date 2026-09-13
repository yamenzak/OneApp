<template>
  <!--
    The assistant beside whatever you are looking at.

    A **panel** in this product's vocabulary (`docs/ONESPACE.md` §12): a strip
    inside a page you toggle and that keeps its state. Not a popover, and the
    difference is the whole reason it is this: an answer here can be eight
    provider calls and forty seconds, and a popover dismisses on the outside
    click somebody makes to go and check the record they were asking about. A
    panel is the popover that survives being ignored.

    Mounted once, in the shell, so every page has it without every page knowing
    about it. `lib/shell/assistant.js` holds whether it is open and what it is
    looking at, because the thing that opens it is somewhere else every time.

    Not drawn on a phone: the page has one surface there, and the assistant is a
    page (`/one/chat`) like everything else.
  -->
  <aside
    v-if="state.showing && state.available"
    class="relative hidden shrink-0 flex-col border-s border-outline-gray-1 bg-surface-base md:flex"
    :style="{ width: `${width}px` }"
    :aria-label="assistantName"
    data-slot="assistant-panel"
  >
    <!--
      A handle on the leading edge, drawn over the border rather than inside
      the panel: 384px was the whole of this surface for as long as it existed,
      and an answer that made four lookups wants more of them than that. The
      width is remembered per person — it is a preference about their screen,
      not about the workspace.

      Nothing is emitted while the pointer moves; the width is held here and
      the panel follows it, so the drag is smooth and there is one write on
      release rather than one per pixel. Same arrangement as `RecordTable`'s
      column resizer, for the same reason.
    -->
    <div
      data-slot="assistant-resizer"
      class="absolute inset-y-0 -start-1 z-20 w-2 cursor-col-resize"
      @pointerdown.prevent="grab"
    />

    <div class="flex shrink-0 flex-col gap-2 border-b border-outline-gray-1 px-3 py-2.5">
      <div class="flex items-center justify-between gap-2">
        <div class="flex min-w-0 items-center gap-2">
          <AiFace size="sm" />
          <p class="truncate text-base font-medium text-ink-primary">{{ assistantName }}</p>
        </div>

        <div class="flex shrink-0 items-center gap-0.5">
          <Button
            variant="ghost"
            icon="lucide-plus"
            :label="__('New chat')"
            :tooltip="__('New chat')"
            data-slot="assistant-new"
            @click="state.session = ''"
          />
          <Dropdown :options="threads">
            <Button
              variant="ghost"
              icon="lucide-history"
              :label="__('Earlier chats')"
              :tooltip="__('Earlier chats')"
              data-slot="assistant-threads"
            />
          </Dropdown>
          <Dropdown :options="menu">
            <Button variant="ghost" icon="lucide-ellipsis" :label="__('More')" :tooltip="__('More')" />
          </Dropdown>
          <Button
            variant="ghost"
            icon="lucide-x"
            :label="__('Close {0}', [assistantName])"
            :tooltip="__('Close')"
            data-slot="assistant-close"
            @click="closeAssistant"
          />
        </div>
      </div>

      <!--
        What it is looking at, as a chip rather than as grey type under the
        name. It is the one fact that decides what every answer will mean, and
        it was the quietest thing in the panel.

        The mark is the file's own — the same artwork the Drive draws, so a
        workbook here and a workbook there are recognisably the same thing.
        Pressing the cross widens the conversation back to the workspace, which
        is a thing people want and previously could only do by closing the
        panel and opening it from the rail.
      -->
      <div
        v-if="shown?.label"
        class="flex items-center gap-1.5 rounded-full border border-outline-gray-2 bg-surface-gray-1 py-0.5 pe-0.5 ps-2"
        data-slot="assistant-context"
      >
        <img
          v-if="shown.file"
          :src="artForKind(shown.kind)"
          :alt="''"
          aria-hidden="true"
          class="size-3.5 shrink-0"
        />
        <Icon v-else name="lucide-layout-list" class="size-3.5 shrink-0 text-ink-muted" />
        <span class="min-w-0 flex-1 truncate text-xs text-ink-secondary">{{ shown.label }}</span>
        <Button
          variant="ghost"
          size="sm"
          icon="lucide-x"
          :label="__('Ask about the whole workspace instead')"
          :tooltip="__('Ask about the workspace')"
          data-slot="assistant-unpin"
          @click="widen"
        />
      </div>
    </div>

    <ChatPanel v-model="state.session" :on="shown" />
  </aside>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button, Dropdown, Icon } from '@/ui'
import AiFace from '@/shared/components/AiFace.vue'
import { artForKind } from '@/modules/onestorage/lib/art'
import { openContext } from '@/modules/onespace/lib/shell/nav'
import { recall, remember } from '@/shared/lib/url/remember'
import ChatPanel from '@/modules/onespace/components/chat/ChatPanel.vue'
import {
  assistant as state,
  assistantName,
  closeAssistant,
  loadAssistant,
  openAssistant,
} from '@/modules/onespace/lib/shell/assistant'
import { useAddress } from '@/shared/composables/useAddress'
import { workspace } from '@/shared/lib/workspace'
import { KIND, writeAt } from '@/shared/lib/url/at'
import { __ } from '@/shared/lib/runtime/translate'

const router = useRouter()
const route = useRoute()

/**
 * How wide the panel is, in pixels, remembered.
 *
 * The floor is where a line of an answer stops being a line and starts being
 * a column of two words; the ceiling is where the page behind it stops being
 * usable, which is the thing the panel is beside.
 */
const MIN = 340
const MAX = 720
const WIDTH = 'assistant.width'

const width = ref(Math.min(MAX, Math.max(MIN, Number(recall(WIDTH)) || 400)))

function grab(event) {
  const from = event.clientX
  const started = width.value
  // The panel is on the trailing edge, so dragging towards the start widens it.
  const move = (moved) => {
    width.value = Math.min(MAX, Math.max(MIN, started + (from - moved.clientX)))
  }
  const done = () => {
    remember(WIDTH, String(width.value))
    window.removeEventListener('pointermove', move)
    window.removeEventListener('pointerup', done)
  }
  window.addEventListener('pointermove', move)
  window.addEventListener('pointerup', done)
}

/**
 * Ask about the workspace instead of about what is open.
 *
 * A new thread, because `openAssistant` starts one whenever the subject
 * changes and this is that: a conversation about a quotation that is now about
 * the workspace is two conversations, and carrying the first forward leaves
 * the model answering "this one" from a note that no longer applies.
 */
function widen() {
  state.on = null
  state.session = ''
}

/**
 * What is open, with its words kept current.
 *
 * `state.on` is the subject and is stored, because changing it starts a new
 * thread. The label is not the subject: a document's title arrives after its
 * id, so a panel opened the instant the page did would otherwise say "This
 * document" until somebody closed and reopened it. Where the page is still
 * describing the same file, its words win.
 */
const shown = computed(() => {
  // `openContext` and not `declaredNow`: a record screen declares nothing and
  // is derived from the address, and reading only the declared claim there
  // answered "nothing open" for every screen in the product.
  const live = openContext(route)
  if (!state.session) return live || state.on
  if (live && state.on?.file && live.file === state.on.file) return live
  return state.on
})

/**
 * While nothing has been asked, the panel follows what you open.
 *
 * Opening a file in the Drive with the panel already open used to leave it
 * offering to talk about the workspace, because the subject was decided when
 * the panel opened and nothing revisited it. Following is right *until there
 * is a conversation*: after that the subject is what the thread is about, and
 * changing it under somebody mid-thread would leave the model answering "this
 * one" from a note that no longer applies — which is the rule `openAssistant`
 * already states and this keeps.
 *
 * Written onto `state.on` rather than only rendered, because that is what goes
 * to the server with the question.
 */
watch(
  () => (state.showing && !state.session ? openContext(route) : undefined),
  (live) => {
    if (live === undefined) return
    if (JSON.stringify(live || null) !== JSON.stringify(state.on || null)) {
      state.on = live || null
    }
  },
  { immediate: true },
)

/** The threads this person has, newest first, as a menu. */
const threads = computed(() => {
  const rows = state.sessions || []
  if (!rows.length) {
    return [{ label: __('No earlier chats'), icon: 'lucide-message-square', onClick: () => {} }]
  }
  return rows.slice(0, 12).map((one) => ({
    label: one.title,
    icon: 'lucide-message-square',
    selected: one.name === state.session,
    onClick: () => { state.session = one.name },
  }))
})

/**
 * The assistant has an address — `?ask=`, §C4.
 *
 * Empty means open on a new conversation; a session name means open on that
 * one. It is a panel and stays one — an answer here can be forty seconds and
 * a popover dismisses on the click somebody makes to go and check the record
 * they asked about — but a panel with an address is one a colleague can be
 * sent to.
 *
 * Not drawn on a phone, where the assistant is a page; the address there is
 * `/one/chat`, which is a route and already had one.
 */
useAddress('ask', {
  read: () => {
    if (!state.showing) return ''
    // A blank value is still an answer: `?ask=` is the assistant open on
    // nothing, which is what pressing the rail entry gives you. Vue Router
    // drops an empty string, so a new conversation says so with a word.
    return state.session || 'new'
  },
  write: (value) => {
    if (!value) {
      closeAssistant()
      return
    }
    state.session = value === 'new' ? '' : value
    // `state.on` and not the route was the bug here: on a fresh page load
    // nothing has set it yet, so a colleague following `?ask=…` to a document
    // got a panel offering to talk about the workspace. The route — and what
    // the page on it has declared — is the thing that knows.
    openAssistant(openContext(route))
  },
})

/**
 * The three things a conversation can be, beyond having it.
 *
 * "Open as a page" is the one that matters and it is why the page still exists:
 * a panel is 384px, and a long answer with four lookups under it wants a
 * column. The thread goes with it — the same conversation, wider.
 */
const menu = computed(() => [
  {
    label: __('New chat'),
    icon: 'lucide-plus',
    onClick: () => { state.session = '' },
  },
  {
    label: __('Open as a page'),
    icon: 'lucide-maximize-2',
    onClick: () => {
      closeAssistant()
      router.push({
        name: 'Chat',
        ...(state.session ? { query: { at: writeAt(KIND.CHAT, state.session) } } : {}),
      })
    },
  },
  ...(state.session
    ? [{
      label: __('Delete for ever'),
      icon: 'lucide-trash-2',
      onClick: async () => {
        await workspace.forgetChat(state.session)
        state.session = ''
        await loadAssistant({ reload: true })
      },
    }]
    : []),
])
</script>
