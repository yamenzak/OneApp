<template>
  <!--
    A conversation: what has been said, and the box to say the next thing in.

    Mounted twice — in the panel beside whatever you are looking at, and on the
    page at /one/chat. One component because they are the same conversation
    seen at two widths, and two would be two places for "what happens when the
    answer comes back" to drift apart.

    Deliberately not a chat that types itself out. An answer here can be eight
    provider calls deep, and streaming it would hold a worker open for the whole
    loop; what arrives is the finished answer with the lookups it made under it.
  -->
  <div class="flex min-h-0 flex-1 flex-col" data-slot="chat">
    <Alert
      v-if="!state.available && state.loaded"
      theme="amber"
      :title="__('{0} is not switched on here', [assistantName])"
    >
      <template #description>
        {{ __('A workspace owner can turn it on under Settings, AI.') }}
      </template>
    </Alert>

    <!-- The transcript owns the scroller; the composer below it does not move. -->
    <div ref="scroller" class="min-h-0 flex-1 overflow-auto px-4 py-6">
      <div class="mx-auto flex w-full flex-col gap-6" :class="wide ? 'max-w-3xl' : ''">
        <!--
          Nothing asked yet. The face and the name together — §E8: a workspace
          that named its assistant and gave it a picture met neither until it
          had already asked something.
        -->
        <div v-if="!turns.length && !asking" class="flex flex-col items-start gap-4">
          <AiFace size="2xl" />
          <!--
            Who it is and what it is about, *where nothing above already says
            so*.

            In the panel both were said twice: the window's own bar carries the
            mark and the name, and the chips under it carry every open thing by
            name — so an empty panel read "OneAI / OneAI / Asking about People"
            with a chip saying People beside it. Four statements, two facts.

            The page at `/one/chat` has neither a window bar nor chips, so it
            keeps them. `framed` is the host saying which it is.
          -->
          <div v-if="!framed" class="flex flex-col gap-2">
            <SpaceName
              brand="oneai"
              :renamed="assistantRenamed"
              :label="assistantName"
              class="text-base-medium"
            />
            <p class="text-p-base text-ink-muted">
              <template v-if="on?.label">
                {{ __('Asking about {0}.', [on.label]) }}
              </template>
              <template v-else>
                {{ __('Ask about anything you can already open — records, files, what a document says.') }}
              </template>
            </p>
          </div>

          <!--
            Four questions to press, chosen by what is open — see
            `shared/lib/ai/openers.js`.

            An empty chat is the one screen where a person has to invent the
            question, and inventing it is the step most people do not take.
            These also say what the panel can see far more convincingly than a
            sentence claiming it: somebody who reads "Which cells feed the
            total?" beside their workbook knows it is looking at the workbook.

            They fill the box rather than sending, because the good version of
            each is usually the offered one with a clause added — and a press
            that spends a model call on a question nobody quite meant is the
            fastest way to teach somebody not to press things.
          -->
          <div class="flex w-full flex-col items-start gap-1.5" data-slot="chat-openers">
            <Button
              v-for="one in openers"
              :key="one"
              variant="outline"
              class="max-w-full !justify-start !rounded-full !font-normal !text-ink-secondary"
              :label="one"
              @click="offer(one)"
            />
          </div>
        </div>

        <ChatTurn
          v-for="turn in turns"
          :key="turn.name"
          :turn="turn"
          @changed="reload"
        />

        <!--
          The three seconds the whole of §E8 is about.

          A spinner beside the word "Looking" said the application was busy,
          which is the one fact nobody needed. This is the shape the answer
          will take — the face that is about to speak, and a skeleton at the
          width of the paragraph that is coming — with the sheen travelling
          across it. The component was built for exactly this and was rendered
          on four surfaces, none of them the assistant's own.

          Ringed in the glow's own colour rather than in a grey hairline, so
          the skeleton, the sheen travelling across it and the window around
          all three are the same thing at three weights — `oneapp-ai-edge`.
        -->
        <div v-if="asking" class="flex w-full gap-2" data-slot="chat-thinking">
          <AiFace size="sm" thinking class="mt-1" />
          <AiGlow
            mode="block"
            active
            empty
            :lines="3"
            class="oneapp-ai-edge min-w-0 flex-1 rounded-6 px-3 py-2"
          />
        </div>
      </div>
    </div>

    <div class="px-4 pb-4 pt-2">
      <!--
        What is attached, above the box it is attached to.

        Not in the window's own strip with the open windows, and the difference
        is worth one line: that strip is *what you have open*, which changes
        under you as you work, and these are *what you chose to bring*. A chip
        you can switch off and a chip you can take back out are two different
        promises, so they sit in two places — and this one is beside the
        composer, which is where every chat that has attachments puts them.
      -->
      <div
        v-if="attachedFiles.length"
        class="mx-auto mb-2 flex w-full flex-wrap items-center gap-1"
        :class="wide ? 'max-w-3xl' : ''"
        data-slot="chat-attached"
      >
        <span
          v-for="one in attachedFiles"
          :key="one.owner"
          class="flex max-w-full items-center gap-1.5 rounded-full border border-outline-gray-2 bg-surface-gray-1 py-0.5 pe-0.5 ps-2"
        >
          <img
            v-if="one.kind"
            :src="artForKind(one.kind)"
            :alt="''"
            aria-hidden="true"
            class="size-3.5 shrink-0"
          />
          <Icon v-else name="lucide-paperclip" class="size-3.5 shrink-0 text-ink-muted" />
          <span class="min-w-0 flex-1 truncate text-xs text-ink-secondary">{{ one.label }}</span>
          <Button
            variant="ghost"
            size="sm"
            icon="lucide-x"
            :label="__('Take {0} back out', [one.label])"
            :tooltip="__('Take it back out')"
            data-slot="chat-detach"
            @click="detachFile(one.owner)"
          />
        </span>
      </div>

      <!--
        One card rather than a box and a button beside it.

        The send lives *inside* the field, under it and to the trailing end,
        which is the shape every assistant anybody uses has settled on — and it
        is not only fashion: a question here is often three lines, the field
        grows, and a button that is a sibling of a growing field either stays
        pinned to the wrong edge or drags the layout around with it.

        The ring on focus is the card's, not the textarea's, so the whole thing
        lights up as one control.
      -->
      <Panel
        pad="none"
        class="mx-auto w-full transition-shadow focus-within:border-outline-gray-3 focus-within:ring-2 focus-within:ring-outline-gray-2"
        :class="wide ? 'max-w-3xl' : ''"
      >
        <!--
          Enter sends and shift-Enter breaks the line, which is what every chat
          does and therefore what fingers expect. A Textarea rather than an
          input because a question about a quotation is often three lines.
        -->
        <!-- The class list goes straight onto the element: with no label to
             wrap, frappe-ui puts `attrs.class` on the `<textarea>` itself, so
             a `[&_textarea]` variant would be matching a descendant that is
             not there. -->
        <Textarea
          ref="box"
          v-model="typed"
          class="w-full !resize-none !border-0 !bg-transparent !shadow-none focus:!ring-0"
          :rows="1"
          :placeholder="
            on?.label ? __('Ask about {0}', [on.label]) : __('Ask about this workspace')
          "
          data-slot="chat-input"
          :disabled="asking || (state.loaded && !state.available)"
          @keydown.enter.exact.prevent="ask"
        />
        <div class="flex items-center justify-between gap-2 px-2 pb-2">
          <!--
            Attach a file, which means attach a file *in OneCloud*.

            `FilePicker` is the whole of it: the library, this device and the
            camera, and an upload writes into the Drive and then picks the
            result. So there is no second store and no "attached but nowhere" —
            what reaches the model is a `File` row it reads through
            `read_document`, under the same permission a click goes through.

            Where the line saying "About People" used to be. That line restated
            the placeholder one row above it, which restated the chip above
            that: three statements of one fact in a column 384px wide.
          -->
          <Button
            variant="ghost"
            icon="lucide-paperclip"
            :label="__('Attach a file')"
            :tooltip="__('Attach a file')"
            data-slot="chat-attach"
            :disabled="asking || (state.loaded && !state.available)"
            @click="attaching = true"
          />
          <Button
            variant="solid"
            icon="lucide-arrow-up"
            :label="__('Send')"
            :tooltip="__('Send')"
            data-slot="chat-send"
            :loading="asking"
            :disabled="!typed.trim()"
            @click="ask"
          />
        </div>
      </Panel>

      <FilePicker
        v-model="attaching"
        multiple
        :title="__('Attach a file')"
        @picked="attachFile"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { Alert, Button, Icon, Textarea } from '@/ui'
