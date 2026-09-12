<template>
  <!--
    Reading mail: three columns, and each answers a different question. The rail
    says *which addresses are mine*, the middle *what has arrived*, the right
    *what does this one say*.

    Deliberately not here: folders a person makes, drag and drop, labels, rules.
    Mail in this product files itself against the record it belongs to, and a
    parallel filing system beside that would be two places to look for the same
    message.
  -->
  <!--
    The folder list, on a phone. The shell draws a sidebar only on a desktop, so
    without this every mailbox and the bin were unreachable from a phone. Off
    the same list the sidebar draws, so the two cannot drift.
  -->
  <PageHeader>
    <nav data-slot="breadcrumb" aria-label="Breadcrumb" class="flex min-w-0 items-center gap-1">
      <!--
        The folder, and how you change it. On a phone a dropdown, because there
        is no rail to pick from; on a desktop the rail is the picker, so this
        says where you are and nothing more.
      -->
      <Dropdown v-if="isMobile" :options="folderOptions">
        <Button
          data-slot="mail-folders"
          icon-right="lucide-chevron-down"
          variant="ghost"
          :label="folderName"
        />
      </Dropdown>
      <Breadcrumbs v-else :items="crumbs" />
    </nav>
  </PageHeader>

  <!--
    Two panels, not one with a rule down it. The shell draws no frame on this
    route (`meta.bare`), so what has arrived and what it says are each their own
    panel with the ground between them — the same shape a screen takes when a
    record opens beside its list, and for the same reason: they are two things
    you are looking at.
  -->
  <div class="flex h-full min-h-0 gap-2">
    <!--
      What has arrived. On a phone the two panes are one screen at a time, which
      is what the URL already says — `?thread=` — so this is a class and not a
      second state to keep in step.
    -->
    <div
      class="relative flex w-full shrink-0 flex-col rounded-6 bg-surface-base md:w-96"
      :class="chosen ? 'hidden md:flex' : 'flex'"
    >
      <div class="flex items-center gap-2 border-b border-outline-gray-1 p-2">
        <!--
          The same box the lists have, and the same 300ms behind it: this
          screen had already arrived at that number on its own, in a watcher
          under the script. The `/` that focuses it and the Escape that
          clears it are the box's now.
        -->
        <ListSearch
          v-model="search"
          class="flex-1"
          :placeholder="__('Search mail')"
          @changed="load()"
        />
        <!-- Write sits over the list rather than in the rail: an action
             belongs to the thing it acts on. -->
        <Button
          variant="subtle"
          icon-left="lucide-pencil"
          :label="__('Write')"
          @click="compose()"
        />
      </div>

      <LoadingText v-if="loading" class="py-8" :text="__('Loading')" />

      <EmptyState
        v-else-if="!threads.length"
        icon="lucide-inbox"
        :title="__('No mail yet')"
        :description="
          addresses.length
            ? __('New mail for this address arrives here.')
            : __('Nobody has given you an address yet. An admin can add one in Settings.')
        "
      />

      <div v-else class="min-h-0 flex-1 overflow-y-auto">
        <!--
          A conversation is a place, so it is a link and it is in the URL: that
          is what makes the back button close a thread and a reload keep one
          open. It is also why these are `router-link`.
        -->
        <Row
          v-for="one in threads"
          :key="one.key"
          :to="{ name: 'Mail', query: { folder, thread: one.key } }"
          layout="bare"
          class="flex flex-col gap-0.5"
          :open="chosen === one.key"
          data-slot="mail-thread"
        >
          <div class="flex items-center gap-2">
            <!--
              The tick, on a span that stops the click.

              `.stop` and not `.prevent`: the browser undoes a cancelled
              checkbox's own toggle *after* Vue has patched the input from our
              state, so the box ends up unticked while the selection says
              otherwise. Measured, not reasoned — the bar said "1 selected" over
              an empty box.

              Shift is read off the event: shift-clicking a second tick takes
              everything between.
            -->
            <span
              class="flex shrink-0 items-center"
              @click.stop="pick(one, $event)"
            >
              <Checkbox
                :model-value="picked.has(one.key)"
                data-slot="mail-pick"
                :aria-label="__('Select {0}', [one.subject])"
              />
            </span>
            <!-- No hover card in the list: fifty of them is fifty listeners
                 and a card that opens while somebody is scanning. -->
            <SenderChip
              class="min-w-0 flex-1 text-p-sm"
              :sender="one.sender"
              :who="one.who"
              :name-class="one.unread ? 'font-semibold text-ink-gray-9' : 'text-ink-secondary'"
            />
            <span class="shrink-0 text-p-xs tabular-nums text-ink-muted">
              {{ when(one.at) }}
            </span>
            <!-- `.prevent` because the whole row is a link: without it,
                 starring also opens the conversation. -->
            <Button
              variant="ghost"
              size="sm"
              icon="lucide-star"
              :label="one.starred ? __('Unstar') : __('Star')"
              :tooltip="one.starred ? __('Unstar') : __('Star')"
              :class="one.starred ? 'text-ink-amber-3' : ''"
              data-slot="mail-star"
              @click.prevent.stop="toggleStar(one)"
            />
          </div>
          <span
            class="truncate text-sm"
            :class="one.unread ? 'font-medium text-ink-primary' : 'text-ink-secondary'"
          >
            {{ one.subject }}
            <span v-if="one.count > 1" class="text-ink-gray-4">({{ one.count }})</span>
          </span>
          <span class="truncate text-xs text-ink-muted">{{ one.preview }}</span>
        </Row>

        <!-- The list held the first fifty messages and stopped, which on a real
             mailbox is not a limit but a broken screen. -->
        <div v-if="more" class="p-2">
          <Button
            class="w-full"
            variant="subtle"
            :label="loadingMore ? __('Loading…') : __('Older conversations')"
            :loading="loadingMore"
            data-slot="mail-more"
            @click="loadMore()"
          />
        </div>
      </div>

      <!--
        What a selection is for. The same bar the record lists draw, in the same
        place, because "several things are ticked and here is what you can do
        with them" is one idea.
      -->
      <SelectionBar
        v-if="picked.size"
        :count="picked.size"
        :total="threads.length"
        @clear="picked.clear()"
        @all="pickAll"
      >
        <!-- Icons, not labels: the list column is 384px, and four labelled
             buttons pushed the count off the left edge. -->
        <Button variant="ghost" icon="lucide-archive" :label="__('Archive')" :tooltip="__('Archive')" @click="act('archive')" />
        <Button variant="ghost" icon="lucide-trash-2" :label="__('Move to the bin')" :tooltip="__('Move to the bin')" @click="act('bin')" />
        <Button variant="ghost" icon="lucide-mail" :label="__('Unread')" :tooltip="__('Mark unread')" @click="act('unread')" />
        <Button variant="ghost" icon="lucide-star" :label="__('Star')" :tooltip="__('Star')" @click="act('star')" />
      </SelectionBar>
    </div>

    <!-- What it says -->
    <div
      class="flex min-w-0 flex-1 flex-col rounded-6 bg-surface-base"
      :class="chosen ? 'flex' : 'hidden md:flex'"
    >
      <EmptyState
        v-if="!chosen"
        icon="lucide-mail-open"
        :title="__('Nothing open')"
        :description="__('Pick a conversation from the list.')"
      />

      <div v-else class="min-h-0 flex-1 overflow-y-auto p-5">
        <!-- The phone has no second column to go back to. `md:hidden` because
             on a desktop the list never left. -->
        <RouterLink
          class="md:hidden"
          :to="{ name: 'Mail', query: { folder } }"
          data-slot="mail-back"
        >
          <Button variant="ghost" icon-left="lucide-arrow-left" :label="__('All conversations')" />
        </RouterLink>
        <!--
          The subject, and what can be done to the *conversation*. These four
          were in the strip under the thread beside Reply and Forward, which
          read as one row of seven things you can do to "this" — and "this" was
          two different objects: Reply answers a message, Archive files the
          whole conversation. Up here they sit against the thing they act on,
          which is the title of the conversation.
        -->
        <div class="mt-2 flex items-start justify-between gap-3 md:mt-0">
          <h2 class="min-w-0 text-lg font-semibold text-ink-gray-9">{{ openSubject }}</h2>
          <!-- Icons, not labels: four labelled buttons beside a subject line
               is a second heading competing with the first. -->
          <div class="flex shrink-0 items-center gap-1">
            <Button
              variant="ghost"
              icon="lucide-archive"
              :label="__('Archive')"
              :tooltip="__('Archive')"
              data-slot="mail-archive"
              @click="act('archive')"
            />
            <Button
              variant="ghost"
              icon="lucide-trash-2"
              :label="__('Move to the bin')"
              :tooltip="__('Move to the bin')"
              data-slot="mail-delete"
              @click="act('bin')"
            />
            <Button
              variant="ghost"
              icon="lucide-mail"
              :label="__('Mark unread')"
              :tooltip="__('Mark unread')"
              data-slot="mail-unread"
              @click="act('unread')"
            />
            <Dropdown v-if="fileable.length" :options="fileable" align="end">
              <Button
                variant="ghost"
                icon="lucide-folder-input"
                :label="__('Move to')"
                :tooltip="__('Move to')"
                data-slot="mail-move"
              />
            </Dropdown>
          </div>
        </div>

        <!--
          The short version, asked for rather than fetched.

          Not drawn on opening and not cached: a summary of a two-message
          thread is a paragraph explaining two messages that are already on
          screen, and paying for one on every conversation somebody clicks
          through would be most of a workspace's credits spent on mail nobody
          needed summarised. The button is the whole of the feature's
          restraint, and it only appears on a thread long enough to be worth
          it.
        -->
        <div v-if="ai.live" class="mt-3 flex flex-col gap-2" data-slot="mail-summary">
          <!--
            Three questions about the conversation, in the order somebody
            asks them: what is this about, what does it leave me to do, and
            which record does it belong to. They are here and not in the
            answering strip below, where they would read as three more ways
            to reply — which is what they are not.

            The first two only appear on a thread long enough to be worth
            paying for. The third appears on any of them: a single message
            saying "the cladding for Al Reem" is exactly the one worth filing
            and is too short to summarise.
          -->
          <div class="flex flex-wrap items-center gap-2">
            <Button
              v-if="summarisable && !summary.running.value && !summary.text.value"
              variant="subtle"
              icon-left="lucide-sparkles"
              :label="__('Summarise this')"
              data-slot="mail-summarise"
              @click="summarise()"
            />
            <Button
              v-if="summarisable"
              variant="subtle"
              icon-left="lucide-list-checks"
              :label="__('What is waiting?')"
              :loading="noticing.running.value"
              data-slot="mail-notice"
              @click="notice()"
            />
            <Button
              variant="subtle"
              icon-left="lucide-link"
              :label="__('What is this about?')"
              :loading="placing.running.value"
              data-slot="mail-file"
              @click="place()"
            />
          </div>
          <AiGlow
            v-if="summary.running.value || summary.text.value"
            mode="block"
            :active="summary.running.value"
            :empty="!summary.text.value"
            class="rounded-6 bg-surface-gray-1 p-3"
          >
            <p class="whitespace-pre-line text-p-sm text-ink-secondary">{{ summary.text.value }}</p>
          </AiGlow>
          <!--
            One line, because that is all a filing answer is: what it filed
            and why, or that it found nothing. The link itself is on the
            record's own correspondence, and anything it was not sure enough
            to write is a card below.
          -->
          <p
            v-if="placing.text.value"
            class="text-p-sm text-ink-secondary"
            data-slot="mail-filed"
          >
            {{ placing.text.value }}
          </p>
          <ErrorMessage v-if="summary.error.value" :message="summary.error.value" />
          <ErrorMessage v-if="placing.error.value" :message="placing.error.value" />
        </div>

        <!--
          What is waiting in this conversation, as cards nobody has answered.

          Under the summary and above the thread: it is the same question one
          step further on — the summary says what this is about, and these say
          what it leaves you to do. Read back on opening rather than only
          after a run, so a card offered yesterday and never answered is still
          there today.
        -->
        <div
          v-if="waiting.length || noticing.running.value"
          class="mt-3 flex flex-col gap-2"
          data-slot="mail-suggestions"
        >
          <AiGlow
            v-if="noticing.running.value && !waiting.length"
            mode="block"
            active
            empty
            :lines="2"
            class="rounded-6 bg-surface-gray-1 p-3"
          />
          <SuggestionCard
            v-for="one in waiting"
            :key="one.name"
            :suggestion="one"
            @answered="readSuggestions()"
          />
        </div>

        <!--
          The conversation itself: read messages closed to a row, a long read run
          folded, and a line where the new mail starts. See
          `components/mail/Thread.vue`.
        -->
        <Thread
          class="mt-4"
          :messages="messages"
          @preview="previewing = $event"
          @respond="compose($event.message, $event.kind)"
        />

        <!--
          Answering the conversation, which means answering its newest message
          — the one at the bottom of the screen, right above these. Any other
          message is answered from its own ⋯ menu, because a strip down here
          cannot say which message it means.

          Disabled until there is a message to answer. `compose(null)` is not an
          error — it is the blank composer, which is the right thing for the New
          button and quietly the wrong thing here: pressed in the moment between
          the thread opening and its messages arriving, Reply opens an empty
          message instead of a reply, and nothing says so.
        -->
        <div class="mt-4 flex flex-wrap items-center gap-2">
          <Button
            variant="subtle"
            icon-left="lucide-reply"
            :label="__('Reply')"
            :disabled="!last"
            @click="compose(last, 'reply')"
          />
          <Button
            variant="ghost"
            icon-left="lucide-reply-all"
            :label="__('Reply to all')"
            data-slot="mail-reply-all"
            :disabled="!last"
            @click="compose(last, 'reply_all')"
          />
          <Button
            variant="ghost"
            icon-left="lucide-forward"
            :label="__('Forward')"
            data-slot="mail-forward"
            :disabled="!last"
            @click="compose(last, 'forward')"
          />
          <!--
            A reply somebody edits, not one they send. It opens the composer
            and writes into it — there is no "send this" anywhere near it,
            and there is not going to be.
          -->
          <Button
            v-if="last && ai.rewrite"
            variant="ghost"
            icon-left="lucide-sparkles"
            :label="__('Suggest a reply')"
            data-slot="mail-suggest"
            @click="composer?.suggestReply(last, chosen, folder)"
          />
        </div>
      </div>
    </div>

    <!--
      What just happened, and the window in which it can be taken back.

      One bar for two things that are the same thing. "Sent" is not a countdown
      a closed tab defeats — the message really is held, by the framework's own
      `send_after`. "Archived 11" is the note `bulk` handed back, which
      `restore` reads.
    -->
    <Panel ground="raised" pad="bar" elevation="over" v-if="note" class="fixed inset-x-0 bottom-8 z-20 mx-auto flex w-fit items-center gap-3" data-slot="mail-undo">
      <span class="text-p-sm text-ink-primary">{{ note.text }}</span>
      <!-- Only where there is something to undo: mail that arrived on a routed
           address was in no folder to begin with. -->
      <Button v-if="note.run" variant="ghost" size="sm" :label="__('Undo')" @click="undo()" />
    </Panel>

    <!-- Every shortcut this screen answers to, because one nobody can find is
         one nobody uses. `?` opens it, which is itself in the list. -->
    <ShortcutsDialog v-model="showingKeys" :groups="SHORTCUTS" />

    <!--
      An attachment opens in the Drive's own previewer, because a mail
      attachment *is* a Drive file — the same `File` row, the same permission
      check on the way to the bytes.
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
  Breadcrumbs,
  Button,
  Checkbox,
  Dropdown,
  ErrorMessage,
  LoadingText,
  PageHeader,
} from '@/ui'
import AiGlow from '@/shared/components/AiGlow.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import Row from '@/shared/components/Row.vue'
import ListSearch from '@/modules/onespace/components/screen/views/ListSearch.vue'
import SuggestionCard from '@/shared/components/SuggestionCard.vue'
import SelectionBar from '@/modules/onespace/components/screen/bodies/SelectionBar.vue'
import ShortcutsDialog from '@/modules/onemail/components/ShortcutsDialog.vue'
import SenderChip from '@/modules/onemail/components/SenderChip.vue'
import MailComposer from '@/modules/onemail/components/MailComposer.vue'
import Thread from '@/modules/onemail/components/Thread.vue'
import FilePreview from '@/modules/onestorage/components/FilePreview.vue'
import { onDoctypeChange } from '@/shared/lib/runtime/socket'
import { MOD, useShortcuts } from '@/modules/onespace/lib/shell/shortcuts'
import { useIsMobile } from '@/modules/onespace/lib/shell/breakpoint'
import { useAiRun } from '@/shared/lib/ai/run'
import { writingVerbs } from '@/shared/lib/ai/verbs'
import { loadMail, mail } from '@/modules/onespace/lib/shell/mail'
import { __ } from '@/shared/lib/runtime/translate'
import { workspace } from '@/shared/lib/workspace'
import Panel from '@/shared/components/Panel.vue'
import { ago } from '@/shared/lib/runtime/format'

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

