<template>
  <div class="flex h-full min-h-0 flex-col">
    <!--
      Who this is, and what you can do to it.

      Where that row goes depends on the surface, and the deciding question is
      whether there is already a header on screen. On a desktop there is: the
      trail above the screen, which names the space, the screen and — while a
      record is open — the record. A second band underneath it holding two
      icons is a header that exists because a component has one, and on a
      showcase page, where the identity is in the hero as well, it was fifty
      pixels of empty white between the trail and the photograph.

      So on a desktop page the controls go *onto* the trail's line and this band
      does not render at all. A pane keeps its own: it is a column beside a list
      that has its own header, and the pane's controls belong to the pane. A
      drawer and a phone keep theirs because both cover the trail.
    -->
    <header
      v-if="!merged"
      class="flex shrink-0 items-center gap-2 border-b border-outline-gray-1 px-4 py-3"
    >
      <RecordChip
        v-if="names"
        data-slot="record-identity"
        :record="identity"
        class="min-w-0 flex-1"
      >
        <template #badge>
          <StateBadge
            v-if="statusValue"
            data-slot="record-status"
            :label="statusValue"
            :states="spec?.states || []"
          />
          <StateBadge
            v-if="docState"
            data-slot="doc-state"
            :label="docState.label"
            :theme="docState.theme"
          />
        </template>
      </RecordChip>
      <!--
        Who else has this open. Frappe's own open-doc room, which is what the
        desk's row of faces is built on — the server checks the reader may see
        the document before it lets them into it, so this is not a way to watch
        something you cannot open.
      -->
      <div v-if="others.length" class="ms-auto flex shrink-0 items-center">
        <AvatarStack :people="watching" slot-name="viewer" />
      </div>

      <RecordControls
        :class="!others.length && 'ms-auto'"
        :record="record"
        :spec="spec"
        :space-code="spaceCode"
        :screen="screen"
        :extras="extras"
        :can-write="canWrite"
        :dirty="dirty"
        :saving="saving"
        :wide="wide"
        :drawer="drawer"
        :can-resize="canResize"
        @save="save"
        @close="emit('close')"
        @reload="emit('reload')"
        @renamed="emit('renamed', $event)"
        @surface="emit('surface', $event)"
        @expand="emit('expand')"
      />
    </header>

    <!--
      The same row, on the page header's line. `defer` because the target is
      rendered by the host in the same pass as this — frappe-ui's own
      `PageHeaderBase` teleports the header itself the same way, for the same
      reason.

      Who else has it open goes with them: the faces belong beside the controls
      wherever the controls are.
    -->
    <Teleport v-if="merged" defer :to="`#${MERGE_TARGET}`">
      <AvatarStack v-if="others.length" :people="watching" slot-name="viewer" />
      <RecordControls
        :record="record"
        :spec="spec"
        :space-code="spaceCode"
        :screen="screen"
        :extras="extras"
        :can-write="canWrite"
        :dirty="dirty"
        :saving="saving"
        :wide="wide"
        :drawer="drawer"
        :can-resize="canResize"
        @save="save"
        @close="emit('close')"
        @reload="emit('reload')"
        @renamed="emit('renamed', $event)"
        @surface="emit('surface', $event)"
        @expand="emit('expand')"
      />
    </Teleport>

    <!--
      Somebody else saved it while this was open. Said rather than done: the
      reader may be halfway through typing, and replacing what is on screen
      with what is on the server is the one thing worse than being out of date.
    -->
    <PrintDialog
      v-model="showPrint"
      :space-code="spaceCode"
      :screen="screen"
      :name="record.name"
    />

    <Alert
      v-if="staleSince"
      class="mx-4 mt-3"
      theme="amber"
      title="Someone else changed this"
    >
      <template #description>
        It was saved {{ when(staleSince) }}. Reloading takes what is on the
        server; anything typed here and not saved goes with it.
      </template>
      <template #actions>
        <Button label="Reload it" @click="emit('reload')" />
      </template>
    </Alert>

    <div class="min-h-0 flex-1 overflow-y-auto px-4 py-4">
      <!--
        The top of the record, where the screen says a record is a place rather
        than a form: a photograph that fills the width, the name over it, the
        two or three numbers worth reading, and what hangs off it.

        Declared, not coded. `view_settings.showcase` in the manifest is the
        whole of it — see `oneapp_core/showcase.py` — so a screen that says
        nothing gets the form it always got, and any space that says it gets
        this page.
      -->
      <RecordShowcase
        v-if="showcase"
        :space-code="spaceCode"
        :screen="screen"
        :record="record"
        :spec="spec"
        :showcase="showcase"
        :title="identity.label"
        :compact="drawer"
        :revision="revision"
        @open="emit('open', $event)"
        @add="emit('add', $event)"
      />

      <Tabs v-model="tab">
        <!--
          The strip stays put on a showcase screen. The hero is most of a
          screenful, so switching from Invoices to Payments halfway down a list
          otherwise means scrolling back up to a strip that is off the top of
          the page — and on a page whose whole point is moving between the
          things filed against one record, that is the one control that must
          not go away.

          A wrapper rather than a class on `TabList`: its own root is
          `relative`, and two position utilities on one element is a fight
          decided by which rule the stylesheet happens to emit last.
        -->
        <!--
          And it scrolls sideways rather than squeezing. Eight tabs is what a
          showcase screen with four related ones comes to, and in a drawer that
          is narrower than the page they came from the last two were off the
          edge with nothing to say so.
        -->
        <div
          class="-mx-4 overflow-x-auto px-4"
          :class="showcase ? 'sticky top-0 z-10 bg-surface-base' : ''"
        >
          <TabList>
            <!--
              A glyph on every one of them, from the same derivation the
              doctype's own tabs use — these four are labels like any other, and
              a strip where the doctype's tabs carry icons and ours do not would
              read as two different strips.
            -->
            <TabTrigger value="fields" label="Details" :icon-left="tabIcon('Details')" />
            <!--
              The other screens in this space that point back at this record —
              a project's quotations, its purchase orders, its invoices, its
              payments — as tabs beside the record's own.

              Second, not last: on a screen that declares them these are what the
              record is *for*, and Activity, Files and Meta are what every record
              has. Each is another screen filtered to this one, so opening one is
              the same list the rail opens with a narrower question asked of it.
            -->
            <TabTrigger
              v-for="one in related"
              :key="one.screen"
              :value="`related:${one.screen}`"
              :label="one.label || one.screen"
              :icon-left="one.icon || tabIcon(one.label || '')"
            />
            <!--
              The count as a badge rather than inside the word: "Comments (3)"
              reads as a label, a badge reads as a number. `#suffix` is the slot
              TabTrigger ships for exactly this — the first version put the badge
              in the default slot, which replaces the label region, so the label
              and the icon had to be rebuilt by hand around it.
            -->
            <!--
              One tab, not two. "Who changed this" and "what did they say about
              it" were separate places, and answering "what happened on Tuesday"
              meant reading both and merging them by eye. The comment count still
              rides here, because a comment is the entry somebody is waiting on.
            -->
            <TabTrigger value="activity" label="Activity" :icon-left="tabIcon('Activity')">
              <template #suffix>
                <Badge
                  v-if="commentCount"
                  :label="String(commentCount)"
                  theme="gray"
                  variant="subtle"
                />
              </template>
            </TabTrigger>
            <!--
              The mail about this record. Beside Activity rather than inside it:
              a comment is something a colleague said in here, a message is
              something somebody said from outside, and merging the two would
              lose the distinction that matters most about correspondence — it
              left the building.
            -->
            <TabTrigger value="mail" label="Mail" :icon-left="tabIcon('Mail')" />
            <TabTrigger value="files" label="Files" :icon-left="tabIcon('Files')" />
            <!--
              What the record *is*, as opposed to what it says: its id, its
              picture and its provenance. Last, because it is the tab you go to
              on purpose rather than the one you land on.
            -->
            <TabTrigger value="meta" label="Meta" :icon-left="tabIcon('Meta')" />
          </TabList>
        </div>

        <TabPanel value="fields">
          <div class="flex flex-col gap-4 pt-4">
            <RecordForm
              v-model:values="form"
              :spec="spec"
              :space-code="spaceCode"
              :screen="screen"
              :disabled="!canWrite"
            />
            <ErrorMessage v-if="error" :message="error" />
          </div>
        </TabPanel>

        <!--
          One per declared tab. A `TabPanel` mounts when it is chosen and
          unmounts when it is not — reka's own default — so a project with six
          related screens costs six requests only if somebody opens all six.
        -->
        <TabPanel
          v-for="one in related"
          :key="one.screen"
          :value="`related:${one.screen}`"
        >
          <RelatedRows
            :space-code="spaceCode"
            :screen="one.screen"
            :field="one.field"
            :name="record.name"
            :label="one.label || ''"
            @open="emit('open', $event)"
          />
        </TabPanel>

        <TabPanel value="activity">
          <RecordActivity
            :space-code="spaceCode"
            :screen="screen"
            :name="record.name"
            :record="record"
            :comments="comments"
            :changes="changes"
            :count="commentCount"
            :more="moreComments"
            :loading="loadingTimeline"
            @added="loadTimeline"
          />
        </TabPanel>

        <TabPanel value="mail">
          <RecordMail :space-code="spaceCode" :screen="screen" :name="record.name" />
        </TabPanel>

        <TabPanel value="files">
          <RecordFiles
            :space-code="spaceCode"
            :screen="screen"
            :name="record.name"
            :can-write="canWrite"
            @count="fileCount = $event"
          />
        </TabPanel>

        <TabPanel value="meta">
          <RecordMeta
            :record="record"
            :space-code="spaceCode"
            :screen="screen"
            :doctype="spec.doctype || ''"
            :label="identity.label"
            :image-field="spec.image_field || ''"
            :image="form[spec.image_field] || ''"
            :assigned="assigned"
            :tags="tags"
            :shares="shares"
            :files="fileCount"
            :can-write="canWrite"
            :can-rename="!!spec.can_rename && canWrite"
            @update:image="form[spec.image_field] = $event"
            @renamed="renamed"
            @assigned="assigned = $event"
            @tagged="tags = $event"
            @shared="shares = $event"
            @files="tab = 'files'"
          />
        </TabPanel>
      </Tabs>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import {
  Alert,
  Badge,
  Button,
  ErrorMessage,
  Tabs,
  TabList,
  TabTrigger,
  TabPanel,
  dayjsLocal,
} from '@/ui'
import AvatarStack from '../fields/AvatarStack.vue'
import RecordChip from './RecordChip.vue'
import RecordForm from './RecordForm.vue'
import RecordActivity from './RecordActivity.vue'
import RecordFiles from './RecordFiles.vue'
import RecordMail from './RecordMail.vue'
import RecordControls from './RecordControls.vue'
import RecordShowcase from './RecordShowcase.vue'
import RelatedRows from './RelatedRows.vue'
import StateBadge from '../fields/StateBadge.vue'
import PrintDialog from './PrintDialog.vue'
import RecordMeta from './RecordMeta.vue'
import { workspace } from '../../../lib/workspace'
import { DRAWER, MERGE_TARGET, PAGE, PANE } from '../../../lib/surfaces'
import { docBadge } from '../../../lib/docstate'
import { tabIcon } from '../../../lib/fields'
import { onDocChange, onDocViewers } from '../../../lib/socket'
import { session } from '../../../lib/session'