import AiFace from '@/shared/components/AiFace.vue'
import FilePicker from '@/modules/onestorage/components/FilePicker.vue'
import { artForKind } from '@/modules/onestorage/lib/art'
import { attachFile, attachedFiles, detachAll, detachFile } from '@/shared/lib/ai/context'
import SpaceName from '@/shared/components/brand/SpaceName.vue'
import Panel from '@/shared/components/Panel.vue'
import AiGlow from '@/shared/components/AiGlow.vue'
import ChatTurn from '@/modules/onespace/components/chat/ChatTurn.vue'
import {
  assistant as state, assistantName, assistantRenamed, loadAssistant,
} from '@/modules/onespace/lib/shell/assistant'
import { openersFor } from '@/shared/lib/ai/openers'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  /**
   * What the reader has open, or null. `{space, screen, docname, label}` — the
   * label is for this component and the rest is for the server, which checks
   * every part of it against what this person may actually reach.
   */
  on: { type: Object, default: null },
  /**
   * Everything the question should carry, front-first — what the chips above
   * this panel have switched on. `on` is its first entry and is what "this"
   * means; this is the whole list, and the server checks every entry of it
   * separately.
   *
   * Left empty by the page at `/one/chat`, where there is no desk to read and
   * `on` is the route's own context. One entry or none, which is what a list
   * of one is.
   */
  sending: { type: Array, default: () => [] },
  /** The page has room for a column of text; the panel does not. */
  wide: { type: Boolean, default: false },
  /**
   * Whether the host already says who this is and what it is about.
   *
   * True in the window, whose bar carries the mark and the name and whose
   * chips carry what is open. False on the page, which has neither.
   */
  framed: { type: Boolean, default: false },
})

