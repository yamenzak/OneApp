<template>
  <!--
    The assistant, floating over whatever you are looking at.

    A **widget**, and the fourth surface in this product's vocabulary after the
    pane, the page and the drawer (`docs/ONESPACE.md`): fixed to the viewport,
    over the content rather than beside it, movable, and not modal. The three
    record surfaces are all about a record you opened *from* somewhere; this is
    the one thing that is about wherever you happen to be, so it is the one
    thing that does not belong in the layout.

    It was a panel — a column in the shell's flex row — and the reason it is
    not any more is arithmetic rather than taste. A panel takes its width off
    the page beside it, and this product already puts two columns there: with
    the Drive's pane open the list came out at about seventy pixels, which is
    enough for a tick and a format mark and nothing at all for the name. A
    third column does not fit on a laptop, and the assistant is the one of the
    three that has no claim to the space.

    What it keeps from the panel is the thing that made it a panel rather than
    a popover: **it survives being ignored.** An answer here can be eight
    provider calls and forty seconds, and a popover dismisses on the outside
    click somebody makes to go and check the record they were asking about.
    Nothing here closes on an outside click. Escape does, because that is a
    person saying so.

    Mounted once, in the shell, so every page has it without every page
    knowing about it.

    Not on a phone: there is one surface there and the assistant is a page
    (`/one/chat`) like everything else.
  -->
  <template v-if="state.available">
    <!--
      Always there, which is the whole point of the shape. The rail entry was
      the only way in and it is a rail you can collapse; this is a fixed mark
      in the corner that does not move when the page does.
    -->
    <!--
      Ghost over its own surface rather than a solid fill. `AiFace` draws the
      workspace's own mark inside a ring, and a coloured disc behind it makes
      that two rings and hides the one anybody chose — the launcher should look
      like the assistant, not like a generic corner button.
    -->
    <Button
      v-if="!state.showing"
      variant="ghost"
      class="fixed bottom-5 end-5 z-40 hidden !size-12 !rounded-full border border-outline-gray-2 !bg-surface-elevation-2 shadow-over md:flex"
      :label="__('Ask {0}', [assistantName])"
      :tooltip="`${__('Ask {0}', [assistantName])} · ${MOD}J`"
      data-slot="assistant-launcher"
      @click="openAssistant(openContext(route))"
    >
      <AiFace size="lg" />
    </Button>

    <Panel
      v-if="state.showing"
      ground="base"
      pad="none"
      elevation="floating"
      as="aside"
      class="fixed z-40 hidden flex-col overflow-hidden md:flex"
      :style="{ insetInlineStart: `${at.x}px`, top: `${at.y}px`, width: `${size.w}px`, height: `${size.h}px` }"
      :aria-label="assistantName"
      data-slot="assistant-widget"
      @keydown.esc="closeAssistant"
    >
      <!--
        The header is the handle. Dragging anywhere else would mean a widget
        that moves when somebody tries to select an answer to copy it, which
        is the commonest thing anybody does with one of these.
      -->
      <div
        class="flex shrink-0 cursor-grab flex-col gap-2 border-b border-outline-gray-1 px-3 py-2.5 active:cursor-grabbing"
        data-slot="assistant-handle"
        @pointerdown="lift"
      >
        <div class="flex items-center justify-between gap-2">
          <div class="flex min-w-0 items-center gap-2">
            <AiFace size="sm" />
            <p class="truncate text-base font-medium text-ink-primary">{{ assistantName }}</p>
          </div>

          <!-- `@pointerdown.stop` on the controls, or pressing one of them
               starts a drag that swallows the click. -->
          <div class="flex shrink-0 items-center gap-0.5" @pointerdown.stop>
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
          name. It is the one fact that decides what every answer will mean.

          The mark is the file's own — the same artwork the Drive draws, so a
          workbook here and a workbook there are recognisably the same thing.
          Pressing the cross widens the conversation back to the workspace.
        -->
        <div
          v-if="shown?.label"
          class="flex items-center gap-1.5 rounded-full border border-outline-gray-2 bg-surface-gray-1 py-0.5 pe-0.5 ps-2"
          data-slot="assistant-context"
          @pointerdown.stop
        >
          <img
            v-if="shown.file"
            :src="artForKind(shown.kind)"
            :alt="''"
            aria-hidden="true"
            class="size-3.5 shrink-0"
          />
          <Icon v-else name="lucide-layout-list" class="size-3.5 shrink-0 text-ink-muted" />
          <span class="min-w-0 flex-1 truncate text-xs text-ink-secondary">
            {{ shown.label }}
            <!--
              And what is highlighted, when anything is. It changes what every
              answer will be about — "summarise this" is the paragraph rather
              than the document — so it is said where the subject is said, and
              it is said in words rather than implied: the passage is going
              into a request, and somebody ought to be able to see that it is.
            -->
            <template v-if="shown.selection">
              · {{ highlighted }}
            </template>
          </span>
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

      <!--
        The grip, at the corner it grows from. Anchored bottom-end by default,
        so the corner that is free is the leading top one — dragging it out
        makes the widget taller and wider without moving the corner the eye is
        anchored on.
      -->
      <div
        class="absolute start-0 top-0 z-10 size-3 cursor-nwse-resize"
        data-slot="assistant-resizer"
        @pointerdown.prevent="stretch"
      />
    </Panel>
  </template>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button, Dropdown, Icon } from '@/ui'
