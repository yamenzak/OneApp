<template>
  <!--
    Reading mail: three columns, and each one answers a different question.

    The rail says *which addresses are mine*, the middle says *what has
    arrived*, and the right says *what does this one say*. It is the shape every
    mail client has had for thirty years, and the reason to keep it is that
    nobody has to learn it.

    What is deliberately not here: folders a person makes, drag and drop,
    labels, rules. Mail in this product files itself against the record it
    belongs to — see `view_settings` and the record's own timeline — and a
    parallel filing system beside that would be two places to look for the same
    message.
  -->
  <div class="flex h-full min-h-0">
    <!-- Which addresses are mine -->
    <div class="flex w-56 shrink-0 flex-col gap-1 border-r border-outline-gray-1 p-3">
      <span class="px-2 pb-1 text-p-xs font-medium uppercase tracking-wide text-ink-gray-5">
        Mail
      </span>
      <RouterLink
        v-for="one in folders"
        :key="one.key"
        :to="{ name: 'Mail', query: { folder: one.key } }"
        data-slot="mail-folder"
      >
        <Button
          class="w-full !justify-start"
          :variant="folder === one.key ? 'subtle' : 'ghost'"
          :icon-left="one.icon"
          :label="one.label"
        />
      </RouterLink>

      <div class="mt-auto pt-3">
        <Button
          variant="ghost"
          class="!justify-start"
          icon-left="lucide-pencil"
          label="Write"
          @click="compose()"
        />
      </div>
    </div>

    <!-- What has arrived -->
    <div class="flex w-96 shrink-0 flex-col border-r border-outline-gray-1">
      <div class="border-b border-outline-gray-1 p-2">
        <FormControl
          v-model="search"
          type="text"
          placeholder="Search subjects"
          @keyup.enter="load()"
        />
      </div>

      <LoadingText v-if="loading" class="py-8" text="Loading" />

      <EmptyState
        v-else-if="!threads.length"
        icon="lucide-inbox"
        title="Nothing here"
        :description="
          addresses.length
            ? 'No mail on this address yet.'
            : 'Nobody has given you an address yet. A workspace admin can, in Settings.'
        "
      />

      <div v-else class="min-h-0 flex-1 overflow-y-auto">
        <!--
          A conversation is a place, so it is a link and it is in the URL. That
          is not tidiness: it is what makes the back button close a thread, a
          reload keep one open, and "look at this one" something somebody can
          send to a colleague. It is also why these are `router-link` and not a
          button somebody has to be told is clickable.
        -->
        <RouterLink
          v-for="one in threads"
          :key="one.key"
          :to="{ name: 'Mail', query: { folder, thread: one.key } }"
          class="flex w-full flex-col gap-0.5 border-b border-outline-gray-1 px-3 py-2.5 text-left hover:bg-surface-gray-2"
          :class="chosen === one.key ? 'bg-surface-gray-2' : ''"
          data-slot="mail-thread"
        >
          <div class="flex items-center gap-2">
            <span
              class="min-w-0 flex-1 truncate text-p-sm"
              :class="one.unread ? 'font-semibold text-ink-gray-9' : 'text-ink-gray-7'"
            >
              {{ one.from }}
            </span>
            <span class="shrink-0 text-p-xs tabular-nums text-ink-gray-5">
              {{ when(one.at) }}
            </span>
          </div>
          <span
            class="truncate text-p-sm"
            :class="one.unread ? 'font-medium text-ink-gray-8' : 'text-ink-gray-6'"
          >
            {{ one.subject }}
            <span v-if="one.count > 1" class="text-ink-gray-4">({{ one.count }})</span>
          </span>
          <span class="truncate text-p-xs text-ink-gray-5">{{ one.preview }}</span>
        </RouterLink>
      </div>
    </div>

    <!-- What it says -->
    <div class="flex min-w-0 flex-1 flex-col">
      <EmptyState
        v-if="!chosen"
        icon="lucide-mail-open"
        title="Nothing open"
        description="Pick a conversation."
      />

      <div v-else class="min-h-0 flex-1 overflow-y-auto p-5">
        <h2 class="text-lg font-semibold text-ink-gray-9">{{ openSubject }}</h2>

        <article
          v-for="one in messages"
          :key="one.name"
          class="mt-4 rounded-6 border border-outline-gray-2 p-4"
          data-slot="mail-message"
        >
          <div class="flex items-baseline justify-between gap-3">
            <span class="text-p-sm font-medium text-ink-gray-8">
              {{ one.sender_full_name || one.sender }}
            </span>
            <span class="text-p-xs text-ink-gray-5">{{ when(one.communication_date) }}</span>
          </div>
          <span class="text-p-xs text-ink-gray-5">to {{ one.recipients }}</span>

          <!-- eslint-disable-next-line vue/no-v-html -->
          <div class="prose-sm mt-3 max-w-none text-ink-gray-8" v-html="one.content" />

          <div v-if="one.attachments?.length" class="mt-3 flex flex-wrap gap-2">
            <a
              v-for="file in one.attachments"
              :key="file.name"
              :href="file.file_url"
              class="flex items-center gap-1.5 rounded-6 border border-outline-gray-2 px-2 py-1 text-p-xs text-ink-gray-7 hover:bg-surface-gray-2"
            >
              <Icon name="lucide-paperclip" class="size-3" :aria-hidden="true" />
              {{ file.file_name }}
            </a>
          </div>
        </article>

        <Button
          class="mt-4"
          variant="subtle"
          icon-left="lucide-reply"
          label="Reply"
          @click="compose(messages[messages.length - 1])"
        />
      </div>
    </div>

    <Dialog v-model="writing" title="New message" size="xl">
      <div class="flex flex-col gap-3">
        <Select
          v-if="addresses.length > 1"
          v-model="draft.sender"
          label="From"
          :options="addresses.map((one) => ({ label: one, value: one }))"
        />
        <FormControl v-model="draft.to" label="To" placeholder="somebody@example.com" />
        <FormControl v-model="draft.subject" label="Subject" />
        <FormControl v-model="draft.content" type="textarea" label="Message" :rows="10" />
        <ErrorMessage v-if="error" :message="error" />
      </div>
      <template #actions>
        <Button variant="solid" label="Send" :loading="sending" @click="post" />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import {
  Button,
  Dialog,
  ErrorMessage,
  FormControl,
  Icon,
  LoadingText,
  Select,
  dayjsLocal,
} from '@/ui'
import EmptyState from '../components/EmptyState.vue'
import { workspace } from '../lib/workspace'

