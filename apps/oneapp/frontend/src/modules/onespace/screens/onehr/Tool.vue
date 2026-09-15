<template>
  <!--
    A Single with a door on it.

    Five screens share this page and they are two kinds. A **settings page** is
    HRMS's own form over a doctype with one document — the rules about leave,
    the rules about pay — and its only verb is Save. A **bulk tool** is the same
    form used as a question: describe the people, see who that is, tick the ones
    you mean, and do it to them.

    They are one component because HRMS made them one shape, and the difference
    arrives as data: a page that answers with a `verb` is a tool.
    `oneapp/onehr/tools.py` has the whole argument.

    The form itself is `RecordForm`, which is the same component a record page
    uses — so a Check is the Switch it is everywhere, a Link opens the picker it
    opens everywhere, and the tabs are the doctype's own. Nothing here draws a
    control.
  -->
  <div class="mx-auto flex w-full max-w-4xl flex-col gap-4 p-4">
    <Panel ground="sunken" pad="loose" data-slot="tool-band">
      <div class="flex flex-col gap-1">
        <h2 class="text-xl-semibold text-ink-primary">{{ heading }}</h2>
        <p class="text-sm text-ink-secondary">{{ standing }}</p>
      </div>
    </Panel>

    <LoadingText v-if="loading && !loaded" :text="__('Loading')" />

    <template v-if="loaded">
      <Panel pad="loose" data-slot="tool-form">
        <RecordForm
          v-model:values="values"
          :spec="spec"
          :space-code="spaceCode"
          :screen="screen"
          :disabled="!spec.may_write"
        />
      </Panel>

      <!-- The tool half. A settings page stops above this line. -->
      <template v-if="isTool">
        <div class="flex items-center justify-between gap-3">
          <p class="text-sm text-ink-secondary" data-slot="tool-count">
            {{ tally }}
          </p>
          <Button
            icon-left="lucide-search"
            :label="__('Find people')"
            :loading="finding"
            :disabled="!spec.may_write"
            data-slot="tool-find"
            @click="find"
          />
        </div>

        <EmptyState
          v-if="found && !people.length"
          icon="lucide-users"
          :title="__('Nobody to do this to')"
          :message="__('Everybody these filters describe has one already.')"
        />

        <Panel v-else-if="people.length" pad="none" data-slot="tool-people">
          <!-- eslint-disable-next-line vue/no-restricted-html-elements -- not a list of records but a form laid out in columns: every row past the name is a number somebody types, and <ListView> renders cells rather than hosting controls -->
          <table class="w-full text-sm">
            <thead class="border-b border-outline-gray-1 text-ink-secondary">
              <tr>
                <!-- The tick and the name are one column, not two: a checkbox
                     with no label of its own is a control with no accessible
                     name, and a checkbox beside a cell repeating the name says
                     it twice. -->
                <th class="p-3 text-start font-medium">
                  <Checkbox
                    :model-value="allTicked"
                    :label="__('Everybody')"
                    data-slot="tool-all"
                    @update:model-value="tickAll"
                  />
                </th>
                <th class="p-3 text-start font-medium">{{ __('Id') }}</th>
                <th
                  v-for="one in spec.amounts"
                  :key="one"
                  class="w-32 p-3 text-start font-medium"
                >
                  {{ label(one) }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="one in people"
                :key="one.employee"
                class="border-b border-outline-gray-1 last:border-0"
                data-slot="tool-person"
              >
                <td class="p-3">
                  <Checkbox
                    v-model="one.ticked"
                    :label="one.employee_name || one.employee"
                  />
                </td>
                <td class="p-3 text-ink-muted">{{ one.employee }}</td>
                <td v-for="key in spec.amounts" :key="key" class="p-3">
                  <FormControl
                    v-model="one[key]"
                    type="number"
                    size="sm"
                    :placeholder="label(key)"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </Panel>

        <div v-if="people.length" class="flex justify-end">
          <Button
            variant="solid"
            :label="spec.verb"
            :loading="running"
            :disabled="!ticked.length"
            data-slot="tool-run"
            @click="run"
          />
        </div>
      </template>

      <!-- And the settings half. -->
      <div v-else class="flex justify-end">
        <Button
          variant="solid"
          :label="__('Save')"
          :loading="saving"
          :disabled="!spec.may_write"
          data-slot="tool-save"
          @click="save"
        />
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

import { Button, Checkbox, FormControl, LoadingText } from '@/ui'
import EmptyState from '@/shared/components/EmptyState.vue'
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
const people = ref([])
const loading = ref(false)
const loaded = ref(false)
const finding = ref(false)
const running = ref(false)
const saving = ref(false)
const found = ref(false)

/** What `RecordForm` is handed. The server sends `columns`, `all_columns` and
 *  `form` under the same names the screen spec uses, so this is the answer
 *  itself rather than a translation of it. */
const spec = computed(() => ({
  ...page.value,
  tab_icons: props.spec?.tab_icons || null,
}))

const isTool = computed(() => Boolean(page.value.verb))

const heading = computed(() => props.spec?.screen_label || props.spec?.label || '')

const standing = computed(() => {
  if (!loaded.value) return ''
  if (!page.value.may_write) {
    return __('These are the rules this workspace runs on. You may read them.')
  }
  return page.value.blurb || __('These are the rules this workspace runs on.')
})

const ticked = computed(() => people.value.filter((one) => one.ticked))

const allTicked = computed(
  () => people.value.length > 0 && ticked.value.length === people.value.length,
)

const tally = computed(() => {
  if (!found.value) return __('Describe who this is for, then find them.')
  if (!people.value.length) return ''
  return __('{0} of {1} ticked',
            [String(ticked.value.length), String(people.value.length)])
})

const label = (fieldname) => {
  const column = (page.value.all_columns || []).find(
    (one) => one.fieldname === fieldname,
  )
  return column?.label || fieldname
}

const tickAll = (on) => {
  for (const one of people.value) one.ticked = Boolean(on)
}

const load = async () => {
  loading.value = true
  try {
    const answer = await workspace.hrPage(props.screen)
    page.value = answer || {}
    values.value = { ...(answer?.values || {}) }
    loaded.value = true
  } catch (raised) {
    notifyError(raised)
  } finally {
    loading.value = false
  }
}

const find = async () => {
  finding.value = true
  try {
    const answer = await workspace.hrPeople(props.screen, values.value)
    // A fresh object per row, and the tick on it: these are what the controls
    // write into, so reusing the server's dicts would make a second Find a
    // silent undo of an edited amount rather than the deliberate one it is.
    people.value = (answer?.people || []).map((one) => ({ ...one, ticked: true }))
    found.value = true
    if (answer?.more) {
      notifySuccess(__('Showing the first {0}.', [String(people.value.length)]))
    }
  } catch (raised) {
    notifyError(raised)
    people.value = []
  } finally {
    finding.value = false
  }
}

const run = async () => {
  running.value = true
  try {
    const answer = await workspace.hrRun(props.screen, values.value,
                                         ticked.value.map((one) => ({ ...one })))
    notifySuccess(__('Done for {0}.', [String(answer?.count ?? 0)]))
    // Asked again rather than emptied: the finder excludes the people this
    // has just been done to, so what comes back is the honest remainder.
    await find()
  } catch (raised) {
    notifyError(raised)
  } finally {
    running.value = false
  }
}

const save = async () => {
  saving.value = true
  try {
    await workspace.hrSave(props.screen, values.value)
    notifySuccess(__('Saved.'))
  } catch (raised) {
    notifyError(raised)
  } finally {
    saving.value = false
  }
}

watch(() => props.screen, () => {
  loaded.value = false
  found.value = false
  people.value = []
  load()
}, { immediate: true })
</script>