import AiFace from '@/shared/components/AiFace.vue'
import { artForKind } from '@/modules/onestorage/lib/art'
import { openContext } from '@/modules/onespace/lib/shell/nav'
import { recall, remember } from '@/shared/lib/url/remember'
import Panel from '@/shared/components/Panel.vue'
import { MOD, useShortcuts } from '@/modules/onespace/lib/shell/shortcuts'
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
 * Where it sits and how big it is, both remembered.
 *
 * Floors first: below about 340 a line of an answer stops being a line and
 * becomes a column of two words, and below 420 the transcript shows one turn.
 * The ceilings are the viewport itself, because a widget larger than the
 * window is one whose close button you cannot reach.
 */
const MIN_W = 340
const MIN_H = 420
// One declared key with two parts, which is what `lib/url/remember.js` means
// by "a key is a prefix". An undeclared one is swallowed rather than stored —
// the throw is inside the `try` — so this was written and never read back
// until the key was declared in `scripts/spa/runtime.py`.
const KEY = 'assistant.at'
const WHERE = 'where'
const SIZE = 'size'

/** Clear of the launcher's corner, which is where the eye already is. */
const MARGIN = 20

const size = reactive({ w: 400, h: 560 })
const at = reactive({ x: 0, y: 0 })

const roomW = () => (typeof window === 'undefined' ? 1280 : window.innerWidth)
const roomH = () => (typeof window === 'undefined' ? 800 : window.innerHeight)

/** Inside the window, whatever the window has just done. */
function settle() {
  size.w = Math.min(Math.max(size.w, MIN_W), Math.max(MIN_W, roomW() - MARGIN * 2))
  size.h = Math.min(Math.max(size.h, MIN_H), Math.max(MIN_H, roomH() - MARGIN * 2))
  at.x = Math.min(Math.max(at.x, 0), Math.max(0, roomW() - size.w))
  at.y = Math.min(Math.max(at.y, 0), Math.max(0, roomH() - size.h))
}

/**
 * Bottom-end unless this person has moved it.
 *
 * The default corner is the one the launcher was in, so opening it puts the
 * widget where the press was — a thing that appears somewhere else is a thing
 * you have to go and find.
 */
function place() {
  const stored = (recall(KEY, WHERE) || '').split(',').map(Number)
  const kept = (recall(KEY, SIZE) || '').split(',').map(Number)
  if (kept.length === 2 && kept.every(Number.isFinite) && kept[0]) {
    size.w = kept[0]
    size.h = kept[1]
  }
  if (stored.length === 2 && stored.every(Number.isFinite)) {
    at.x = stored[0]
    at.y = stored[1]
  } else {
    at.x = roomW() - size.w - MARGIN
    at.y = roomH() - size.h - MARGIN
  }
  settle()
}

