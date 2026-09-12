<template>
  <!--
    A file somebody was sent, open in the editor it belongs in.

    Not the workspace. There is no rail, no sidebar, no settings, no assistant
    and no notification feed, because every one of those is a window onto a
    workspace this reader has no account in — `App.vue` draws this route
    outside the shell for exactly that reason. What is here is the file, a
    line saying where it came from and when the link stops working, and
    nothing else.
  -->
  <div class="flex h-full min-h-0 flex-col bg-surface-base">
    <div
      v-if="link"
      class="flex shrink-0 items-center gap-3 border-b border-outline-gray-1 px-4 py-2.5"
      data-slot="link-bar"
    >
      <!-- Where this came from and what it allows. The file's own name is not
           here: the editor below draws a header with the name in it, and two
           bars saying the same word is one bar too many. The one case with no
           editor — a drawing, a PDF — names it in the body instead. -->
      <p class="min-w-0 truncate text-sm text-ink-secondary">
        {{ __('Shared with you') }}
      </p>
      <Badge :theme="link.level === 'write' ? 'green' : 'gray'" variant="subtle">
        {{ link.level === 'write' ? __('You can edit this') : __('Read only') }}
      </Badge>
      <span v-if="until" class="ms-auto shrink-0 text-p-xs text-ink-muted">
        {{ __('This link stops working {0}', [until]) }}
      </span>
    </div>

    <div v-if="loading" class="grid flex-1 place-items-center">
      <LoadingIndicator class="size-5 text-ink-muted" />
    </div>

    <!--
      Gone, expired, revoked, or never real. One sentence for all four, and
      the same one the server gives: a refusal that explains itself tells
      somebody holding a nearly-right secret that it was nearly right.
    -->
    <div v-else-if="!link" class="grid flex-1 place-items-center p-6">
      <div class="max-w-sm text-center">
        <p class="text-base-medium text-ink-primary">{{ __('This link is not available') }}</p>
        <p class="mt-1.5 text-p-base text-ink-secondary">
          {{ __('It may have expired, or been taken back. Ask whoever sent it for a new one.') }}
        </p>
      </div>
    </div>

    <!-- Something neither editor draws — a drawing, a photograph, a PDF. The
         read-only link already knew how to hand those over, so this hands
         over to it rather than inventing a second answer. -->
    <div v-else-if="!link.editable" class="grid flex-1 place-items-center p-6">
      <div class="max-w-sm text-center">
        <p class="text-base-medium text-ink-primary">{{ link.title }}</p>
        <p class="mt-1.5 text-p-base text-ink-secondary">
          {{ __('This one opens outside the browser.') }}
        </p>
        <Button
          class="mt-4"
          variant="solid"
          icon-left="lucide-download"
          :label="__('Download it')"
          @click="download"
        />
      </div>
    </div>

    <SheetEditor
      v-else-if="link.kind === SHEET"
      :id="link.name"
      :host-menu="[]"
      class="min-h-0 flex-1"
    />

    <DocEditor
      v-else-if="doc"
      :name="link.name"
      :doc="doc"
      class="min-h-0 flex-1"
    />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

import { Badge, Button, LoadingIndicator } from '@/ui'
import SheetEditor from '@/modules/onesheet/components/editor/index.vue'
import DocEditor from '@/modules/onedoc/components/DocEditor.vue'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'
import { ago } from '@/shared/lib/runtime/format'

// The two kinds an editor can draw. From `onestorage/kinds.py`, which is
// where the strings are decided.
const SHEET = 'Sheet'

const props = defineProps({
  secret: { type: String, required: true },
})

const link = ref(null)
const doc = ref(null)
const loading = ref(true)

const until = computed(() =>
  link.value?.expires_on ? ago(link.value.expires_on) : '',
)

function download() {
  window.location.href = `/api/method/oneapp.onestorage.open_link?secret=${encodeURIComponent(props.secret)}`
}

async function follow() {
  try {
    const found = await workspace.linkFollow(props.secret)
    link.value = found
    // A document's editor takes its whole payload as a prop, the way
    // `Doc.vue` hands it one. `docOpen` reads the link's endpoint when the
    // address bar has a secret in it, so this is the same call the
    // signed-in page makes.
    if (found?.editable && found.kind !== SHEET) {
      doc.value = await workspace.docOpen(found.name)
    }
  } catch {
    link.value = null
  } finally {
    loading.value = false
  }
}

follow()
</script>
