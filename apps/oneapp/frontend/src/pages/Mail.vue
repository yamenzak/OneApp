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
  <!--
    The folder list, on a phone.

    The shell draws a sidebar only on a desktop — `MobileShell` has no such
    slot — so without this every mailbox, every folder and the bin were
    unreachable from a phone: the page opened on `folder=all` and offered no
    way out of it. Drive answers the same problem the same way (`Drive.vue`,
    the places dropdown), off the same list the sidebar draws, so the two
    cannot drift.

    Only on a phone. On a desktop it would be a second control saying what the
    sidebar beside it already says. Write is not here either — it is over the
    list already, on both layouts.
  -->
  <PageHeader v-if="isMobile">
    <Dropdown :options="folderOptions">
      <Button
        data-slot="mail-folders"
        icon-right="lucide-chevron-down"
        variant="ghost"
        :label="folderName"
      />
    </Dropdown>
  </PageHeader>

  <div class="flex h-full min-h-0">
    <!--
      What has arrived.

      On a phone the two panes are one screen at a time: the list until a
      conversation is open, the conversation after. Which is the same thing the
      URL already says — `?thread=` — so this is a class and not a second state
      to keep in step, and the back button still closes a conversation.
    -->
    <div
      class="flex w-full shrink-0 flex-col border-r border-outline-gray-1 sm:w-96"
      :class="chosen ? 'hidden sm:flex' : 'flex'"
    >
      <div class="flex items-center gap-2 border-b border-outline-gray-1 p-2">
        <FormControl
          v-model="search"
          class="flex-1"
          type="text"
          placeholder="Search mail"
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
              icon="lucide-star"
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
    <div class="flex min-w-0 flex-1 flex-col" :class="chosen ? 'flex' : 'hidden sm:flex'">
      <EmptyState
        v-if="!chosen"
        icon="lucide-mail-open"
        title="Nothing open"
        description="Pick a conversation."
      />

      <div v-else class="min-h-0 flex-1 overflow-y-auto p-5">
        <!-- The phone has no second column to go back to, so it needs a way
             out. `sm:hidden` because on a desktop the list never left. -->
        <RouterLink
          class="sm:hidden"
          :to="{ name: 'Mail', query: { folder } }"
          data-slot="mail-back"
        >
          <Button variant="ghost" icon-left="lucide-arrow-left" label="All conversations" />
        </RouterLink>
        <h2 class="mt-2 text-lg font-semibold text-ink-gray-9 sm:mt-0">{{ openSubject }}</h2>

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
            The body, in a document of its own.

            This was a `v-html` div with a regex holding the images back, and
            both halves were wrong. The div meant a sender's `<style>` block
            applied to *our* application; the regex held two of six ordinary
            tracking-pixel shapes and leaked the rest — `<img src = "…">` with
            spaces, `srcset`, `style="background:url(…)"`,
            `<picture><source>`. The banner said "hidden to protect your
            privacy" while a CSS background pixel loaded.

            This is Frappe's reader, vendored: DOMPurify, then a DOM pass that
            blanks remote `<img>`, inline `[style]` and `<style>` alike, then a
            `srcdoc` iframe that grows to its own height. It draws its own
            "images hidden" banner, so ours is gone with the regex behind it.
            See `components/mail/reader/VENDORED.md`.
          -->
          <div class="mt-3" data-slot="mail-body">
            <EmailContent :content="one.content" block-images />
          </div>

          <div v-if="one.attachments?.length" class="mt-3 flex flex-wrap gap-2">
            <AttachmentChip
              v-for="file in one.attachments"
              :key="file.name"
              :file="file"
              @open="previewing = file"
            />
          </div>
        </article>

        <div class="mt-4 flex flex-wrap items-center gap-2">
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

    <!--
      The window in which "Sent" can be taken back. Not a countdown in the
      browser that a closed tab defeats: the message really is held, by the
      framework's own `send_after`, and the queue refuses to pick it up until
      the window passes.
    -->
    <div
      v-if="justSent"
      class="fixed bottom-8 left-1/2 z-20 flex -translate-x-1/2 items-center gap-3 rounded-6 border border-outline-gray-2 bg-surface-elevation-2 px-4 py-2 shadow-xl"
      data-slot="mail-undo"
    >
      <span class="text-p-sm text-ink-gray-8">Sent</span>
      <Button variant="ghost" size="sm" label="Undo" @click="unsend()" />
    </div>

    <!--
      An attachment opens in the Drive's own previewer, because a mail
      attachment *is* a Drive file — the same `File` row, the same object, the
      same permission check on the way to the bytes. A second viewer here would
      be a second thing to keep in step with the first.
    -->
    <FilePreview v-model="preview" :file="previewing" />

    <MailComposer
      ref="composer"
      v-model="writing"
      :addresses="addresses"
      @sent="afterSend"
    />
  </div>
</template>

