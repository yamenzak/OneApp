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
      class="relative flex w-full shrink-0 flex-col border-r border-outline-gray-1 sm:w-96"
      :class="chosen ? 'hidden sm:flex' : 'flex'"
    >
      <div class="flex items-center gap-2 border-b border-outline-gray-1 p-2">
        <FormControl
          v-model="search"
          class="flex-1"
          type="text"
          placeholder="Search mail"
          data-slot="mail-search"
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
            <!--
              The tick, on a span that stops the click.

              `.stop` and not `.prevent`, which took a while to be sure of: the
              whole row is a link, and stopping the click short of the anchor is
              what keeps selecting a conversation from also opening it. Adding
              `.prevent` looks equivalent and is not — the browser undoes a
              cancelled checkbox's own toggle *after* Vue has already patched
              the input from our state, so the box ends up unticked while the
              selection says otherwise. Measured, not reasoned: the bar appeared
              saying "1 selected" over a box with nothing in it.

              Shift is read off the event: shift-clicking a second tick takes
              everything between, which is the one thing that makes a list of
              fifty selectable by hand.
            -->
            <span
              class="flex shrink-0 items-center"
              @click.stop="pick(one, $event)"
            >
              <Checkbox
                :model-value="picked.has(one.key)"
                data-slot="mail-pick"
                :aria-label="`Select ${one.subject}`"
              />
            </span>
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

      <!--
        What a selection is for. The same bar the record lists draw, in the same
        place, because "several things are ticked and here is what you can do
        with them" is one idea and this product should have one of it.
      -->
      <SelectionBar
        v-if="picked.size"
        :count="picked.size"
        :total="threads.length"
        @clear="picked.clear()"
        @all="pickAll"
      >
        <!-- Icons, not labels: the list column is 384px and four labelled
             buttons plus a count and Select all do not fit in it — the count
             was pushed off the left edge, which is the one thing on the bar
             somebody actually has to read. -->
        <Button variant="ghost" icon="lucide-archive" label="Archive" tooltip="Archive" @click="act('archive')" />
        <Button variant="ghost" icon="lucide-trash-2" label="Delete" tooltip="Move to Trash" @click="act('bin')" />
        <Button variant="ghost" icon="lucide-mail" label="Unread" tooltip="Mark unread" @click="act('unread')" />
        <Button variant="ghost" icon="lucide-star" label="Star" tooltip="Star" @click="act('star')" />
      </SelectionBar>
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

        <!--
          The conversation itself: read messages closed to a row, a long read
          run folded, and a line where the new mail starts. See
          `components/mail/Thread.vue` — it is enough rules to be worth its own
          file, and this page was long enough already.
        -->
        <Thread class="mt-4" :messages="messages" @preview="previewing = $event" />

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
      What just happened, and the window in which it can be taken back.

      One bar for two things that are the same thing. "Sent" is not a countdown
      in the browser that a closed tab defeats — the message really is held, by
      the framework's own `send_after`, and the queue refuses to pick it up
      until the window passes. "Archived 11" is the note `bulk` handed back,
      which `restore` reads to put every one of them where it was.
    -->
    <div
      v-if="note"
      class="fixed bottom-8 left-1/2 z-20 flex -translate-x-1/2 items-center gap-3 rounded-6 border border-outline-gray-2 bg-surface-elevation-2 px-4 py-2 shadow-xl"
      data-slot="mail-undo"
    >
      <span class="text-p-sm text-ink-gray-8">{{ note.text }}</span>
      <!-- Only where there is something to undo. A message that arrived on a
           routed address was in no folder to begin with, so there is nowhere to
           put it back to — and an Undo that does nothing is worse than none. -->
      <Button v-if="note.run" variant="ghost" size="sm" label="Undo" @click="undo()" />
    </div>

    <!-- Every shortcut this screen answers to, because one nobody can find is
         one nobody uses. `?` opens it, which is itself in the list. -->
    <ShortcutsDialog v-model="showingKeys" :groups="SHORTCUTS" />

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
  Checkbox,
  Dropdown,
  FormControl,
  LoadingText,
  PageHeader,
  dayjsLocal,
  debounce,
} from '@/ui'
import EmptyState from '../components/EmptyState.vue'
import SelectionBar from '../components/screen/bodies/SelectionBar.vue'
import ShortcutsDialog from '../components/mail/ShortcutsDialog.vue'
import SenderChip from '../components/mail/SenderChip.vue'
import MailComposer from '../components/mail/MailComposer.vue'
import Thread from '../components/mail/Thread.vue'
import FilePreview from '../components/drive/FilePreview.vue'
import { onDoctypeChange } from '../lib/socket'
import { MOD, useShortcuts } from '../lib/shortcuts'
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

