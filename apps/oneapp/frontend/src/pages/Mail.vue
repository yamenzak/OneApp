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
    <!-- What has arrived -->
    <div class="flex w-96 shrink-0 flex-col border-r border-outline-gray-1">
      <div class="flex items-center gap-2 border-b border-outline-gray-1 p-2">
        <FormControl
          v-model="search"
          class="flex-1"
          type="text"
          placeholder="Search subjects"
          @keyup.enter="load()"
        />
        <!-- Write sits over the list rather than in the rail: the rail is the
             shell's sidebar now, and an action belongs to the thing it acts
             on. -->
        <Button
          variant="subtle"
          icon-left="lucide-pencil"
          label="Write"
          @click="compose()"
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
            <!-- No hover card in the list: fifty of them is fifty listeners
                 and a card that opens while somebody is scanning down. The
                 face and the name are the point here; the card is on the
                 message. -->
            <SenderChip
              class="min-w-0 flex-1 text-p-sm"
              :sender="one.sender"
              :who="one.who"
              :name-class="one.unread ? 'font-semibold text-ink-gray-9' : 'text-ink-gray-7'"
            />
            <span class="shrink-0 text-p-xs tabular-nums text-ink-gray-5">
              {{ when(one.at) }}
            </span>
            <!-- `.prevent` because the whole row is a link: without it, starring
                 also opens the conversation. -->
            <Button
              variant="ghost"
              size="sm"
              :icon="one.starred ? 'lucide-star' : 'lucide-star-off'"
              :label="one.starred ? 'Unstar' : 'Star'"
              :tooltip="one.starred ? 'Unstar' : 'Star'"
              :class="one.starred ? 'text-ink-amber-3' : ''"
              data-slot="mail-star"
              @click.prevent.stop="toggleStar(one)"
            />
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

        <!-- The list held the first fifty messages and stopped, which on a real
             mailbox is not a limit but a broken screen. -->
        <div v-if="more" class="p-2">
          <Button
            class="w-full"
            variant="subtle"
            :label="loadingMore ? 'Loading…' : 'Older conversations'"
            :loading="loadingMore"
            data-slot="mail-more"
            @click="loadMore()"
          />
        </div>
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
          <div class="flex items-start justify-between gap-3">
            <SenderChip
              card
              class="text-p-sm"
              :sender="one.sender"
              :who="one.who"
              name-class="font-medium text-ink-gray-8"
            />
            <span class="shrink-0 text-p-xs text-ink-gray-5">
              {{ when(one.communication_date) }}
            </span>
          </div>
          <span class="mt-0.5 block text-p-xs text-ink-gray-5">to {{ one.recipients }}</span>

          <!--
            Remote images held back until asked for. Frappe strips the
            dangerous half of inbound HTML on save — a `<script>` and an
            `onerror` never reach the database — so what is left is the
            privacy half, and nothing strips that: a 1×1 image on somebody
            else's server reports the moment a message was opened, by whom,
            from where.
          -->
          <div
            v-if="one.held"
            class="mt-3 flex items-center gap-2 rounded-6 bg-surface-gray-2 px-3 py-2"
            data-slot="mail-blocked-images"
          >
            <Icon name="lucide-image-off" class="size-3.5 text-ink-gray-5" :aria-hidden="true" />
            <span class="flex-1 text-p-xs text-ink-gray-6">
              {{ one.held }} image{{ one.held > 1 ? 's' : '' }} not loaded, so the
              sender is not told you opened this.
            </span>
            <Button variant="ghost" size="sm" label="Show images" @click="reveal(one)" />
          </div>

          <!-- eslint-disable-next-line vue/no-v-html -->
          <div class="prose-sm mt-3 max-w-none text-ink-gray-8" v-html="one.body" />

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

        <div class="mt-4 flex items-center gap-2">
          <Button
            variant="subtle"
            icon-left="lucide-reply"
            label="Reply"
            @click="compose(last, 'reply')"
          />
          <Button
            variant="ghost"
            icon-left="lucide-reply-all"
            label="Reply to all"
            data-slot="mail-reply-all"
            @click="compose(last, 'reply_all')"
          />
          <Button
            variant="ghost"
            icon-left="lucide-forward"
            label="Forward"
            data-slot="mail-forward"
            @click="compose(last, 'forward')"
          />
          <!--
            Filing the conversation, not the message. Filing a reply and
            leaving the original in the inbox is the behaviour every mail
            client got complained about until it stopped.
          -->
          <Button
            variant="ghost"
            icon-left="lucide-archive"
            label="Archive"
            data-slot="mail-archive"
            @click="act('archive')"
          />
          <Button
            variant="ghost"
            icon-left="lucide-trash-2"
            label="Delete"
            data-slot="mail-delete"
            @click="act('bin')"
          />
          <Button
            variant="ghost"
            icon-left="lucide-mail"
            label="Mark unread"
            data-slot="mail-unread"
            @click="act('unread')"
          />
          <Dropdown v-if="fileable.length" :options="fileable">
            <Button
              variant="ghost"
              icon-left="lucide-folder-input"
              label="Move to"
              data-slot="mail-move"
            />
          </Dropdown>
        </div>
      </div>
    </div>

    <Dialog v-model="writing" :title="writingTitle" size="xl">
      <div class="flex flex-col gap-3">
        <Select
          v-if="addresses.length > 1"
          v-model="draft.sender"
          label="From"
          :options="addresses.map((one) => ({ label: one, value: one }))"
        />
        <div class="flex items-end gap-2">
          <FormControl
            v-model="draft.to"
            class="flex-1"
            label="To"
            placeholder="somebody@example.com"
          />
          <!-- Behind a toggle, because most messages have neither and two
               empty boxes above every one of them is two boxes to skip. -->
          <Button
            variant="ghost"
            :label="copies ? 'Hide Cc and Bcc' : 'Cc and Bcc'"
            data-slot="mail-copies"
            @click="copies = !copies"
          />
        </div>
        <FormControl v-if="copies" v-model="draft.cc" label="Cc" />
        <FormControl v-if="copies" v-model="draft.bcc" label="Bcc" />
        <FormControl v-model="draft.subject" label="Subject" />

        <!--
          The same editor a Text Editor field gets, with the same extensions:
          mail is prose, and a textarea sends a paragraph of plain text to
          somebody whose client will render it as one long line. `Editor` is
          renderless — it owns the model, the upload and the placeholder and
          draws nothing — so the toolbar is a choice made here.
        -->
        <div class="rounded-6 border border-outline-gray-2 bg-surface-base px-3 py-2">
          <Editor
            v-model="draft.content"
            :extensions="EXTENSIONS"
            format="html"
            placeholder="Write your message"
            :upload-function="uploadInline"
          >
            <template #default="{ editor }">
              <EditorFixedMenu :editor="editor" :items="articleToolbar" class="mb-2" />
              <EditorContent :editor="editor" aria-label="Message" dir="auto" />
            </template>
          </Editor>
        </div>

        <!-- What is going with it. A forward arrives here already carrying the
             original's files; anything else is added below. -->
        <div v-if="draft.attachments.length" class="flex flex-wrap gap-2">
          <span
            v-for="one in draft.attachments"
            :key="one.name"
            class="flex items-center gap-1.5 rounded-6 border border-outline-gray-2 px-2 py-1 text-p-xs text-ink-gray-7"
            data-slot="mail-attachment"
          >
            <Icon name="lucide-paperclip" class="size-3" :aria-hidden="true" />
            {{ one.file_name }}
            <Button
              variant="ghost"
              size="sm"
              icon="lucide-x"
              :label="`Remove ${one.file_name}`"
              :tooltip="`Remove ${one.file_name}`"
              @click="unattach(one)"
            />
          </span>
        </div>

        <FileUploader :private="true" @success="attach">
          <template #default="{ openFileSelector, uploading }">
            <Button
              variant="subtle"
              icon-left="lucide-paperclip"
              :label="uploading ? 'Attaching…' : 'Attach a file'"
              data-slot="mail-attach"
              @click="openFileSelector()"
            />
          </template>
        </FileUploader>

        <ErrorMessage v-if="error" :message="error" />
      </div>
      <template #actions>
        <Button variant="solid" label="Send" :loading="sending" @click="post" />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, onUnmounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import {
  Button,
  Dialog,
  Dropdown,
  Editor,
  EditorContent,
  EditorFixedMenu,
  ErrorMessage,
  FileUploader,
  FormControl,
  Icon,
  LoadingText,
  RichTextKit,
  Select,
  articleToolbar,
  dayjsLocal,
  upload,
} from '@/ui'
import EmptyState from '../components/EmptyState.vue'
import SenderChip from '../components/SenderChip.vue'
import { holdImages, loadMail, mail, showImages } from '../lib/mail'
import { workspace } from '../lib/workspace'