<script setup>
import { computed, onUnmounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import {
  Button,
  Dropdown,
  FormControl,
  LoadingText,
  PageHeader,
  dayjsLocal,
  debounce,
} from '@/ui'
import EmptyState from '../components/EmptyState.vue'
import SenderChip from '../components/mail/SenderChip.vue'
import MailComposer from '../components/mail/MailComposer.vue'
import EmailContent from '../components/mail/reader/EmailContent.vue'
import AttachmentChip from '../components/mail/AttachmentChip.vue'
import FilePreview from '../components/drive/FilePreview.vue'
import { onDoctypeChange } from '../lib/socket'
import { useIsMobile } from '../lib/screen'
import { loadMail, mail } from '../lib/mail'
import { workspace } from '../lib/workspace'

const loading = ref(true)

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

// Which attachment is being looked at, and therefore whether the previewer is
// open at all — one ref rather than two kept in step by hand.
const previewing = ref(null)
const preview = computed({
  get: () => !!previewing.value,
  set: (showing) => { if (!showing) previewing.value = null },
})

const isMobile = useIsMobile()

/**
 * Every folder the sidebar draws, as dropdown options.
 *
 * Off `mail.folders` — the same list `MailSidebar` reads — rather than a copy,
 * so a mailbox connected on a desktop appears on the phone without a second
 * place to remember. Quiet folders (spam, drafts, the bin) are in, because on
 * a phone this dropdown is the *only* way to any of them.
 *
 * Grouped by address rather than indented, because a folder belongs to a
 * mailbox: two people's Archives are two folders, and a flat list that loses
 * which is which is a list you cannot act on. `depth: 0` rows are the mailboxes
 * themselves and become the headings.
 */
const folderOptions = computed(() => {
  const groups = []
  const into = (option) => {
    if (groups.length) groups[groups.length - 1].options.push(option)
    else groups.push({ group: '', hideLabel: true, options: [option] })
  }

  for (const one of mail.folders) {
    const option = {
      label: one.label,
      icon: one.icon,
      onClick: () => router.push({ name: 'Mail', query: { folder: one.key } }),
    }

    // "All mail" belongs to no address — it is the union — so it sits above the
    // groups rather than starting one.
    if (!one.address) into(option)
    else if (one.depth) into(option)
    else {
      // The address heads its own group, and the row under it is that
      // mailbox's inbox: `reading.py` says the address *is* the inbox, and
      // repeating "sales@4dl.app" under the heading "sales@4dl.app" says
      // nothing twice.
      groups.push({
        group: one.label,
        options: [{ ...option, label: 'Inbox', icon: 'lucide-inbox' }],
      })
    }
  }
  return groups
})

/**
 * What the button says.
 *
 * `All mail` is the fallback and not a bug: the server only lists that row when
 * there is more than one mailbox (see `mailbox/reading.py`), and with one
 * mailbox `?folder=all` is still the state the page opens in.
 */
const folderName = computed(
  () => mail.folders.find((one) => one.key === folder.value)?.label || 'All mail',
)

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



// The same relative wording the record timeline uses, from the same helper.
const when = (value) => (value ? dayjsLocal(value).fromNow() : '')

async function boot() {
  // The rail is the shell's sidebar and fetches the same list, so this reads
  // it from the shared store rather than asking again — two requests would
  // draw the rail and the compose box's From list a beat apart.
  const found = await loadMail()
  addresses.value = found.addresses || []
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



async function read() {
  if (!chosen.value) {
    messages.value = []
    return
  }
  // Whole, as it was received. `EmailContent` sanitises and holds the images
  // back at render time, so the stored message stays intact — which is what
  // keeps a forward or a print correct, and what makes "show images" a swap
  // in the browser rather than another round trip.
  messages.value = await workspace.mailThread(chosen.value, folder.value)

  const names = messages.value.map((one) => one.name)
  if (names.length) {
    await workspace.mailMarkRead(names)
    const thread = threads.value.find((one) => one.key === chosen.value)
    if (thread) thread.unread = 0
  }
}




const composer = ref(null)

/** Open the composer, blank or carrying a message. */
const compose = (from, kind) => composer.value?.compose(from, kind)

const justSent = ref('')
let undoTimer = null

// The undo bar lives exactly as long as the server is holding the message.
async function afterSend(done) {
  justSent.value = done?.name || ''
  clearTimeout(undoTimer)
  undoTimer = setTimeout(() => { justSent.value = '' }, (done?.undo_seconds || 15) * 1000)
  await load()
}

async function unsend() {
  const name = justSent.value
  justSent.value = ''
  clearTimeout(undoTimer)
  const done = await workspace.mailUnsend(name)
  // Straight back into the composer with what was sent, because "undo" that
  // discards the message is not undo.
  if (done?.ok) await composer.value?.reopen()
  await load()
}

boot()


watch(folder, () => load())

/**
 * Search, once the typing stops.
 *
 * This was `watch(search, () => load())` — a full-text query over subject *and*
 * body on every keystroke, so "quotation" was nine searches and the answer you
 * saw was whichever raced home last. 300ms is the same pause the Drive's
 * picker uses.
 */
watch(search, debounce(() => load(), 300))
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