// --- a selection ------------------------------------------------------------
//
// Reading a morning's post is the same three actions forty times. Doing them
// one conversation at a time is the whole cost of a mail reader, which is why
// every one of them lets you tick a row.

/** The conversations ticked, by key. */
const picked = ref(new Set())

/** The last one ticked, so shift can take everything between. */
let anchor = ''

function pick(one, event) {
  const keys = threads.value.map((row) => row.key)
  const at = keys.indexOf(one.key)

  // Shift takes the run. Not a nicety: without it a list of fifty is fifty
  // clicks, and the reason people fall back to the mouse and the menu.
  if (event?.shiftKey && anchor && keys.includes(anchor)) {
    const from = keys.indexOf(anchor)
    const [start, end] = from < at ? [from, at] : [at, from]
    keys.slice(start, end + 1).forEach((key) => picked.value.add(key))
  } else if (picked.value.has(one.key)) {
    picked.value.delete(one.key)
  } else {
    picked.value.add(one.key)
  }

  anchor = one.key
}

const pickAll = () => threads.value.forEach((row) => picked.value.add(row.key))

/** What the bar says afterwards, and what pressing it again would mean. */
const WORDS = {
  archive: 'Archived',
  bin: 'Moved to Trash',
  unread: 'Marked unread',
  read: 'Marked read',
  star: 'Starred',
  unstar: 'Unstarred',
}

/** For the flags, undo is the opposite flag: nothing moved, so nothing to put back. */
const OPPOSITE = { unread: 'read', read: 'unread', star: 'unstar', unstar: 'star' }

/** The two that move mail, and so the two Undo has to put back. Matches `MOVES`
 *  in `mailbox/selections.py`, which is what decides whether a note comes back. */
const MOVES = ['archive', 'bin']

/**
 * Do one thing to the selection — or, when nothing is ticked, to the open
 * conversation.
 *
 * One path for both, because they are one action with two ways of saying which
 * mail. It is also what gives the header's own Archive an Undo, which it did
 * not have: filing away a conversation somebody is reading is exactly as easy
 * to do by mistake as filing eleven.
 *
 * Delete is a move to Trash and not `delete_doc`: removing the document would
 * take the message off the record it is filed against and away from everybody
 * else who holds the address, permanently, on a click every mail client has
 * taught people is reversible.
 */