const loading = ref(true)
const sending = ref(false)
const error = ref('')

const route = useRoute()
const router = useRouter()

const threads = ref([])
const addresses = ref([])
const cursor = ref(0)
const more = ref(false)
const loadingMore = ref(false)

/** Two pages of conversations as one list, the older half folded into the newer. */
function merge(have, next) {
  const by = new Map(have.map((one) => [one.key, one]))
  for (const one of next) {
    const already = by.get(one.key)
    if (!already) {
      by.set(one.key, one)
      continue
    }
    already.count += one.count
    already.unread += one.unread
  }
  return [...by.values()]
}

async function loadMore() {
  loadingMore.value = true
  try {
    await load({ append: true })
  } finally {
    loadingMore.value = false
  }
}
const search = ref('')
const messages = ref([])

// Both read from the URL rather than kept beside it. One source, so a link
// pasted into the address bar opens exactly what the person who sent it saw.
const folder = computed(() => String(route.query.folder || 'all'))
const chosen = computed(() => String(route.query.thread || ''))

/** The message a reply or a forward is built from: the last one in the thread. */
const last = computed(() => messages.value[messages.value.length - 1] || null)

const openSubject = computed(
  () => threads.value.find((one) => one.key === chosen.value)?.subject || '',
)

// Where this conversation can go: the folders of the address it is in. An
// address it is not in has folders on a server that has never seen it.
const fileable = computed(() => {
  const address = owner.value
  if (!address) return []
  return mail.folders
    .filter((one) => one.address === address && one.folder && one.folder !== SENT_KEY)
    .map((one) => ({
      label: one.label,
      icon: one.icon,
      onClick: () => moveTo(address, one.folder),
    }))
})