// Both read from the URL rather than kept beside it, so a link pasted into the
// address bar opens exactly what the person who sent it saw.
const folder = computed(() => String(route.query.folder || 'all'))
const chosen = computed(() => String(route.query.thread || ''))

// Which attachment is being looked at, and therefore whether the previewer is
// open — one ref rather than two kept in step by hand.
const previewing = ref(null)
const preview = computed({
  get: () => !!previewing.value,
  set: (showing) => { if (!showing) previewing.value = null },
})

const isMobile = useIsMobile()

/**
 * Every folder the sidebar draws, as dropdown options.
 *
 * Off `mail.folders` rather than a copy, so a mailbox connected on a desktop
 * appears on the phone. Quiet folders (spam, drafts, the bin) are in, because
 * on a phone this dropdown is the *only* way to any of them.
 *
 * Grouped by address rather than indented, because a folder belongs to a
 * mailbox: two people's Archives are two folders. `depth: 0` rows are the
 * mailboxes themselves and become the headings.
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
      // mailbox's inbox: `reading.py` says the address *is* the inbox.
      groups.push({
        group: one.label,
        options: [{ ...option, label: __('Inbox'), icon: 'lucide-inbox' }],
      })
    }
  }
  return groups
})

/**
 * What the button says. `All mail` is the fallback and not a bug: the server
 * only lists that row when there is more than one mailbox, and with one mailbox
 * `?folder=all` is still the state the page opens in.
 */
