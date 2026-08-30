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
      <div v-if="others.length" class="ms-auto flex shrink-0 items-center -space-x-1.5">
        <!-- The gap between overlapping faces is drawn as a ring of the
             surface behind them. A `ring-*` colour is not one of the theme's
             tokens — they are background, text and outline — so it is a
             padded background rather than a ring. -->
        <Tooltip v-for="who in others" :key="who" :text="`${who} is looking at this too`">
          <span data-slot="viewer" class="inline-flex rounded-full bg-surface-base p-0.5">
            <Avatar :label="who" size="sm" />
          </span>
        </Tooltip>
      </div>

      <div class="flex shrink-0 items-center gap-1" :class="!others.length && 'ms-auto'">
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
          <TabTrigger value="fields">Details</TabTrigger>
          <!--
            The count as a badge rather than inside the word: "Comments (3)"
            reads as a label, a badge reads as a number.

            One interpolation for the text, because Vue condenses the newline
            before it into a leading space and a tab whose label starts with a
            space is a label nothing can match on.
          -->
          <TabTrigger value="comments">
            <span class="flex items-center gap-1.5"
              >{{ 'Comments'
              }}<Badge
                v-if="commentCount"
                :label="String(commentCount)"
                theme="gray"
                variant="subtle"
              />
            </span>
          </TabTrigger>
          <TabTrigger v-if="trackChanges" value="history">History</TabTrigger>
          <TabTrigger value="files">Files</TabTrigger>
        </TabList>

        <TabPanel value="fields">
          <div class="flex flex-col gap-4 pt-4">
            <!-- The record's own picture, where the doctype declares one.
                 Replaced in place, because an Attach Image field otherwise
                 renders as a file box halfway down the form. -->
            <RecordImage
              v-if="spec.image_field"
              :value="form[spec.image_field] || ''"
              :label="identity.label"
              :field="spec.image_field"
              :doctype="spec.doctype"
              :name="record.name"
              :can-write="canWrite"
              @update:value="form[spec.image_field] = $event"
            />
            <RecordForm
              v-model:values="form"
              :spec="spec"
              :space-code="spaceCode"
              :screen="screen"
              :disabled="!canWrite"
            />
            <ErrorMessage v-if="error" :message="error" />
            <RecordMeta :record="record" />
          </div>
        </TabPanel>

        <TabPanel value="comments">
          <RecordComments
            :space-code="spaceCode"
            :screen="screen"
            :name="record.name"
            :comments="comments"
            :count="commentCount"
            :more="moreComments"
            :loading="loadingTimeline"
            @added="loadTimeline"
          />
        </TabPanel>

        <TabPanel value="history">
          <RecordHistory :changes="changes" :loading="loadingTimeline" />
        </TabPanel>

        <TabPanel value="files">
          <RecordFiles
            :space-code="spaceCode"
            :screen="screen"
            :name="record.name"
            :can-write="canWrite"
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
import RecordChip from './RecordChip.vue'
import RecordForm from './RecordForm.vue'
import RecordComments from './RecordComments.vue'
import RecordHistory from './RecordHistory.vue'
import RecordFiles from './RecordFiles.vue'
import RecordImage from './RecordImage.vue'
import RecordMeta from './RecordMeta.vue'
import { workspace } from '../../lib/workspace'
import { valueTheme } from '../../lib/fields'
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
const emit = defineEmits(['saved', 'close', 'reload'])

const tab = ref('fields')
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
// Everybody in the room but this reader — the desk does the same, because a
// face saying "you are here" is a face saying nothing.
const others = ref([])
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
  } finally {
    loadingTimeline.value = false
  }
}

const like = async () => {
  const result = await workspace.toggleLike(props.spaceCode, props.screen, props.record.name)
  liked.value = !!result?.liked
  likes.value = result?.likes || []
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

watch(
  () => props.record,
  () => {
    enterRoom()
    tab.value = 'fields'
    error.value = ''
    Object.keys(form).forEach((key) => delete form[key])
    for (const field of fields.value) form[field.fieldname] = props.record?.[field.fieldname]
    loadTimeline()
  },
  { immediate: true },
)
</script>