// The one folder name that is not a folder — see `mailbox.SENT`. A conversation
// cannot be filed into it, because it is a question about the sender.
const SENT_KEY = '__sent'

/** Which of this person's addresses the open conversation belongs to. */
const owner = computed(() => {
  const here = messages.value[0]
  return (
    mail.folders.find((one) => one.key === folder.value)?.address ||
    (here?.recipients || '')
      .split(',')
      .map((one) => one.trim())
      .find((one) => mail.addresses.includes(one)) ||
    mail.addresses[0] ||
    ''
  )
})

async function toggleStar(one) {
  one.starred = !one.starred
  await workspace.mailStar(one.key, folder.value, one.starred)
}

/**
 * Archive, delete, or put back to unread.
 *
 * Delete is a move to Trash and not `delete_doc`: removing the document would
 * take the message off the record it is filed against and away from everybody
 * else who holds the address, permanently, on a click every mail client has
 * taught people is reversible.
 */
async function act(what) {
  const address = owner.value
  if (what === 'unread') {
    await workspace.mailMarkUnread(chosen.value, folder.value)
  } else if (what === 'archive') {
    await workspace.mailArchive(chosen.value, address, folder.value)
  } else {
    await workspace.mailBin(chosen.value, address, folder.value)
  }
  // Back to the list: the conversation somebody just filed away is not the
  // thing they want still open in front of them.
  router.push({ name: 'Mail', query: { folder: folder.value } })
  await load()
  await loadMail({ reload: true })
}

async function moveTo(address, into) {
  await workspace.mailFileThread(chosen.value, address, into, folder.value)
  await load()
  await read()
}

const writing = ref(false)
const copies = ref(false)
const draft = reactive({
  sender: '', to: '', cc: '', bcc: '', subject: '', content: '',
  in_reply_to: '', attachments: [],
})
const writingTitle = ref('New message')

// The same extensions a Text Editor field gets. Mail is the long-form case, so
// it wants the article bundle rather than the comment one.
const EXTENSIONS = [RichTextKit]

/** Where an image pasted into the body goes: a private File, like any other. */
const uploadInline = (file) => upload(file, { private: true })

// The same relative wording the record timeline uses, from the same helper.
const when = (value) => (value ? dayjsLocal(value).fromNow() : '')