const folderName = computed(
  () => mail.folders.find((one) => one.key === folder.value)?.label || __('All mail'),
)

/** The trail. `All mail` is the root and a folder is under it — one level,
 *  because a mail folder tree is one level here. */
const crumbs = computed(() => [
  { label: __('Mail'), route: { name: 'Mail' } },
  ...(folder.value === 'all' ? [] : [{
    label: folderName.value,
    route: { name: 'Mail', query: { folder: folder.value } },
  }]),
])

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
// Reading a morning's post is the same three actions forty times, which is why
// every row can be ticked.

/** The conversations ticked, by key. */
const picked = ref(new Set())

/** The last one ticked, so shift can take everything between. */
let anchor = ''

function pick(one, event) {
  const keys = threads.value.map((row) => row.key)
  const at = keys.indexOf(one.key)

  // Shift takes the run: without it a list of fifty is fifty clicks, and the
  // reason people fall back to the mouse and the menu.
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
  archive: __('Archived'),
  bin: __('Moved to Trash'),
  unread: __('Marked unread'),
  read: __('Marked read'),
  star: __('Starred'),
  unstar: __('Unstarred'),
}

/** The same, said of several. A whole sentence each rather than a word with a
 *  number stuck on the end, because where the number goes is not the same in
 *  every language. */