async function act(what) {
  const keys = picked.value.size ? [...picked.value] : chosen.value ? [chosen.value] : []
  if (!keys.length) return false

  const address = owner.value
  const done = await workspace.mailBulk(what, keys, address, folder.value)
  picked.value.clear()

  const count = done?.done || keys.length
  const said = keys.length > 1 ? `${WORDS[what]} ${count}` : WORDS[what]

  // Conversations whose folder the server actually recorded. Mail that arrived
  // on a routed address was in no folder at all, and inventing an INBOX it
  // never had would file it somewhere new under the word Undo.
  const back = (done?.was || []).filter((row) => row.folder)

  if (MOVES.includes(what)) {
    announce(
      said,
      back.length
        ? async () => {
            await workspace.mailUndoBulk(back, address, folder.value)
            await load()
            await loadMail({ reload: true })
          }
        : null,
    )
  } else {
    // Nothing moved, so there is nothing to put back — the way back from a flag
    // is the opposite flag.
    announce(said, async () => {
      await workspace.mailBulk(OPPOSITE[what], keys, address, folder.value)
      await load()
      await loadMail({ reload: true })
    })
  }

  // Back to the list, but only if the conversation in front of somebody is one
  // of the ones that just moved. Marking three others unread should not close
  // what they are reading.
  if (chosen.value && keys.includes(chosen.value) && MOVES.includes(what)) {
    router.push({ name: 'Mail', query: { folder: folder.value } })
  }
  await load()
  await loadMail({ reload: true })
  return true
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

/**
 * The one thing that can be taken back, and for how long.
 *
 * `{ text, undo }`, and there is only ever one: two floating bars stacked on
 * each other is a screen apologising twice. Sending sets it for exactly as long
 * as the server holds the message; a bulk action sets it for fifteen seconds,
 * which is long enough to notice forty conversations vanish.
 */
const note = ref(null)
let undoTimer = null

function announce(text, run, seconds = 15) {
  clearTimeout(undoTimer)
  note.value = { text, run }
  undoTimer = setTimeout(() => { note.value = null }, seconds * 1000)
}

async function undo() {
  const run = note.value?.run
  note.value = null
  clearTimeout(undoTimer)
  await run?.()
}

async function afterSend(done) {
  announce('Sent', () => unsend(done?.name || ''), done?.undo_seconds || 15)
  await load()
}

async function unsend(name) {
  const done = await workspace.mailUnsend(name)
  // Straight back into the composer with what was sent, because "undo" that
  // discards the message is not undo.
  if (done?.ok) await composer.value?.reopen()
  await load()
}

// --- the keyboard -----------------------------------------------------------
//
// Gmail's letters, because Frappe Mail uses them, Outlook and Superhuman use
// them, and a product that picks different ones is asking people to learn
// something for nothing. See `lib/shortcuts.js` for the two rules that keep
// them from firing while somebody is typing.

const showingKeys = ref(false)

/** The list, in the shape the dialog draws — and the source of the bindings. */
const SHORTCUTS = [
  {
    title: 'Moving about',
    keys: [
      [['J'], 'Next conversation'],
      [['K'], 'Previous conversation'],
      [['/'], 'Search'],
      [['Esc'], 'Clear the selection, or close the conversation'],
      [['?'], 'This list'],
    ],
  },
  {
    title: 'Writing',
    keys: [
      [['C'], 'Write'],
      [['R'], 'Reply'],
      [['Shift', 'R'], 'Reply to all'],
      [['F'], 'Forward'],
    ],
  },
  {
    title: 'Filing',
    keys: [
      [['E'], 'Archive'],
      [['#'], 'Move to Trash'],
      [['U'], 'Mark unread'],
      [['S'], 'Star'],
    ],
  },
  {
    title: 'Selecting',
    keys: [
      [['X'], 'Tick this conversation'],
      [[MOD, 'A'], 'Tick everything on this page'],
      [[MOD, 'Z'], 'Undo the last thing'],
    ],
  },
]

/** Open the conversation `by` rows away from the one open now. */
function step(by) {
  const keys = threads.value.map((row) => row.key)
  if (!keys.length) return false
  const at = keys.indexOf(chosen.value)
  const next = keys[Math.min(Math.max(at + by, 0), keys.length - 1)]
  router.push({ name: 'Mail', query: { folder: folder.value, thread: next } })
}

function escape() {
  if (picked.value.size) picked.value.clear()
  else if (chosen.value) router.push({ name: 'Mail', query: { folder: folder.value } })
  else return false
}

useShortcuts({
  j: () => step(1),
  k: () => step(-1),
  // The search box is found rather than held in a ref: `FormControl` renders
  // the control it is told to and the attribute rides down to it, so this asks
  // the document for the thing somebody would have clicked.
  '/': () => document.querySelector('[data-slot="mail-search"]')?.focus(),
  escape,
  '?': () => { showingKeys.value = true },

  c: () => compose(),
  r: () => compose(last.value, 'reply'),
  'shift+r': () => compose(last.value, 'reply_all'),
  f: () => compose(last.value, 'forward'),

  e: () => act('archive'),
  '#': () => act('bin'),
  u: () => act('unread'),
  s: () => act('star'),

  x: () => {
    const row = threads.value.find((one) => one.key === chosen.value)
    if (!row) return false
    pick(row)
  },
  'mod+a': pickAll,
  'mod+z': () => (note.value ? undo() : false),
})

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