/**
 * What goes to the server with the question.
 *
 * The chips where there are chips, and the single context where there is not.
 * A list either way, because that is the one shape the endpoint takes — and a
 * page sending a bare object is the shape it still accepts, which is what a
 * tab nobody has reloaded is doing.
 */
const attaching = ref(false)

const carrying = computed(() =>
  // Attachments first: the first entry is what "this" means, and a file
  // somebody just chose is more what they mean than a window that happened to
  // be open behind the panel.
  [
    ...attachedFiles.value,
    ...(props.sending.length ? props.sending : [props.on].filter(Boolean)),
  ].map(
    // `owner` and `on` are the chip's own bookkeeping; the server has no use
    // for either and every field sent is a field it has to ignore by name.
    ({ owner, on, label, ...rest }) => rest,
  ),
)

/** The open thread. Empty until the first question opens one. */
const session = defineModel({ type: String, default: '' })

const typed = ref('')
const box = ref(null)

/** The four questions this context is worth offering — `lib/ai/openers.js`. */
const openers = computed(() => openersFor(props.on))

/**
 * An opener, put in the box rather than sent.
 *
 * The good version of each is usually the offered one with a clause added, and
 * a press that spends a model call on a question nobody quite meant teaches
 * people not to press things. So it fills and focuses, and the person decides.
 */
function offer(question) {
  typed.value = question
  nextTick(() => box.value?.$el?.querySelector('textarea')?.focus())
}
const asking = ref(false)
const turns = ref([])
const scroller = ref(null)

watch(session, async (name) => {
  turns.value = name ? (await workspace.assistantMessages(name))?.messages || [] : []
  toBottom()
}, { immediate: true })

async function ask() {
  const question = typed.value.trim()
  if (!question || asking.value) return

  // Shown before the round trip, because the round trip can be a minute. The
  // server writes its own row; this one is replaced by it when the answer
  // lands, which is why its key is not an id from the server.
  turns.value = [...turns.value, { name: 'asking', role: 'user', content: question }]
  typed.value = ''
  asking.value = true
  toBottom()

  try {
    const answered = await workspace.askAssistant(question, session.value, carrying.value)
    turns.value = answered?.messages || turns.value
    if (answered?.session) session.value = answered.session
    await loadAssistant({ reload: true })
  } finally {
    asking.value = false
    toBottom()
  }
}

/** After a change was applied or discarded, so the card says what it became. */
async function reload() {
  if (!session.value) return
  turns.value = (await workspace.assistantMessages(session.value))?.messages || turns.value
}

function toBottom() {
  nextTick(() => {
    if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
  })
}
</script>
