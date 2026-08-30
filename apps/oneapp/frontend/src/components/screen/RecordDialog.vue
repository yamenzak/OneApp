<template>
  <Dialog v-model="open" :title="title" size="3xl">
    <div class="flex flex-col gap-5">
      <div class="flex items-center justify-between gap-3">
        <div class="flex min-w-0 items-center gap-2">
          <Avatar v-if="image" :image="image" :label="title" shape="square" size="lg" />
          <p v-if="!isNew" class="truncate text-p-xs text-ink-gray-5">{{ record.name }}</p>
        </div>

        <div v-if="!isNew" class="flex shrink-0 items-center gap-1">
          <!-- One icon, two themes: lucide ships no filled heart, so the
               colour is what says whether this is yours. -->
          <Button
            icon-left="lucide-heart"
            :label="String(likes.length || 0)"
            :variant="liked ? 'subtle' : 'ghost'"
            :theme="liked ? 'red' : 'gray'"
            @click="like"
          />
          <Button
            icon-left="lucide-message-square"
            :label="String(commentCount)"
            variant="ghost"
            @click="tab = 'comments'"
          />
        </div>
      </div>

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
          <TabTrigger v-if="!isNew" value="comments">
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
          <TabTrigger v-if="!isNew && trackChanges" value="history">History</TabTrigger>
        </TabList>

        <TabPanel value="fields">
          <div class="flex flex-col gap-4 pt-4">
            <!-- The doctype's own tabs and sections, over the fields this
                 person may write. See RecordForm. -->
            <RecordForm
              v-model:values="form"
              :spec="spec"
              :space-code="spaceCode"
              :screen="screen"
              :disabled="!canWrite"
              :is-new="isNew"
            />
            <ErrorMessage v-if="error" :message="error" />
          </div>
        </TabPanel>

        <TabPanel value="comments">
          <div class="flex flex-col gap-4 pt-4">
            <div class="flex items-start gap-2">
              <Textarea v-model="draft" :rows="2" placeholder="Add a comment" class="flex-1" />
              <Button
                label="Comment"
                :disabled="!draft.trim()"
                :loading="commenting"
                @click="addComment"
              />
            </div>

            <LoadingText v-if="loadingTimeline" text="Loading comments" />

            <EmptyState
              v-else-if="!comments.length"
              class="!py-8"
              icon="lucide-message-square"
              title="No comments"
              description="Nothing has been said about this one yet."
            />

            <!-- The page is capped, and a list that silently stops at fifty
                 reads as "that is all of them". -->
            <p v-if="moreComments" class="text-p-xs text-ink-gray-5">
              Showing the {{ comments.length }} most recent of {{ commentCount }}.
            </p>

            <div v-for="entry in comments" :key="entry.name" class="flex gap-3">
              <Avatar :label="entry.comment_by || entry.comment_email" size="sm" />
              <div class="min-w-0 flex-1">
                <div class="flex items-baseline gap-2">
                  <span class="truncate text-p-sm font-medium text-ink-gray-8">
                    {{ entry.comment_by || entry.comment_email }}
                  </span>
                  <span class="shrink-0 text-p-xs text-ink-gray-5">{{ when(entry.creation) }}</span>
                </div>
                <p class="whitespace-pre-wrap text-p-sm text-ink-gray-7">{{ entry.content }}</p>
              </div>
            </div>
          </div>
        </TabPanel>

        <TabPanel value="history">
          <div class="flex flex-col gap-3 pt-4">
            <LoadingText v-if="loadingTimeline" text="Loading history" />

            <EmptyState
              v-else-if="!changes.length"
              class="!py-8"
              icon="lucide-history"
              title="No changes recorded"
              description="Nothing on this screen has changed since it was created."
            />

            <!--
              In the screen's own words. Frappe stores a version as raw field
              names, and "grand_total: 120 → 140" for a field the customer's
              screen calls "Total" reads as though it belongs to something else.
            -->
            <div v-for="entry in changes" :key="entry.name" class="flex gap-3">
              <Avatar :label="entry.by" size="sm" />
              <div class="min-w-0 flex-1">
                <div class="flex items-baseline gap-2">
                  <span class="truncate text-p-sm font-medium text-ink-gray-8">{{ entry.by }}</span>
                  <span class="shrink-0 text-p-xs text-ink-gray-5">{{ when(entry.on) }}</span>
                </div>
                <p v-for="(change, i) in entry.entries" :key="i" class="text-p-sm text-ink-gray-6">
                  <span class="text-ink-gray-8">{{ change.label }}</span>
                  <span class="text-ink-gray-4"> {{ change.from || '—' }} → </span>
                  <span class="text-ink-gray-8">{{ change.to || '—' }}</span>
                </p>
              </div>
            </div>
          </div>
        </TabPanel>
      </Tabs>
    </div>

    <template v-if="canWrite" #actions>
      <Button variant="solid" label="Save" :loading="saving" @click="save" />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import {
  Dialog,
  Badge,
  Button,
  Avatar,
  Textarea,
  ErrorMessage,
  LoadingText,
  Tabs,
  TabList,
  TabTrigger,
  TabPanel,
  dayjsLocal,
} from '@/ui'
import EmptyState from '../EmptyState.vue'
import RecordForm from './RecordForm.vue'
import { workspace } from '../../lib/workspace'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  record: { type: Object, default: () => ({}) },
  spec: { type: Object, required: true },
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const open = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const tab = ref('fields')
const form = reactive({})
const error = ref('')
const saving = ref(false)
const draft = ref('')
const commenting = ref(false)
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

const isNew = computed(() => !!props.record?.__new)
// The screen's whole field list, not the columns someone chose to see. Hiding
// a column is a statement about the list; the record still has the field, and
// the server still lets this screen write it. Read here only to seed the form
// — how the fields are laid out is the doctype's business, and RecordForm's.
const fields = computed(() => props.spec?.all_columns || props.spec?.columns || [])
const canWrite = computed(() => !!props.spec?.can_write)

const trackChanges = computed(() => !!props.spec?.track_changes)
const image = computed(() =>
  props.spec?.image_field ? props.record?.[props.spec.image_field] : null,
)

const title = computed(() => {
  if (isNew.value) return `New ${props.spec?.screen_label || 'record'}`
  const field = props.spec?.title_field
  return (field && props.record?.[field]) || props.record?.name || 'Record'
})

const when = (value) => (value ? dayjsLocal(value).fromNow() : '')

const loadTimeline = async () => {
  if (isNew.value || !props.record?.name) {
    comments.value = []
    commentCount.value = 0
    changes.value = []
    return
  }
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

const addComment = async () => {
  commenting.value = true
  try {
    await workspace.comment(props.spaceCode, props.screen, props.record.name, draft.value)
    draft.value = ''
    await loadTimeline()
  } finally {
    commenting.value = false
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
    await workspace.saveRecord(
      props.spaceCode,
      props.screen,
      { ...form },
      isNew.value ? null : props.record.name,
    )
    emit('saved')
    open.value = false
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    saving.value = false
  }
}

watch(
  () => [props.modelValue, props.record],
  ([showing]) => {
    if (!showing) return
    tab.value = 'fields'
    error.value = ''
    Object.keys(form).forEach((key) => delete form[key])
    for (const field of fields.value) form[field.fieldname] = props.record?.[field.fieldname]
    loadTimeline()
  },
  { immediate: true },
)
</script>