const props = defineProps({
  record: { type: Object, required: true },
  spec: { type: Object, required: true },
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  /** Whether the pane is the page. The pane knows; this does not ask. */
  phone: { type: Boolean, default: false },
  /**
   * Which of the three surfaces this is being drawn on — `pane`, `page` or
   * `drawer`. See `lib/surfaces.js`.
   *
   * Passed rather than worked out here: the host owns the decision, because it
   * is the one that knows whether a list is beside this and whether another
   * record is underneath it.
   */
  surface: { type: String, default: PANE },
  /**
   * Bumped by the host when something was added to the showcase's rail, so the
   * rail re-reads itself. Passed through; nothing here reads it.
   */
  revision: { type: Number, default: 0 },
})
const emit = defineEmits([
  'saved', 'close', 'reload', 'renamed', 'open', 'surface', 'expand', 'add',
])

const drawer = computed(() => props.surface === DRAWER)
const wide = computed(() => props.surface === PAGE)

/**
 * Whether the header says who this record is.
 *
 * Once each, never twice. Two things already say it somewhere else:
 *
 *   * the trail above the screen, on any desktop surface that does not cover
 *     it — which is the pane and the page both, and was the bug in the first
 *     version of this: a record filling the window said its own name twice,
 *     six pixels apart, in two sizes;
 *   * the hero, wherever there is a showcase, in 48px an inch below this.
 *
 * What is left is a phone, where the record is a fixed overlay and the trail is
 * behind it, and the drawer, which covers the trail for the same reason. Those
 * two say it here.
 */
