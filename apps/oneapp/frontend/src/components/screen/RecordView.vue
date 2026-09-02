<template>
  <div class="flex h-full min-h-0 flex-col">
    <!--
      Who this is, and the handful of things you do to a record rather than to
      one of its fields.

      The identity is drawn only where the trail is not already drawing it: on
      a desktop the breadcrumb above the list says which record this is, and
      saying it twice in two different sizes is how a pane starts to read as a
      second page. On a phone the pane *is* the page, so it says it here — and
      on a desktop the row is the controls alone rather than the word "Record",
      which is a label that says nothing and takes a line to say it.
    -->
    <header class="flex shrink-0 items-center gap-2 border-b border-outline-gray-1 px-4 py-3">
      <RecordChip v-if="phone" :record="identity" class="min-w-0 flex-1">
        <template #badge>
          <Badge
            v-if="statusValue"
            data-slot="record-status"
            :label="String(statusValue)"
            :theme="statusTheme"
            variant="subtle"
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

      <div class="flex shrink-0 items-center gap-1" :class="!others.length && 'ms-auto'">
        <!-- What this screen can do to this record beyond editing its fields.
             Declared by the space and resolved server-side, so a screen that
             declares none renders nothing here. -->
        <ScreenActions
          :actions="spec.actions || []"
          scope="record"
          :space-code="spaceCode"
          :screen="screen"
          :names="[record.name]"
          @ran="emit('reload')"
        />
        <!--
          Who this is for. Beside the actions rather than in the form, because
          assignment is not a field: it is not on the doctype, there is no
          column for it, and it is a thing you do to a record.
        -->
        <AssignControl
          :space-code="spaceCode"
          :screen="screen"
          :name="record.name"
          :people="assigned"
          @assigned="assigned = $event"
        />
        <!-- One icon, two themes: lucide ships no filled heart, so the colour
             is what says whether this is yours. -->
        <Button
          icon-left="lucide-heart"
          :label="String(likes.length || 0)"
          :variant="liked ? 'subtle' : 'ghost'"
          :theme="liked ? 'red' : 'gray'"
          @click="like"
        />
        <!--
          Tell me when this changes. Beside the heart because it is the same
          kind of thing — a standing statement about one record, made by one
          person, that no field carries — and the pair reads as "mine" and
          "watch this" rather than as two unrelated controls.

          Drawn only where the doctype tracks its changes: a follow that can
          never report anything is a switch that lies, and the server decides
          that rather than this file guessing from a fieldtype.
        -->
        <!--
          Submit, cancel, amend — or a workflow's own transitions, which is the
          same row of buttons because the server hands back one list either
          way. Absent on a doctype that is neither submittable nor governed by
          a workflow, which is most of them.
        -->
        <DocActions
          v-if="record._state"
          :space-code="spaceCode"
          :screen="screen"
          :name="record.name"
          :state="record._state"
          :status-field="spec.status_field || ''"
          :dirty="dirty"
          @moved="emit('reload')"
          @opened="emit('renamed', $event)"
        />
        <!--
          Print. Beside the bell rather than in a menu: printing a record is
          something people do often enough that hiding it behind three dots is
          hiding it. Only where the doctype allows it — Frappe's own `print`
          permission, which is a permission like any other.
        -->
        <Button
          v-if="spec.can_print"
          data-slot="print"
          icon="lucide-printer"
          variant="ghost"
          label="Print this record"
          tooltip="Print"
          @click="showPrint = true"
        />
        <Button
          v-if="canFollow"
          data-slot="follow"
          icon="lucide-bell"
          :variant="following ? 'subtle' : 'ghost'"
          :theme="following ? 'blue' : 'gray'"
          :label="following ? 'Stop following this record' : 'Follow this record'"
          :tooltip="
            following
              ? 'Following — you are told when this changes'
              : 'Follow, to be told when this changes'
          "
          :loading="followBusy"
          @click="follow"
        />
        <!--
          Save lives up here rather than in a footer, and the reason is the
          corner: the toast that says a save worked is fixed to the bottom
          right of the window, which is exactly where a pane's footer button
          sits — so saving twice in a row meant clicking through the
          confirmation of the first one. frappe-ui's ToastProvider hard-codes
          that position, so the button moved instead.
        -->
        <Button
          v-if="canWrite"
          variant="solid"
          label="Save"
          :loading="saving"
          @click="save"
        />
        <Button
          icon="lucide-x"
          variant="ghost"
          label="Close the record"
          tooltip="Close the record"
          @click="emit('close')"
        />
      </div>
    </header>

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
      <Tabs v-model="tab">
        <TabList>
          <!--
            A glyph on every one of them, from the same derivation the
            doctype's own tabs use — these four are labels like any other, and
            a strip where the doctype's tabs carry icons and ours do not would
            read as two different strips.
          -->
          <TabTrigger value="fields" label="Details" :icon-left="tabIcon('Details')" />
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
          <TabTrigger value="files" label="Files" :icon-left="tabIcon('Files')" />
          <!--
            What the record *is*, as opposed to what it says: its id, its
            picture and its provenance. Last, because it is the tab you go to
            on purpose rather than the one you land on.
          -->
          <TabTrigger value="meta" label="Meta" :icon-left="tabIcon('Meta')" />
        </TabList>

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
  Avatar,
  Badge,
  Button,
  ErrorMessage,
  Tabs,
  TabList,
  TabTrigger,
  TabPanel,
  Tooltip,
  dayjsLocal,
} from '@/ui'
import AssignControl from './AssignControl.vue'
import AvatarStack from './AvatarStack.vue'
import RecordChip from './RecordChip.vue'
import ScreenActions from './ScreenActions.vue'
import RecordForm from './RecordForm.vue'
import RecordActivity from './RecordActivity.vue'
import RecordFiles from './RecordFiles.vue'
import DocActions from './DocActions.vue'
import PrintDialog from './PrintDialog.vue'
import RecordMeta from './RecordMeta.vue'
import { workspace } from '../../lib/workspace'
import { tabIcon, valueTheme } from '../../lib/fields'
import { onDocChange, onDocViewers } from '../../lib/socket'
import { session } from '../../lib/session'

const props = defineProps({
  record: { type: Object, required: true },
  spec: { type: Object, required: true },
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  /** Whether the pane is the page. The pane knows; this does not ask. */
  phone: { type: Boolean, default: false },
})
const emit = defineEmits(['saved', 'close', 'reload', 'renamed'])

const tab = ref('fields')

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
const followBusy = ref(false)
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

// Whether the form holds something the server has not seen. Read from the
// record rather than tracked with a flag: a flag has to be cleared in every
// path that saves, reloads or switches record, and the one that forgets it
// leaves Submit disabled on a record with nothing wrong with it.
//
// It gates the document actions and nothing else. Submitting what is on the
// server while the form holds something else is how a document gets submitted
// that nobody has read.
const dirty = computed(() =>
  fields.value.some(
    (field) => (form[field.fieldname] ?? '') !== (props.record?.[field.fieldname] ?? ''),
  ),
)
const trackChanges = computed(() => !!props.spec?.track_changes)

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
const statusTheme = computed(() => valueTheme(statusValue.value, props.spec?.states || []))

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
  followBusy.value = true
  try {
    const result = await workspace.toggleFollow(
      props.spaceCode,
      props.screen,
      props.record.name,
    )
    following.value = !!result?.following
  } finally {
    followBusy.value = false
  }
}

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
