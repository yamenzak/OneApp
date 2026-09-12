<template>
  <!--
    The agreements this workspace runs under, and what this person agreed to.

    Two columns because there are two questions and they are asked at different
    times: what does it say, and did I agree. The list carries the second — a
    tick, a version, and the date — and clicking one answers the first.

    The text is rendered on the server from what every module declares, so a
    document that mentions Cloudflare mentions it because OneStorage said so.
    `docs/LEGAL.md` explains the machinery; this is the reading room.
  -->
  <div class="flex h-full min-h-0 flex-col gap-4">
    <Panel tone="amber" pad="tight" v-if="pending.length">
      <p class="text-p-sm font-medium text-ink-amber-3">
        {{ __('There are agreements you have not accepted yet.') }}
      </p>
      <p class="mt-1 text-p-xs text-ink-secondary">
        {{ __('You will be asked for them the next time the workspace loads.') }}
      </p>
    </Panel>

    <div class="flex min-h-0 flex-1 gap-4">
      <!-- A `div` rather than a `ul`, because each clause is a control: the
           row *is* the button, and `<Row as="li">` with a click would be a
           list item nothing can tab to. -->
      <div class="flex w-64 shrink-0 flex-col gap-1 overflow-y-auto">
        <Row
          v-for="one in rows"
          :key="one.key"
          edge="rounded"
          pad="normal"
          :selected="one.key === showing"
          @click="open(one.key)"
        >
          <span class="flex items-center justify-between gap-2">
            <span class="truncate text-sm font-medium text-ink-primary">{{ one.title }}</span>
            <Badge v-if="one.accepted" theme="green" variant="subtle" :label="__('Agreed')" />
            <Badge v-else-if="one.audience" theme="amber" variant="subtle" :label="__('Not yet')" />
          </span>
          <span class="mt-0.5 block text-p-xs text-ink-muted">
            {{ __('Version {0}', [one.version]) }}
          </span>
        </Row>
      </div>

      <div class="min-w-0 flex-1 overflow-y-auto rounded-6 border border-outline-gray-2 p-5">
        <LoadingText v-if="loading" :text="__('Loading')" />
        <!-- `v-html` because the server assembled it out of declarations we
             wrote and escaped every one of them on the way — `assemble._esc`.
             Nothing a customer typed reaches this. -->
        <article v-else-if="shown" class="prose prose-sm max-w-none" v-html="shown.html" />
        <EmptyState
          v-else
          icon="lucide-scale"
          :title="__('Pick a document')"
          :said="__('Everything this workspace runs under, and what you agreed to.')"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import { Badge, LoadingText } from '@/ui'
import EmptyState from '@/shared/components/EmptyState.vue'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'
import Panel from '@/shared/components/Panel.vue'
import Row from '@/shared/components/Row.vue'

const documents = ref([])
const state = ref({ blocking: [], waiting: [] })
const showing = ref('')
const shown = ref(null)
const loading = ref(false)

const pending = computed(() => [...state.value.blocking, ...state.value.waiting])

// One row per document, with whether this person's part of it is done. A
// document that binds the workspace and not the person shows the workspace's
// answer, because that is the one that matters to whoever is reading.
const rows = computed(() =>
  documents.value.map((one) => ({
    ...one,
    accepted: one.audience
      ? !state.value.blocking.some((row) => row.document === one.key)
      : true,
  })),
)

async function open(key) {
  showing.value = key
  shown.value = null
  loading.value = true
  try {
    shown.value = await workspace.legalDocument(key)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  const [found, standing] = await Promise.all([
    workspace.legalCatalogue().catch(() => ({ documents: [] })),
    workspace.legalOutstanding().catch(() => ({ blocking: [], waiting: [] })),
  ])
  documents.value = found?.documents || []
  state.value = standing || { blocking: [], waiting: [] }
  if (documents.value.length) open(documents.value[0].key)
})
</script>