const names = computed(() => !showcase.value && (props.phone || drawer.value))

// The reader may choose between the pane and the page, and only between those.
// A phone has room for one surface and a drawer is not a width somebody picks.
const canResize = computed(() => !props.phone && !drawer.value)

/**
 * Whether this record's controls belong on the page header's line rather than
 * in a band of their own.
 *
 * Only the desktop page. It is the one surface where the trail above is both
 * visible and about this record — so a second bar under it is chrome with
 * nothing in it but two icons. The pane sits beside a list whose header is the
 * trail, so its controls are the pane's; the drawer and the phone both cover
 * the trail, so they have to draw one.
 */
const merged = computed(() => wide.value && !props.phone && !drawer.value)

const tab = ref('fields')

/**
 * How this screen says a record should be drawn, where it says anything.
 *
 * Already checked server-side — `showcase.shape` drops what is structurally
 * not one — so this is read, not validated. Null rather than an empty object,
 * because "no showcase" is the answer for nearly every screen and `v-if` on a
 * truthy object is the whole of the branch.
 */
const showcase = computed(() => props.spec?.view_settings?.showcase || null)

// The screens that point back at this record, as tabs. Only where there is a
// showcase: they are part of the same declaration, and a form with four
// related-list tabs bolted onto it is a different page from the one this is.
const related = computed(() => showcase.value?.tabs || [])

