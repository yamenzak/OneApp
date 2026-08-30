<template>
  <div class="flex h-full min-h-0 flex-col">
    <!--
      Who this is, and the handful of things you do to a record rather than to
      one of its fields.

      The identity is drawn only where the trail is not already drawing it: on
      a desktop the breadcrumb above the list says which record this is, and
      saying it twice in two different sizes is how a pane starts to read as a
      second page. On a phone the pane *is* the page, so it says it here.
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
      <span v-else class="text-p-sm font-medium text-ink-gray-8">Record</span>

      <div class="ms-auto flex shrink-0 items-center gap-1">
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
      </Tabs>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { Badge, Button, ErrorMessage, Tabs, TabList, TabTrigger, TabPanel } from '@/ui'
import RecordChip from './RecordChip.vue'
import RecordForm from './RecordForm.vue'
import RecordComments from './RecordComments.vue'
import RecordHistory from './RecordHistory.vue'
import { workspace } from '../../lib/workspace'
import { valueTheme } from '../../lib/fields'

const props = defineProps({
  record: { type: Object, required: true },
  spec: { type: Object, required: true },
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  /** Whether the pane is the page. The pane knows; this does not ask. */
  phone: { type: Boolean, default: false },
})
const emit = defineEmits(['saved', 'close'])

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
watch(
  () => props.record,
  () => {
    tab.value = 'fields'
    error.value = ''
    Object.keys(form).forEach((key) => delete form[key])
    for (const field of fields.value) form[field.fieldname] = props.record?.[field.fieldname]
    loadTimeline()
  },
  { immediate: true },
)
</script>