place()

/** A drag, of either kind: hold the numbers here and write once on release. */
function drag(move, done) {
  const stop = (event) => {
    window.removeEventListener('pointermove', move)
    window.removeEventListener('pointerup', stop)
    done(event)
  }
  window.addEventListener('pointermove', move)
  window.addEventListener('pointerup', stop)
}

function lift(event) {
  const fromX = event.clientX - at.x
  const fromY = event.clientY - at.y
  drag(
    (moved) => {
      at.x = moved.clientX - fromX
      at.y = moved.clientY - fromY
      settle()
    },
    () => remember(KEY, `${Math.round(at.x)},${Math.round(at.y)}`, WHERE),
  )
}

/**
 * The leading-top corner, which grows it away from where it is anchored.
 *
 * Both the size and the position move, because dragging that corner outwards
 * has to leave the opposite corner where it was — otherwise the widget appears
 * to slide while you are resizing it.
 */
function stretch(event) {
  const edgeX = at.x + size.w
  const edgeY = at.y + size.h
  drag(
    (moved) => {
      size.w = Math.max(MIN_W, edgeX - moved.clientX)
      size.h = Math.max(MIN_H, edgeY - moved.clientY)
      at.x = edgeX - size.w
      at.y = edgeY - size.h
      settle()
    },
    () => {
      remember(KEY, `${Math.round(size.w)},${Math.round(size.h)}`, SIZE)
      remember(KEY, `${Math.round(at.x)},${Math.round(at.y)}`, WHERE)
    },
  )
}

// A window that got smaller must not leave the widget off the edge of it.
onMounted(() => window.addEventListener('resize', settle))
onBeforeUnmount(() => window.removeEventListener('resize', settle))

/**
 * Anywhere, without reaching for the rail — which is the other half of "always
 * there". A rail entry is a rail you can collapse; a shortcut costs no pixels.
 *
 * `mod+j` because `mod+k` is a command palette everywhere and taking it here
 * would be taking it from the thing people expect it to be.
 */
useShortcuts({
  'mod+j': () => (state.showing ? closeAssistant() : openAssistant(openContext(route))),
})

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

/**
 * What is highlighted, counted in the unit that surface counts in.
 *
 * Words for prose, and the range itself for a workbook — "C3:E8" is what a
 * person selecting cells is looking at, and a word count of a pipe table is a
 * number about nothing. The digest's first line is the range, which is why it
 * is first.
 */
const highlighted = computed(() => {
  const said = String(shown.value?.selection || '')
  if (shown.value?.kind === 'Sheet') return said.split('\n')[0]
  const count = said.trim().split(/\s+/).filter(Boolean).length
  return __('{0} words highlighted', [count])
})

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
    // Context first, thread second, and the order is the whole of it.
    // `openAssistant` starts a new thread whenever the subject changes — which
    // on a fresh page load it always has, from nothing to whatever is open —
    // so setting the session before that call is setting a session that the
    // call then throws away. A link to a conversation opened an empty one.
    //
    // `openContext(route)` and not `state.on`: nothing has set `state.on` yet
    // on a fresh load, so a colleague following `?ask=…` to a document got a
    // widget offering to talk about the workspace instead.
    openAssistant(openContext(route))
    state.session = value === 'new' ? '' : value
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
      // Navigate, and let the widget close because it did.
      //
      // Closing first looked obvious and cancelled the navigation: closing
      // writes `?ask=` out of the URL through `useAddress`, that write is a
      // `router.replace`, and a replace issued while a push is in flight
      // aborts the push — so "Open as a page" left the reader exactly where
      // they were, on a route with one fewer query parameter.
      //
      // Nothing has to close it either. The chat route carries no `ask`, so
      // the moment the URL changes `useAddress` reads a value that disagrees
      // with the state and writes the state back down to match: the widget
      // shuts itself, which is the same mechanism that closes it when
      // somebody presses Back.
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