// Read the panel's own two lists the first time somebody opens it, and not
// again while they are on the same record — every write from inside it answers
// with the state that followed.
watch(tab, (now) => {
  if (now === 'meta' && !collabLoaded.value) {
    collabLoaded.value = true
    loadCollab()
  }
})
const form = reactive({})
const error = ref('')
const saving = ref(false)
const loadingTimeline = ref(false)
const comments = ref([])
// How many there are, which is not how many are loaded: the timeline is paged
// at fifty, so on a busy record the length of the list stops moving while the
// record keeps gaining comments.
const commentCount = ref(0)
const moreComments = ref(false)
const changes = ref([])
const likes = ref([])
const liked = ref(false)
const tags = ref([])
const shares = ref({})
// Null while nothing has counted them. The Files tab reports what it found, so
// this stays empty until somebody opens it rather than costing a second request
// on every record that is never asked about.
const fileCount = ref(null)
const collabLoaded = ref(false)
const showPrint = ref(false)
const following = ref(false)
const canFollow = ref(false)
// Everybody in the room but this reader — the desk does the same, because a
// face saying "you are here" is a face saying nothing.
const others = ref([])
// The same shape every identity in this product is drawn from, so the faces in
// the room and the faces on the assignment are one component. The room carries
// ids and no more — Frappe's open-doc room is a list of users, not a query —
// so the id is the label too.
const watching = computed(() =>
  others.value.map((who) => ({ value: who, label: who, image: null })),
)

// Who the record is assigned to, as the server resolved it. A ref rather than
// a computed over the record, because the control writes it back: the answer
// after an assignment is what the document ended up holding, and re-reading
// the whole record to learn one list is a round trip for nothing.
const assigned = ref([])
// When somebody else last saved it, or empty. Set from the document's own
// room rather than by polling.
const staleSince = ref('')

const when = (value) => (value ? dayjsLocal(value).fromNow() : '')

