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
      The way in is the dock — `components/desk/Dock.vue`.

      There was a 64px mark fixed in the bottom corner, and it was the right
      answer while the assistant was the only thing that floated: a rail entry
      is a rail you can collapse, and this had to be reachable from anywhere.
      The dock is that, for every app rather than for one, and two permanent
      marks in the same corner meaning nearly the same thing is the shape
      `docs/UNIFICATION.md` F1 refuses. It also took the corner a list's own
      footer had to be told to keep clear of, which is a rule that can go with
      it.
    -->
    <!--
      A tenant of the one window there is — `components/desk/DeskWindow.vue`.
      The drag, the resize, the remembered corner, the fill and the close were
      all written here first and are all there now; what is left below is what
      makes this window the assistant rather than any other.
    -->
    <DeskWindow
      v-if="assistantShowing"
      id="assistant"
      :title="assistantName"
      :label="assistantName"
      :tint="colourOf('oneai')"
      @close="closeAssistant"
    >
      <template #title>
        <AiFace size="sm" />
        <p class="truncate text-base font-medium text-ink-primary">{{ assistantName }}</p>
      </template>

      <template #controls>
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
      </template>

      <template #under>
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
      </template>

      <ChatPanel v-model="state.session" :on="shown" />
    </DeskWindow>
  </template>
</template>

<script setup>
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button, Dropdown, Icon } from '@/ui'
import { colourOf } from '@/shared/lib/brand/naming'
import AiFace from '@/shared/components/AiFace.vue'
import { artForKind } from '@/modules/onestorage/lib/art'
import { openContext } from '@/modules/onespace/lib/shell/nav'
import { useShortcuts } from '@/modules/onespace/lib/shell/shortcuts'
import ChatPanel from '@/modules/onespace/components/chat/ChatPanel.vue'
import DeskWindow from '@/modules/onespace/components/desk/DeskWindow.vue'
import {
  assistant as state,
  assistantName,
  assistantShowing,
  closeAssistant,
  loadAssistant,
  openAssistant,
  pressAssistant,
} from '@/modules/onespace/lib/shell/assistant'
import { useAddress } from '@/shared/composables/useAddress'
import { workspace } from '@/shared/lib/workspace'
import { KIND, writeAt } from '@/shared/lib/url/at'
import { __ } from '@/shared/lib/runtime/translate'

const router = useRouter()
const route = useRoute()

/**
 * Anywhere, without reaching for the dock — which is the other half of "always
 * there". A shortcut costs no pixels.
 *
 * `mod+j` because `mod+k` is a command palette everywhere and taking it here
 * would be taking it from the thing people expect it to be.
 *
 * It folds rather than closes, which is what changed when there was somewhere
 * to fold to. Pressing it twice used to throw the conversation away and start
 * a new one on the way back; now the second press is the same thing the dock's
 * tile does, and the thread is where it was left.
 */
useShortcuts({
  'mod+j': () => pressAssistant(openContext(route)),
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
  () => (assistantShowing.value && !state.session ? openContext(route) : undefined),
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
    if (!assistantShowing.value) return ''
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
