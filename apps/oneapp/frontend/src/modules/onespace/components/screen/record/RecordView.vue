<template>
  <div class="flex h-full min-h-0 flex-col">
    <!--
      Who this is, and what you can do to it.

      On a desktop page the trail above already names the record, so the
      controls go onto its line and this band does not render. A pane keeps its
      own; a drawer and a phone keep theirs because both cover the trail.
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
      <!-- Who else has this open: Frappe's own open-doc room, which the
           server only admits a reader who may see the document to. -->
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
      rendered by the host in the same pass as this.
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

    <!-- Somebody else saved it while this was open. Said rather than done:
         the reader may be halfway through typing. -->
    <PrintDialog
      v-model="showPrint"
      :space-code="spaceCode"
      :screen="screen"
      :name="record.name"
    />

    <!-- A copy, as a draft: Frappe's Duplicate opens an unsaved form rather
         than inserting a second document. -->
    <!--
      Mounted rather than `v-if`-ed into existence. The dialog fills its form
      from `preset` in a watcher on *opening*, and a component that appears
      already open never sees that transition.
    -->
    <CreateDialog
      v-if="spec?.can_create"
      v-model="copying"
      :spec="spec"
      :space-code="spaceCode"
      :screen="screen"
      :preset="copy"
      @created="emit('open', { screen, name: $event })"
    />

    <Alert
      v-if="staleSince"
      class="mx-4 mt-3"
      theme="amber"
      :title="__('Someone else changed this')"
    >
      <template #description>
        {{ __('It was saved {0}. Reloading takes what is on the server; anything typed here and not saved goes with it.', [when(staleSince)]) }}
      </template>
      <template #actions>
        <Button :label="__('Reload it')" @click="emit('reload')" />
      </template>
    </Alert>

    <div class="min-h-0 flex-1 overflow-y-auto px-4 py-4">
      <!--
        The top of the record: a photograph, the name over it, the two or three
        numbers worth reading. Declared rather than coded —
        `view_settings.showcase` in the manifest is the whole of it.
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
          The strip stays put on a showcase screen: the hero is most of a
          screenful, and this is the one control that must not scroll away.
          A wrapper rather than a class on `TabList`, whose own root is
          `relative`.
        -->
        <!-- And it scrolls sideways rather than squeezing: eight tabs in a
             drawer put the last two off the edge with nothing to say so. -->
        <div
          class="-mx-4 overflow-x-auto px-4"
          :class="showcase ? 'sticky top-0 z-10 bg-surface-base' : ''"
        >
          <TabList>
            <!-- A glyph on every one, from the derivation the doctype's own
                 tabs use, or the strip reads as two strips. -->
            <TabTrigger value="fields" :label="__('Details')" :icon-left="tabIcon('Details')" />
            <!--
              The other screens in this space that point back at this record.
              Second, not last: on a screen that declares them these are what
              the record is *for*.
            -->
            <TabTrigger
              v-for="one in related"
              :key="one.screen"
              :value="`related:${one.screen}`"
              :label="one.label || one.screen"
              :icon-left="one.icon || tabIcon(one.label || '')"
            />
            <!-- The count as a badge rather than inside the word. `#suffix`
                 is the slot for it; the default slot replaces the label. -->
            <!-- One tab, not two: answering "what happened on Tuesday" from
                 separate places meant merging them by eye. -->
            <TabTrigger value="activity" :label="__('Activity')" :icon-left="tabIcon('Activity')">
              <template #suffix>
                <Badge
                  v-if="commentCount"
                  :label="String(commentCount)"
                  theme="gray"
                  variant="subtle"
                />
              </template>
            </TabTrigger>
            <!-- The mail about this record. Beside Activity rather than in
                 it: a message is something said from outside. -->
            <TabTrigger value="mail" :label="__('Mail')" :icon-left="tabIcon('Mail')" />
            <TabTrigger value="files" :label="__('Files')" :icon-left="tabIcon('Files')" />
            <!-- What the record *is* rather than what it says. Last, because
                 it is the tab you go to on purpose. -->
            <TabTrigger value="meta" :label="__('Meta')" :icon-left="tabIcon('Meta')" />
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
              :docname="record?.name || ''"
              :ai="record?._ai || {}"
              @reload="emit('reload')"
            />
            <ErrorMessage v-if="error" :message="error" />
          </div>
        </TabPanel>

        <!-- One per declared tab. A `TabPanel` mounts when it is chosen, so
             six related screens cost six requests only if all six are opened. -->
        <TabPanel
          v-for="one in related"
          :key="one.screen"
          :value="`related:${one.screen}`"
        >
          <RelatedRows
            :space-code="spaceCode"
            :screen="one.screen"
            :field="one.field"
            :where="one.where || []"
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
import { computed, onBeforeUnmount, provide, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
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
import AvatarStack from '@/modules/onespace/components/screen/fields/AvatarStack.vue'
import RecordChip from '@/modules/onespace/components/screen/record/RecordChip.vue'
import RecordForm from '@/modules/onespace/components/screen/record/RecordForm.vue'
import RecordActivity from '@/modules/onespace/components/screen/record/RecordActivity.vue'
import RecordFiles from '@/modules/onespace/components/screen/record/RecordFiles.vue'
import RecordMail from '@/modules/onespace/components/screen/record/RecordMail.vue'
import RecordControls from '@/modules/onespace/components/screen/record/RecordControls.vue'
import RecordShowcase from '@/modules/onespace/components/screen/record/RecordShowcase.vue'
import RelatedRows from '@/modules/onespace/components/screen/record/RelatedRows.vue'
import StateBadge from '@/modules/onespace/components/screen/fields/StateBadge.vue'
import PrintDialog from '@/modules/onespace/components/screen/record/PrintDialog.vue'
import CreateDialog from '@/modules/onespace/components/screen/record/CreateDialog.vue'
import RecordMeta from '@/modules/onespace/components/screen/record/RecordMeta.vue'
import { workspace } from '@/shared/lib/workspace'
import { notifyError, notifySuccess } from '@/shared/lib/runtime/notify'
import { DRAWER, MERGE_TARGET, PAGE, PANE } from '@/modules/onespace/lib/screen/surfaces'
import { RETURN_TO } from '@/modules/onespace/lib/screen/returnTo'
import { docBadge } from '@/modules/onespace/lib/screen/docstate'
import { tabIcon } from '@/modules/onespace/lib/screen/fields'
import { onDocChange, onDocViewers } from '@/shared/lib/runtime/socket'
import { session } from '@/modules/onespace/lib/shell/session'
import { __ } from '@/shared/lib/runtime/translate'
import { errorText } from '@/shared/lib/runtime/errors'

const props = defineProps({
  record: { type: Object, required: true },
  spec: { type: Object, required: true },
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  /** Whether the pane is the page. The pane knows; this does not ask. */
  phone: { type: Boolean, default: false },
  /**
   * Which of the three surfaces this is drawn on — see `lib/screen/surfaces.js`.
   * Passed rather than worked out here: the host knows whether a list is beside
   * this and whether another record is underneath it.
   */
  surface: { type: String, default: PANE },
  /** Bumped by the host when the showcase's rail gained something. Passed
   *  through; nothing here reads it. */
  revision: { type: Number, default: 0 },
})
const route = useRoute()

const emit = defineEmits([
  'saved', 'close', 'reload', 'renamed', 'open', 'surface', 'expand', 'add',
])

const drawer = computed(() => props.surface === DRAWER)
const wide = computed(() => props.surface === PAGE)

/**
 * Whether the header says who this record is. Once each, never twice.
 *
 * The trail says it on any desktop surface that does not cover it, and the hero
 * says it wherever there is a showcase. What is left is the phone and the
 * drawer, which cover the trail.
 */
const names = computed(() => !showcase.value && (props.phone || drawer.value))

// The reader may choose between the pane and the page, and only between those.
// A phone has room for one surface and a drawer is not a width somebody picks.
const canResize = computed(() => !props.phone && !drawer.value)

/**
 * Whether this record's controls belong up on the bar rather than inside the
 * panel.
 *
 * Both desktop surfaces now. As a page the trail above is about this record;
 * as a pane the bar carries a second trail exactly the width of the pane, and
 * these are what sits at the end of it. Left inside the panel only where there
 * is no trail of its own to join: a phone, and a drawer over another record.
 */
const merged = computed(() => !props.phone && !drawer.value)

const tab = ref('fields')

/**
 * How this screen says a record should be drawn, where it says anything.
 * Already checked server-side by `showcase.shape`, so this is read, not
 * validated.
 */
const showcase = computed(() => props.spec?.view_settings?.showcase || null)

/**
 * The screens that point back at this record, as tabs.
 *
 * A showcase's own declared four first, because somebody chose them; then
 * everything derived — every other screen in this space whose doctype links to
 * this one. See `spaceview/connections.py`.
 */
const related = computed(() => [
  ...(showcase.value?.tabs || []),
  ...(props.spec?.connections || []),
])

// Read the panel's own two lists once per record: every write from inside it
// answers with the state that followed.
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
// at fifty.
const commentCount = ref(0)
const moreComments = ref(false)
const changes = ref([])
const likes = ref([])
const liked = ref(false)
const tags = ref([])
const shares = ref({})
// Null while nothing has counted them. The Files tab reports what it found, so
// this costs nothing on a record nobody asks about.
const fileCount = ref(null)
const collabLoaded = ref(false)
const showPrint = ref(false)
const following = ref(false)
const canFollow = ref(false)
// Everybody in the room but this reader: a face saying "you are here" says
// nothing.
const others = ref([])
// The room carries ids and no more — Frappe's open-doc room is a list of users
// — so the id is the label too.
const watching = computed(() =>
  others.value.map((who) => ({ value: who, label: who, image: null })),
)

// Who the record is assigned to, as the server resolved it. A ref rather than a
// computed, because the control writes it back.
const assigned = ref([])
// When somebody else last saved it, from the document's own room.
const staleSince = ref('')

const when = (value) => (value ? dayjsLocal(value).fromNow() : '')

// The screen's whole field list, not the columns someone chose to see: hiding a
// column is a statement about the list. Read here only to seed the form.
const fields = computed(() => props.spec?.all_columns || props.spec?.columns || [])
const canWrite = computed(() => !!props.spec?.can_write)

/**
 * One value, flattened to a string that can be compared to another.
 *
 * `!==` is wrong for all three shapes a field holds: a child table is a fresh
 * array every render, a Currency arrives as a number and comes back as a
 * string, and empty is spelled `null`, `undefined` and `''`. Keys are sorted so
 * a row rebuilt in another order is still the same row.
 */
const flat = (value) => {
  if (Array.isArray(value)) return `[${value.map(flat).join(',')}]`
  if (value && typeof value === 'object') {
    return `{${Object.keys(value).sort().map((key) => `${key}:${flat(value[key])}`).join(',')}}`
  }
  return value === null || value === undefined ? '' : String(value)
}

// Whether the form holds something the server has not seen. Read from the
// record rather than tracked with a flag, which has to be cleared in every path
// that saves, reloads or switches record.
//
// The header turns on it both ways — Save only while it is true, the document's
// own actions only while it is false.
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

// The way back, for the editors this record can open. A sheet or a document
// opened from here is still a page — see `lib/screen/returnTo.js` — but it
// carries the record's name and address so closing it comes back.
provide(RETURN_TO, computed(() => ({
  label: identity.value.label || identity.value.value || '',
  path: route.fullPath,
})))

const statusValue = computed(() => {
  const field = props.spec?.status_field
  return (field && props.record?.[field]) || ''
})
// Where the framework stands, beside the doctype's own status field and de-duped
// against it. Only the phone draws the pair; a desktop trail already says it.
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
 * Tags and shares, on opening the Meta tab rather than on opening the record:
 * two requests most records never need.
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

// What the server says afterwards, not what was asked for: a refused follow
// would otherwise light a bell over a subscription that does not exist.
const follow = async () => {
  const result = await workspace.toggleFollow(props.spaceCode, props.screen, props.record.name)
  following.value = !!result?.following
}

/**
 * The verbs that are not the framework's, as menu entries — print, follow, like.
 * As buttons in the header they competed with the one button that mattered.
 *
 * The like keeps its count in the label: a number nobody can see is not one.
 */
/**
 * A copy of this record, as values, and the dialog holding them. Fetched on the
 * click: `copy_doc` on a forty-line invoice is not a cost to pay on every read.
 */
const copying = ref(false)
const copy = ref({})

const startCopy = async () => {
  try {
    copy.value = (await workspace.duplicateRecord(props.spaceCode, props.screen, props.record.name)) || {}
  } catch {
    copy.value = {}
  }
  copying.value = true
}

/**
 * The address of what is on screen, for somebody to paste into a message.
 *
 * `clipboard` is unavailable over plain HTTP and in some private modes, and
 * there is no useful fallback — so it says it could not rather than pretending.
 */
const copyLink = async () => {
  try {
    await navigator.clipboard.writeText(window.location.href)
    notifySuccess(__('Link copied'))
  } catch {
    notifyError(__('This browser would not let the page copy to the clipboard.'))
  }
}

const extras = computed(() => {
  const found = []
  if (props.spec?.can_print) {
    found.push({
      key: 'print',
      label: __('Print'),
      icon: 'lucide-printer',
      onClick: () => (showPrint.value = true),
    })
  }
  if (canFollow.value) {
    found.push({
      key: 'follow',
      label: following.value ? __('Stop following') : __('Follow'),
      icon: 'lucide-bell',
      onClick: follow,
    })
  }
  // The word, and how many, which is a count beside it rather than part of
  // the sentence.
  const likeWord = liked.value ? __('Liked') : __('Like')
  found.push({
    key: 'like',
    label: likes.value.length ? `${likeWord} · ${likes.value.length}` : likeWord,
    icon: 'lucide-heart',
    onClick: like,
  })
  // The three the desk has had forever. Last, because they are the ones
  // somebody goes looking for.
  if (props.spec?.can_create) {
    found.push({
      key: 'duplicate',
      label: __('Duplicate'),
      icon: 'lucide-copy-plus',
      onClick: startCopy,
    })
  }
  found.push({
    key: 'link',
    label: __('Copy link'),
    icon: 'lucide-link',
    onClick: copyLink,
  })
  found.push({
    key: 'reload',
    label: __('Reload'),
    icon: 'lucide-refresh-cw',
    onClick: () => emit('reload'),
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
    error.value = errorText(e)
  } finally {
    saving.value = false
  }
}

// No Escape key. A pane is not modal, and the controls inside it — the link
// picker above all — do not mark their own Escape as handled, so closing a
// dropdown closed the record under it. The way out is the X.

// --- the room ---------------------------------------------------------------
//
// Two rooms per record, both Frappe's: the document's own events, and who has
// it open. Re-joined whenever the record changes.
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
    // Frappe's rooms carry user ids — an email — which is `name` on the
    // session's user rather than the object itself.
    others.value = users.filter((who) => who && who !== session.user?.name)
  })
  const stopChanges = onDocChange(doctype, name, (data) => {
    // Our own save comes back through the same room, and telling somebody their
    // own change arrived is noise.
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

// Set by the Meta tab just before a rename lands: a rename is the same record
// with a new id, and being thrown back to Details for it is a small rudeness.
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
    // Cleared rather than left standing, or the panel shows the last record's
    // for as long as the request takes.
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