async function boot() {
  // The rail is the shell's sidebar and fetches the same list, so this reads
  // it from the shared store rather than asking again — two requests would
  // draw the rail and the compose box's From list a beat apart.
  const found = await loadMail()
  addresses.value = found.addresses || []
  draft.sender = addresses.value[0] || ''
  await load()
}

async function load({ append = false } = {}) {
  if (!append) loading.value = true
  try {
    const found = await workspace.mailThreads(
      folder.value,
      append ? cursor.value : 0,
      search.value,
    )
    // Merged by key rather than concatenated. A conversation can straddle two
    // pages — the grouping happens per page of *messages* — and appending
    // blindly would show it twice with half its messages in each.
    threads.value = append ? merge(threads.value, found.threads || []) : (found.threads || [])
    cursor.value = found.next || 0
    more.value = !!found.more
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
/** A file finished uploading — remember it for the send. */
function attach(file) {
  draft.attachments.push({ name: file.name, file_name: file.file_name || file.name })
}

function unattach(one) {
  draft.attachments = draft.attachments.filter((row) => row.name !== one.name)
}

/** Put one message's remote images back, for this reading only. */
function reveal(one) {
  one.body = showImages(one.body)
  one.held = 0
}

async function read() {
  if (!chosen.value) {
    messages.value = []
    return
  }
  // Held here rather than server-side: the message stays whole in the
  // database, which is what makes "show images" a swap in the browser instead
  // of another round trip, and what keeps a forward or a print correct.
  messages.value = (await workspace.mailThread(chosen.value, folder.value)).map((one) => {
    const { body, held } = holdImages(one.content)
    return { ...one, body, held }
  })

  const names = messages.value.map((one) => one.name)
  if (names.length) {
    await workspace.mailMarkRead(names)
    const thread = threads.value.find((one) => one.key === chosen.value)
    if (thread) thread.unread = 0
  }
}

const TITLES = { reply: 'Reply', reply_all: 'Reply to all', forward: 'Forward' }

/**
 * Open the composer, blank or carrying a message.
 *
 * The carrying case is built on the server — see `mailbox.draft`. Quoting in
 * the browser would quote the copy the reader is looking at, which has had its
 * remote images held back, and send somebody a reply full of empty `<img>`.
 */
async function compose(from, kind = 'reply') {
  error.value = ''
  copies.value = false
  Object.assign(draft, {
    to: '', cc: '', bcc: '', subject: '', content: '', in_reply_to: '', attachments: [],
  })
  writingTitle.value = 'New message'

  if (from) {
    writingTitle.value = TITLES[kind] || 'Reply'
    const opening = await workspace.mailDraft(from.name, kind)
    Object.assign(draft, opening, { bcc: '' })
    draft.attachments = opening.attachments || []
    copies.value = !!opening.cc
  } else if (!draft.sender) {
    draft.sender = addresses.value[0] || ''
  }
  writing.value = true
}

async function post() {
  error.value = ''
  sending.value = true
  try {
    await workspace.mailSend({
      ...draft,
      // Names, not the files. They are already on the site; sending the bytes
      // back through this call would be a second upload of what we hold.
      attachments: JSON.stringify(draft.attachments.map((one) => one.name)),
    })
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
watch(folder, () => load())
watch(search, () => load())
watch([chosen, folder], read, { immediate: true })

// --- mail arriving ----------------------------------------------------------
//
// A list left open stops being a photograph of when it was opened. Frappe
// publishes `list_update` for every document that changes and inbound mail is a
// `Communication`, so this is the same seam the record lists already use — the
// bell's one-minute poll is for the rail, not for the screen somebody is
// looking at.
//
// Coalesced: an IMAP sync that pulls forty messages publishes forty of these in
// a second, and one refetch each is a list that spends its afternoon reloading.
let pending = null
const arrived = onDoctypeChange('Communication', () => {
  clearTimeout(pending)
  pending = setTimeout(() => {
    // Only the first page. Somebody who has paged back four screens and is
    // reading does not want the list to collapse under them because a
    // newsletter arrived.
    if (cursor.value <= PAGE_ONE) load()
  }, 400)
})

const PAGE_ONE = 50

onUnmounted(() => {
  clearTimeout(pending)
  if (arrived) arrived()
})
</script>