const loading = ref(true)
const sending = ref(false)
const error = ref('')

const route = useRoute()

const folders = ref([])
const addresses = ref([])
const threads = ref([])
const search = ref('')
const messages = ref([])

// Both read from the URL rather than kept beside it. One source, so a link
// pasted into the address bar opens exactly what the person who sent it saw.
const folder = computed(() => String(route.query.folder || 'all'))
const chosen = computed(() => String(route.query.thread || ''))

const openSubject = computed(
  () => threads.value.find((one) => one.key === chosen.value)?.subject || '',
)

const writing = ref(false)
const draft = reactive({ sender: '', to: '', subject: '', content: '', in_reply_to: '' })

// The same relative wording the record timeline uses, from the same helper.
const when = (value) => (value ? dayjsLocal(value).fromNow() : '')

async function boot() {
  const found = await workspace.mailFolders()
  folders.value = found.folders || []
  addresses.value = found.addresses || []
  draft.sender = addresses.value[0] || ''
  await load()
}

async function load() {
  loading.value = true
  try {
    const found = await workspace.mailThreads(folder.value, 0, search.value)
    threads.value = found.threads || []
  } finally {
    loading.value = false
  }
}

/**
 * Open whatever the URL says is open.
 *
 * Marked read here, which is the moment a person actually looked at it —
 * marking on fetch would clear the unread flag for a thread the list happened
 * to preview, and marking on the server would do it for everybody who shares
 * the address.
 */
async function read() {
  if (!chosen.value) {
    messages.value = []
    return
  }
  messages.value = await workspace.mailThread(chosen.value, folder.value)

  const names = messages.value.map((one) => one.name)
  if (names.length) {
    await workspace.mailMarkRead(names)
    const thread = threads.value.find((one) => one.key === chosen.value)
    if (thread) thread.unread = 0
  }
}

function compose(replyTo) {
  error.value = ''
  if (replyTo) {
    draft.to = replyTo.sender
    draft.subject = replyTo.subject?.match(/^re:/i)
      ? replyTo.subject
      : `Re: ${replyTo.subject || ''}`
    draft.in_reply_to = replyTo.name
    // The address it was sent *to* is the one to answer from, where that is one
    // of ours. Replying to a message that reached `sales@` from a personal
    // address is how a customer learns a shared mailbox is not shared.
    const mine = addresses.value.find((one) => (replyTo.recipients || '').includes(one))
    if (mine) draft.sender = mine
  } else {
    draft.to = ''
    draft.subject = ''
    draft.in_reply_to = ''
  }
  draft.content = ''
  writing.value = true
}

async function post() {
  error.value = ''
  sending.value = true
  try {
    await workspace.mailSend({ ...draft })
    writing.value = false
    await load()
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    sending.value = false
  }
}

boot()

// The list follows the folder; the reading pane follows the thread. Separately,
// because changing folder should not refetch a thread and opening a thread
// should not refetch the list.
watch(folder, load)
watch([chosen, folder], read, { immediate: true })
</script>
