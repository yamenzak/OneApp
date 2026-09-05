<!--
  The mail about this record.

  Every message here is a `Communication` that names this document — inherited
  down a conversation, found as an id this site issues written in a subject or
  body, or filed by somebody. Where each link came from is drawn beside the
  message, because a link nobody can explain is a link nobody will trust, and
  the ones made without a person are exactly the ones worth being able to see
  and take back.

  What is listed is what *this reader* may already see. The server does that;
  it is said here too because it is the rule the tab exists under: a link is not
  a grant, or filing a message against a project would publish it to everybody
  who can open the project.
-->
<template>
  <div class="flex h-full min-h-0 flex-col gap-4">
    <div class="flex shrink-0 items-center justify-between gap-3">
      <p class="text-p-sm text-ink-gray-6">
        {{ messages.length }}
        {{ messages.length === 1 ? 'message' : 'messages' }} about this record
      </p>
      <Button
        v-if="canSend"
        icon-left="lucide-send"
        label="Write"
        @click="write"
      />
    </div>

    <div v-if="loading" class="grid place-items-center py-10">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <Alert v-else-if="error" theme="red" title="This could not be loaded">
      <template #description>{{ error }}</template>
    </Alert>

    <!--
      The way in is the way out: a record with no mail yet is where somebody
      writes the first message, so the empty state carries the same control the
      header does rather than being a dead end.
    -->
    <EmptyState
      v-else-if="!messages.length"
      icon="lucide-mail"
      title="No mail about this yet"
      description="Messages that mention this record file themselves here. You can also write one."
    >
      <template #action>
        <Button v-if="canSend" icon-left="lucide-send" label="Write" @click="write" />
      </template>
    </EmptyState>

    <div v-else class="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto">
      <article
        v-for="message in messages"
        :key="message.name"
        data-slot="record-message"
        class="rounded-6 border border-outline-gray-1 p-4"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="flex min-w-0 items-center gap-2">
            <Avatar
              size="sm"
              :label="message.person?.label || message.sender"
              :image="message.person?.image"
            />
            <div class="min-w-0">
              <p class="truncate text-p-sm font-medium text-ink-gray-8">
                {{ message.person?.label || message.sender }}
              </p>
              <p class="truncate text-p-xs text-ink-gray-5">
                {{ message.sent_or_received === 'Sent' ? 'to' : 'to' }}
                {{ message.recipients }}
              </p>
            </div>
          </div>

          <div class="flex shrink-0 items-center gap-2">
            <!-- Which way it went. A record's correspondence is a record of
                 both halves, and "did we answer this" is the question the tab
                 is opened to settle. -->
            <Badge
              :theme="message.sent_or_received === 'Sent' ? 'blue' : 'gray'"
              :label="message.sent_or_received === 'Sent' ? 'Sent' : 'Received'"
            />
            <Tooltip v-if="message.by" :text="REASONS[message.by] || message.by">
              <Badge theme="gray" variant="subtle" :label="message.by" />
            </Tooltip>
            <!-- Every link has to be undoable, and the ones made without a
                 person most of all. `tooltip` on the Button rather than a
                 Tooltip around it, because frappe-ui's Button builds its own
                 and one component is one behaviour. -->
            <Button
              icon="lucide-unlink"
              variant="ghost"
              label="Not about this record"
              tooltip="Not about this record"
              :loading="detaching === message.name"
              @click="detach(message)"
            />
          </div>
        </div>

        <p class="mt-3 text-p-sm font-medium text-ink-gray-8">
          {{ message.subject }}
        </p>
        <!-- The body as text and short. A record's tab answers "what was said
             about this", and the whole message with its images and its quoted
             history is what the Mail screen is for. -->
        <p class="mt-1 line-clamp-3 text-p-sm text-ink-gray-6">{{ plain(message.content) }}</p>

        <div class="mt-3 flex items-center gap-2 text-p-xs text-ink-gray-5">
          <span>{{ when(message.communication_date) }}</span>
          <Icon v-if="message.has_attachment" name="lucide-paperclip" class="size-3.5" />
        </div>
      </article>

      <Button
        v-if="more"
        variant="ghost"
        label="Load more"
        :loading="loading"
        @click="load(messages.length + PAGE)"
      />
    </div>

    <MailComposer
      ref="composer"
      v-model="writing"
      :addresses="addresses"
      :about="{ spaceCode, screen, name }"
      @sent="afterSend"
    />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import {
  Alert, Avatar, Badge, Button, Icon, LoadingIndicator, Tooltip, dayjsLocal,
} from '@/ui'
import EmptyState from '../../EmptyState.vue'
import MailComposer from '../../mail/MailComposer.vue'
import { workspace } from '../../../lib/workspace'
import { plainText } from '../../../lib/format'

const props = defineProps({
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  name: { type: String, required: true },
})

const PAGE = 50

// What each provenance value means, spelled out where somebody is looking at
// it. The stored value is one word because it is a key; a badge that says
// "thread" and explains nothing is a badge that raises a question.
const REASONS = {
  thread: 'Inherited from the conversation this message belongs to',
  text: 'This record’s id was written in the subject or the message',
  manual: 'Filed here by somebody',
}

const messages = ref([])
const addresses = ref([])
const canSend = ref(false)
const more = ref(false)
const loading = ref(false)
const error = ref('')
const detaching = ref('')
const writing = ref(false)
const composer = ref(null)

async function load(limit = PAGE) {
  loading.value = true
  error.value = ''
  try {
    const found = await workspace.recordMail(props.spaceCode, props.screen, props.name, limit)
    messages.value = found?.messages || []
    canSend.value = !!found?.can_send
    more.value = !!found?.more
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    loading.value = false
  }
}

async function write() {
  if (!addresses.value.length) {
    const held = await workspace.mail()
    addresses.value = (held?.addresses || []).map((one) => one.email_id || one)
  }
  composer.value?.compose(null)
}

async function afterSend() {
  writing.value = false
  await load()
}

async function detach(message) {
  detaching.value = message.name
  try {
    await workspace.recordMailDetach(props.spaceCode, props.screen, props.name, message.name)
    messages.value = messages.value.filter((one) => one.name !== message.name)
  } finally {
    detaching.value = ''
  }
}

// A body as words. The markup, the held images and the quoted history are the
// Mail screen's problem; this tab answers "what was said about this record".
const plain = (html) => plainText(html)

const when = (value) => (value ? dayjsLocal(value).fromNow() : '')

onMounted(() => load())
</script>
