<template>
  <!--
    A doctype with exactly one document, as a screen.

    Frappe calls it a Single and the list engine has nothing to say about one:
    no list, no record id, no New button. So every screen mechanism here passed
    straight over them and a Single was reachable from the desk and nowhere
    else. `oneapp/onespace/singles.py` has the whole argument.

    Two kinds, and the difference arrives as data rather than as a second
    component: a page that answers with a `verb` is a **tool**, whose document
    is used and dropped, and a page without one is a **settings page**, whose
    only verb is Save.

    The form itself is `RecordForm`, which is the component a record page uses
    — so a Check is the Switch it is everywhere, a Link opens the picker it
    opens everywhere, a Table is the child grid it is everywhere, and the tabs
    are the doctype's own. Nothing here draws a control.
  -->
  <div class="mx-auto flex w-full max-w-4xl flex-col gap-4 p-4">
    <Panel ground="sunken" pad="loose" data-slot="single-band">
      <div class="flex flex-col gap-1">
        <h2 class="text-xl-semibold text-ink-primary">{{ heading }}</h2>
        <p class="text-sm text-ink-secondary">{{ standing }}</p>
      </div>
    </Panel>

    <LoadingText v-if="loading && !loaded" :text="__('Loading')" />

    <template v-if="loaded">
      <Panel pad="loose" data-slot="single-form">
        <RecordForm
          v-model:values="values"
          :spec="formSpec"
          :space-code="spaceCode"
          :screen="screen"
          :disabled="!page.may_write"
        />
      </Panel>

      <div class="flex justify-end">
        <Button
          variant="solid"
          :label="page.verb || __('Save')"
          :loading="working"
          :disabled="!page.may_write"
          :data-slot="page.verb ? 'single-run' : 'single-save'"
          @click="commit"
        />
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

import { Button, LoadingText } from '@/ui'
import Panel from '@/shared/components/Panel.vue'
import RecordForm from '@/modules/onespace/components/screen/record/RecordForm.vue'
import { workspace } from '@/shared/lib/workspace'
import { notifyError, notifySuccess } from '@/shared/lib/runtime/notify'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  spaceCode: { type: String, required: true },
  screen: { type: String, default: '' },
  /** The screen's own declaration, for its label. The fields come from the
   *  server, because they are the doctype's rather than the manifest's. */
  spec: { type: Object, default: () => ({}) },
})

const page = ref({})
const values = ref({})
const loading = ref(false)
const loaded = ref(false)
const working = ref(false)

/** What `RecordForm` is handed. The server sends `columns`, `all_columns` and
 *  `form` under the same names the screen spec uses, so this is the answer
 *  itself rather than a translation of it. */
const formSpec = computed(() => ({
  ...page.value,
  tab_icons: props.spec?.tab_icons || null,
}))

const heading = computed(() => props.spec?.screen_label || props.spec?.label || '')

const standing = computed(() => {
  if (!loaded.value) return ''
  if (!page.value.may_write) {
    return __('These are the rules this workspace runs on. You may read them.')
  }
  return page.value.blurb || __('These are the rules this workspace runs on.')
})

const load = async () => {
  loading.value = true
  try {
    const answer = await workspace.singlePage(props.spaceCode, props.screen)
    page.value = answer || {}
    values.value = { ...(answer?.values || {}) }
    loaded.value = true
  } catch (raised) {
    notifyError(raised)
  } finally {
    loading.value = false
  }
}

/** Save, or run — whichever this page's one button is. */
const commit = async () => {
  working.value = true
  try {
    if (page.value.verb) {
      const answer = await workspace.singleRun(
        props.spaceCode, props.screen, values.value,
      )
      if (answer?.enqueued) {
        notifySuccess(__('That is more than one pass takes, so it is running '
                         + 'in the background.'))
      } else {
        notifySuccess(__('Made {0}.', [String(answer?.count ?? 0)]))
      }
      // Asked again rather than emptied: a tool's document was never stored,
      // so what comes back is the empty form it always was.
      await load()
    } else {
      await workspace.singleSave(props.spaceCode, props.screen, values.value)
      notifySuccess(__('Saved.'))
    }
  } catch (raised) {
    notifyError(raised)
  } finally {
    working.value = false
  }
}

watch(
  () => [props.spaceCode, props.screen],
  () => {
    loaded.value = false
    page.value = {}
    values.value = {}
    load()
  },
  { immediate: true },
)
</script>