const WORDS_MANY = {
  archive: (n) => __('Archived {0}', [n]),
  bin: (n) => __('Moved {0} to Trash', [n]),
  unread: (n) => __('Marked {0} unread', [n]),
  read: (n) => __('Marked {0} read', [n]),
  star: (n) => __('Starred {0}', [n]),
  unstar: (n) => __('Unstarred {0}', [n]),
}

/** For the flags, undo is the opposite flag: nothing moved, so nothing to put back. */
const OPPOSITE = { unread: 'read', read: 'unread', star: 'unstar', unstar: 'star' }

/** The two that move mail, and so the two Undo has to put back. Matches `MOVES`
 *  in `mailbox/selections.py`. */
const MOVES = ['archive', 'bin']

/**
 * Do one thing to the selection — or, when nothing is ticked, to the open
 * conversation. One path for both, which is also what gives the header's own
 * Archive an Undo.
 *
 * Delete is a move to Trash and not `delete_doc`: removing the document would
 * take the message off the record it is filed against and away from everybody
 * else who holds the address, permanently.
 */
async function act(what) {
  const keys = picked.value.size ? [...picked.value] : chosen.value ? [chosen.value] : []
  if (!keys.length) return false

  const address = owner.value
  const done = await workspace.mailBulk(what, keys, address, folder.value)
  picked.value.clear()

  const count = done?.done || keys.length
  const said = keys.length > 1 ? WORDS_MANY[what](count) : WORDS[what]

  // Conversations whose folder the server actually recorded. Mail that arrived
  // on a routed address was in no folder at all, and inventing an INBOX it never
  // had would file it somewhere new under the word Undo.
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
  // of the ones that just moved.
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
const when = (value) => (value ? ago(value) : '')

async function boot() {
  // The rail is the shell's sidebar and fetches the same list, so this reads it
  // from the shared store rather than asking again.
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
    // Merged by key rather than concatenated: a conversation can straddle two
    // pages, and appending blindly would show it twice with half its messages
    // in each.
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
  // back at render time, so a forward or a print stays correct and "show
  // images" is a swap in the browser rather than another round trip.
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

// --- the short version ------------------------------------------------------
//
// Asked for, never fetched. A summary of the two-message thread somebody just
// opened is a paragraph about two messages already on screen, and buying one
// for every conversation clicked through is most of a workspace's credits
// spent on mail nobody needed summarised.

const ai = writingVerbs()
const summary = useAiRun()

//: Below both of these, a conversation is shorter than its own summary would
//: be. Either, not both: three short messages is a conversation with a shape
//: worth stating, and one long message is a page somebody has to read before
//: they know whether they needed to.
const WORTH_SUMMARISING = 3
const WORTH_SUMMARISING_CHARS = 2500

const summarisable = computed(() => {
  if (!ai.summarise) return false
  if (messages.value.length >= WORTH_SUMMARISING) return true
  const length = messages.value.reduce((sum, one) => sum + (one.content || '').length, 0)
  return length >= WORTH_SUMMARISING_CHARS
})

const summarise = () =>
  summary.start(() => workspace.mailSummarise(chosen.value, folder.value))

// A different conversation is a different summary, and the one on screen must
// not be read as being about the thread that replaced it.
watch(chosen, () => summary.reset())

// --- what it leaves you to do -----------------------------------------------
//
// The cards live on the server, so this is a read rather than something held
// from the run: a card offered yesterday and never answered is still waiting
// today, and one somebody applied from another tab is applied here too.

const noticing = useAiRun()
const waiting = ref([])

async function readSuggestions() {
  waiting.value = chosen.value
    ? (await workspace.mailSuggestions(chosen.value, folder.value).catch(() => [])) || []
    : []
}

async function notice() {
  await noticing.start(() => workspace.mailNotice(chosen.value, folder.value))
  await readSuggestions()
}

// --- and which record it is about -------------------------------------------
//
// The one AI answer here that can write something: above its confidence
// threshold the server files the message itself, with `custom_linked_by` set
// to `model` so the record's correspondence says a machine did it and
// `detach` takes it back. Below it, a card — which is why the read below runs
// after the run either way.

const placing = useAiRun()

async function place() {
  await placing.start(() => workspace.mailFile(chosen.value, folder.value))
  await readSuggestions()
}

watch([chosen, folder], () => {
  waiting.value = []
  noticing.reset()
  placing.reset()
  readSuggestions()
}, { immediate: true })

/**
 * The one thing that can be taken back, and for how long. There is only ever
 * one: two floating bars stacked on each other is a screen apologising twice.
 * Sending sets it for exactly as long as the server holds the message; a bulk
 * action for fifteen seconds.
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
  announce(__('Sent'), () => unsend(done?.name || ''), done?.undo_seconds || 15)
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
// Gmail's letters, because Frappe Mail, Outlook and Superhuman use them. See
// `lib/shell/shortcuts.js` for the two rules that keep them from firing while
// somebody is typing.

const showingKeys = ref(false)

/** The list, in the shape the dialog draws — and the source of the bindings. */
const SHORTCUTS = [
  {
    title: __('Moving about'),
    keys: [
      [['J'], __('Next conversation')],
      [['K'], __('Previous conversation')],
      [['/'], __('Search')],
      [['Esc'], __('Clear the selection, or close the conversation')],
      [['?'], __('This list')],
    ],
  },
  {
    title: __('Writing'),
    keys: [
      [['C'], __('Write')],
      [['R'], __('Reply')],
      [['Shift', 'R'], __('Reply to all')],
      [['F'], __('Forward')],
    ],
  },
  {
    title: __('Filing'),
    keys: [
      [['E'], __('Archive')],
      [['#'], __('Move to the bin')],
      [['U'], __('Mark unread')],
      [['S'], __('Star')],
    ],
  },
  {
    // Not keys, but the same question — "what can I type here?" — and the same
    // place people look for the answer.
    title: __('Searching'),
    keys: [
      [['from:'], __('Who it is from')],
      [['to:'], __('Who it went to')],
      [['subject:'], __('The subject line only')],
      [['has:attachment'], __('Carries a file')],
      [['is:unread'], __('Not read yet')],
      [['is:starred'], __('Starred')],
    ],
  },
  {
    title: __('Selecting'),
    keys: [
      [['X'], __('Tick this conversation')],
      [[MOD, 'A'], __('Tick everything on this page')],
      [[MOD, 'Z'], __('Undo the last thing')],
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

watch([chosen, folder], read, { immediate: true })

// --- mail arriving ----------------------------------------------------------
//
// Frappe publishes `list_update` for every document that changes and inbound
// mail is a `Communication`, so this is the seam the record lists already use.
// Coalesced: an IMAP sync that pulls forty messages publishes forty of these in
// a second.
let pending = null
const arrived = onDoctypeChange('Communication', () => {
  clearTimeout(pending)
  pending = setTimeout(() => {
    // Only the first page. Somebody who has paged back four screens and is
    // reading does not want the list to collapse under them.
    if (cursor.value <= PAGE_ONE) load()
  }, 400)
})

const PAGE_ONE = 50

onUnmounted(() => {
  clearTimeout(pending)
  if (arrived) arrived()
})
</script>