// The screen's whole field list, not the columns someone chose to see. Hiding
// a column is a statement about the list; the record still has the field, and
// the server still lets this screen write it. Read here only to seed the form
// — how the fields are laid out is the doctype's business, and RecordForm's.
const fields = computed(() => props.spec?.all_columns || props.spec?.columns || [])
const canWrite = computed(() => !!props.spec?.can_write)

/**
 * One value, flattened to a string that can be compared to another.
 *
 * `!==` is not enough for any of the three shapes a field actually holds. A
 * child table is an array of row objects, so two identical grids are two
 * different arrays and every doctype with a grid read as permanently unsaved.
 * A Currency or Int arrives from the server as a number and comes back out of
 * its control as a string, so `4200 !== '4200'` said the same thing about
 * every numeric field. And empty is spelled three ways — `null` on a record,
 * `undefined` in a form that has not touched the field, `''` in a cleared box.
 *
 * Keys are sorted so that a row rebuilt in another order is still the same
 * row; everything else is compared as the text it would be saved as.
 */
const flat = (value) => {
  if (Array.isArray(value)) return `[${value.map(flat).join(',')}]`
  if (value && typeof value === 'object') {
    return `{${Object.keys(value).sort().map((key) => `${key}:${flat(value[key])}`).join(',')}}`
  }
  return value === null || value === undefined ? '' : String(value)
}

// Whether the form holds something the server has not seen. Read from the
// record rather than tracked with a flag: a flag has to be cleared in every
// path that saves, reloads or switches record, and the one that forgets it
// leaves Submit disabled on a record with nothing wrong with it.
//
// The header turns on it in both directions — Save appears only while it is
// true, the document's own actions only while it is false — because those are
// two answers to one question. Submitting what is on the server while the form
// holds something else is how a document gets submitted that nobody has read;
// offering Save on a record nobody has touched is a button whose only effect is
// to bump `modified`.
const dirty = computed(() =>
  fields.value.some(
    (field) => flat(form[field.fieldname]) !== flat(props.record?.[field.fieldname]),
  ),
)

const identity = computed(() => {
  const field = props.spec?.title_field
  const label = (field && props.record?.[field]) || props.record?.name
  return {
    value: props.record?.name,
    label: String(label || ''),
    id: label === props.record?.name ? '' : props.record?.name,
    image: props.spec?.image_field ? props.record?.[props.spec.image_field] : null,
  }
})

const statusValue = computed(() => {
  const field = props.spec?.status_field
  return (field && props.record?.[field]) || ''
})
// Where the framework stands on it, beside the doctype's own status field and
// de-duped against it. Only the phone draws this pair — on a desktop the trail
// above the list is already saying who this record is, and says it there.
const docState = computed(() =>
  docBadge(props.record?._state, props.spec?.status_field || ''),
)

const loadTimeline = async () => {
  if (!props.record?.name) return
  loadingTimeline.value = true
  try {
    const found = await workspace.timeline(props.spaceCode, props.screen, props.record.name)
    comments.value = found?.comments || []
    commentCount.value = found?.comment_count ?? comments.value.length
    moreComments.value = !!found?.more_comments
    changes.value = found?.changes || []
    likes.value = found?.likes || []
    liked.value = !!found?.liked
    following.value = !!found?.following
    canFollow.value = !!found?.can_follow
  } finally {
    loadingTimeline.value = false
  }
}

/**
 * Tags and shares, on opening the Meta tab rather than on opening the record.
 *
 * Two requests that most records never need: a person reads a record to read
 * it, and paying for who-else-can-see-this on every open is paying for the
 * exception. The panel is the only thing that draws either.
 */
const loadCollab = async () => {
  if (!props.record?.name) return
  const [found, given] = await Promise.all([
    workspace.tags(props.spaceCode, props.screen, props.record.name),
    workspace.shares(props.spaceCode, props.screen, props.record.name),
  ])
  tags.value = found?.tags || []
  shares.value = given || {}
}

const like = async () => {
  const result = await workspace.toggleLike(props.spaceCode, props.screen, props.record.name)
  liked.value = !!result?.liked
  likes.value = result?.likes || []
}

