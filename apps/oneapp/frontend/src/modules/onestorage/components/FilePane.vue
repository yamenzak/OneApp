<!--
  A file you are looking at, beside the list you found it in.

  The placement rule, applied — `docs/UNIFICATION.md` §C2. The same file used
  to open three ways: a resizable pane in the Drive, a modal dialog from a
  record's Files tab, and a modal dialog from a mail attachment. `FileSurface`
  is chrome-free precisely so that "whatever holds it owns the title and the
  actions", and three holders had been written for what is one question — is
  this the subject of the list I am in? — with one answer.

  So: one pane, three callers. Looking at a photograph is how you decide which
  photograph, and a modal makes that open-look-close-open rather than a walk
  down the list.

  What is different per caller is passed in rather than branched on here: the
  Drive puts an editor in the body and a Copy button in the actions, a mail
  attachment and a record's file take the defaults.
-->
<template>
  <ObjectPane v-if="open && file" :max-share="maxShare" :min="min">
    <template #body>
      <div class="flex h-full min-h-0 flex-col overflow-hidden rounded-6 bg-surface-base">
        <!--
          Always, and thin over an editor.

          It was hidden over an editor once, on the grounds that both editors
          bring an identity bar of their own. One of them does: a sheet's bar
          is inside this pane. A document's is *teleported to the shell's
          header* — not in the pane at all — so over a document the pane had no
          chrome whatsoever and no way out of it but the browser's back button,
          which is not a control and did not close the pane either.

          What is left is the name and the way out, which is the one thing
          neither editor can provide: only the host knows this is a pane rather
          than a page.
        -->
        <header class="flex shrink-0 items-center gap-2 border-b border-outline-gray-1 p-3">
          <h2 class="flex min-w-0 flex-1 items-center gap-1.5">
            <span class="truncate text-base text-ink-primary">{{ name }}</span>
            <!-- A file a model drew carries the same mark here as in the list.
                 This was the one surface `FileFace` did not reach, because the
                 dialog took its title as a string and the mark had nowhere to
                 go. -->
            <AiMark v-if="file._ai" :mark="file._ai" />
          </h2>

          <slot name="actions" />

          <!--
            A link, not `FileShare`. Two different things wear the word share:
            `FileShare` is a `DocShare` row and needs the other person to have
            a login here, and this is the one for the consultant who does not.
            The row's menu offers the first; a file you are looking at is
            usually a file you are about to send somebody.
          -->
          <Button
            v-if="shareable"
            icon="lucide-link"
            variant="ghost"
            :label="__('Share a link')"
            :tooltip="__('Share a link')"
            @click="sharing = true"
          />
          <Button
            v-if="downloadable"
            icon="lucide-download"
            variant="ghost"
            :label="__('Download')"
            :tooltip="__('Download')"
            @click="download"
          />
          <Button
            icon="lucide-x"
            variant="ghost"
            :label="__('Close')"
            :tooltip="__('Close')"
            data-slot="file-pane-close"
            @click="open = false"
          />
        </header>

        <!-- The body is the caller's where it has one — an editor — and the
             plain surface where it does not. -->
        <slot>
          <div class="min-h-0 flex-1 overflow-auto p-3">
            <FileSurface :file="file" :live="open" :tall="false" />
          </div>
        </slot>
      </div>
    </template>
  </ObjectPane>

  <ShareLink v-model="sharing" :file="file" />
</template>

<script setup>
import { computed, ref } from 'vue'

import { Button } from '@/ui'
import AiMark from '@/modules/onespace/components/AiMark.vue'
import ObjectPane from '@/shared/components/ObjectPane.vue'
import FileSurface from '@/modules/onestorage/components/FileSurface.vue'
import ShareLink from '@/modules/onestorage/components/ShareLink.vue'
import { downloadUrl } from '@/modules/onestorage/lib/files'
import { __ } from '@/shared/lib/runtime/translate'

const open = defineModel({ type: Boolean, default: false })

const props = defineProps({
  /** The row, as any file list has it. */
  file: { type: Object, default: null },
  /** How much of the window this may take. An editor wants more than a photo. */
  maxShare: { type: Number, default: 0.45 },
  /** The narrowest it opens at, where the body needs a floor. */
  min: { type: Number, default: undefined },
  /** Offer a link a stranger can follow. A remote file has no row to link to. */
  shareable: { type: Boolean, default: true },
  /** Offer the file itself. An editor saves rather than downloads. */
  downloadable: { type: Boolean, default: true },
})

const sharing = ref(false)

const name = computed(() => props.file?.file_name || __('File'))

const download = () => window.open(downloadUrl(props.file.name), '_blank')
</script>