// What the server says afterwards, not what was asked for. A follow that was
// refused — the record moved out of reach between opening it and pressing this
// — would otherwise leave a bell lit over a subscription that does not exist.
const follow = async () => {
  const result = await workspace.toggleFollow(props.spaceCode, props.screen, props.record.name)
  following.value = !!result?.following
}

/**
 * The verbs that are not the framework's, as menu entries.
 *
 * Print, follow, like — three things you do *to* a record rather than to one
 * of its fields, and none of them a thing anybody does twice in a row. They
 * were three buttons in the header, which is where they were competing with
 * the one button that mattered.
 *
 * The like keeps its count, in the label. A number nobody can see is not a
 * number, and the count is the only reason a like is on a record at all.
 */
const extras = computed(() => {
  const found = []
  if (props.spec?.can_print) {
    found.push({ key: 'print', label: 'Print', icon: 'lucide-printer', onClick: () => (showPrint.value = true) })
  }
  if (canFollow.value) {
    found.push({
      key: 'follow',
      label: following.value ? 'Stop following' : 'Follow',
      icon: 'lucide-bell',
      onClick: follow,
    })
  }
  found.push({
    key: 'like',
    label: `${liked.value ? 'Liked' : 'Like'}${likes.value.length ? ` · ${likes.value.length}` : ''}`,
    icon: 'lucide-heart',
    onClick: like,
  })
  return found
})

const save = async () => {
  saving.value = true
  error.value = ''
  try {
    await workspace.saveRecord(props.spaceCode, props.screen, { ...form }, props.record.name)
    emit('saved')
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    saving.value = false
  }
}

// No Escape key. It was the first thing tried, and it is wrong twice over: a
// pane is not modal, so there is nothing for Escape to dismiss, and the
// controls inside it — the link picker above all — do not mark their own
// Escape as handled, so closing a dropdown closed the record under it. The
// way out is the X, the browser's back button, and on a phone the same X at
// the top of the page.
// --- the room ---------------------------------------------------------------
//
// Two rooms per record, both Frappe's: one carries the document's own events,
// the other is the list of who has it open. Re-joined whenever the record
// changes, because a pane that stays mounted while you click down a list would
// otherwise still be reporting the first record's viewers.
let leaveRoom = null

const enterRoom = () => {
  if (leaveRoom) leaveRoom()
  leaveRoom = null
  others.value = []
  staleSince.value = ''

  const doctype = props.spec?.doctype
  const name = props.record?.name
  if (!doctype || !name) return

  const stopViewers = onDocViewers(doctype, name, (users) => {
    // Frappe's rooms carry user ids — an email — which is what `name` is on
    // the session's user rather than the object itself.
    others.value = users.filter((who) => who && who !== session.user?.name)
  })
  const stopChanges = onDocChange(doctype, name, (data) => {
    // Our own save comes back through the same room. `saving` is still true
    // while the round trip finishes, and telling somebody their own change
    // arrived is noise.
    if (saving.value) return
    staleSince.value = data?.modified || new Date().toISOString()
  })
  leaveRoom = () => {
    stopViewers()
    stopChanges()
  }
}

onBeforeUnmount(() => {
  if (leaveRoom) leaveRoom()
})

// Set by the Meta tab just before a rename lands. The watch below resets the
// tab because a *different* record is a different form — but a rename is the
// same record with a new id, and being thrown back to Details for pressing
// Rename is the kind of small rudeness that makes people not press it twice.
const renamedInPlace = ref(false)

const renamed = (name) => {
  renamedInPlace.value = true
  emit('renamed', name)
}

watch(
  () => props.record,
  () => {
    enterRoom()
    if (!renamedInPlace.value) tab.value = 'fields'
    renamedInPlace.value = false
    // A different record's tags and shares are a different record's. Cleared
    // rather than left standing, or the panel shows the last one's for as long
    // as the request takes.
    tags.value = []
    shares.value = {}
    fileCount.value = null
    collabLoaded.value = false
    error.value = ''
    Object.keys(form).forEach((key) => delete form[key])
    for (const field of fields.value) form[field.fieldname] = props.record?.[field.fieldname]
    assigned.value = props.record?._assigned || []
    loadTimeline()
  },
  { immediate: true },
)
</script>
