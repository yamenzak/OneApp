<template>
  <!--
    Building one of the workspace's own roles.

    A role is a name and a list of what it reaches, so the dialog is those two
    things and nothing else. The list is not free — `available` is every
    doctype this workspace's own spaces expose, and the server refuses a save
    outside it — which is the whole security argument for letting a customer
    author permissions at all. So this offers exactly that list and there is no
    way to type something into it.

    Grouped by space and named by the screen's own word: a doctype is called
    `Sales Invoice` and the navigation calls it Invoices, and the second is the
    word the person building a role has been looking at all week.

    Every row is a select and not a tick, because "what may they do to this"
    has four answers and a checkbox has two. None is one of the four and is the
    default, so an empty dialog grants nothing.
  -->
  <Dialog
    v-model="showing"
    size="2xl"
    :title="role ? __('Edit {0}', [role.role_label]) : __('New role')"
  >
    <template #default>
      <div class="flex flex-col gap-5">
        <div class="grid gap-4 sm:grid-cols-2">
          <FormControl
            v-model="label"
            type="text"
            :label="__('Name')"
            :placeholder="__('Bookkeeper')"
            :description="__('What you will see when handing it out.')"
          />
          <FormControl
            v-model="description"
            type="text"
            :label="__('What it is for')"
            :placeholder="__('Reads everything, edits the invoices')"
            :description="__('One sentence, for whoever hands it out next.')"
          />
        </div>

        <EmptyState
          v-if="!groups.length"
          icon="lucide-shield"
          :title="__('Nothing to build one from yet')"
          :description="__('A role reaches the screens your apps bring. Add an app first and its screens appear here.')"
        />

        <section v-for="group in groups" :key="group.space" class="flex flex-col gap-1">
          <h4 class="text-p-xs uppercase tracking-wide text-ink-muted">
            {{ group.label }}
          </h4>

          <div
            v-for="row in group.rows"
            :key="row.document_type"
            data-slot="grant-row"
            class="flex items-center gap-3 border-b border-outline-gray-1 py-2"
          >
            <span class="min-w-0 flex-1 truncate text-sm text-ink-primary">
              {{ row.label }}
            </span>

            <!-- Only where something is granted. "Only their own" beside a row
                 that grants nothing is a question about nothing, and it reads
                 as though the row were half on. -->
            <Checkbox
              v-if="chosen[row.document_type]"
              :model-value="mine[row.document_type] || false"
              :label="__('Only their own')"
              @update:model-value="mine[row.document_type] = $event"
            />

            <!-- Sized from outside: FormControl computes `w-full` for a
                 select and there is no prop to turn it off, so a width on the
                 control itself loses to the library's own. -->
            <div class="w-32 shrink-0">
              <FormControl
                type="select"
                :model-value="chosen[row.document_type] || ''"
                :options="levels"
                @update:model-value="pick(row, $event)"
              />
            </div>
          </div>
        </section>

        <ErrorMessage v-if="error" :message="error" />
      </div>
    </template>

    <template #actions>
      <Button
        variant="solid"
        :label="role ? __('Save changes') : __('Create role')"
        :disabled="!label.trim()"
        :loading="saving"
        @click="save"
      />
      <Button :label="__('Cancel')" @click="showing = false" />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { Button, Checkbox, Dialog, ErrorMessage, FormControl } from '@/ui'
import EmptyState from '@/shared/components/EmptyState.vue'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'
import { errorText } from '@/shared/lib/runtime/errors'

const props = defineProps({
  // Every doctype this workspace's spaces expose: {space, space_label,
  // document_type, label}. The server's allowlist, sent so the dialog can
  // only offer what a save would accept.
  available: { type: Array, default: () => [] },
  // Levels the server knows. Read from the payload rather than written here,
  // so a fourth one is a server change and not a server change plus this file.
  accessLevels: { type: Array, default: () => [] },
  // The role being edited, or null for a new one.
  role: { type: Object, default: null },
})

const emit = defineEmits(['saved'])

const showing = defineModel({ type: Boolean, default: false })

const label = ref('')
const description = ref('')
const chosen = reactive({})
const mine = reactive({})
const saving = ref(false)
const error = ref('')

// Written out rather than run through `__(level)`: the extractor reads
// literals, so a variable inside `__()` is a word that never reaches a
// catalogue and stays English in Arabic. A level not in here still renders,
// under its own name — untranslated beats absent.
const WORDS = () => ({ Read: __('Read'), Write: __('Write'), Manage: __('Manage') })

// None first and empty, so a select that has never been touched grants
// nothing — the safe answer is the one you get by doing nothing.
const levels = computed(() => {
  const words = WORDS()
  return [
    { label: __('None'), value: '' },
    ...props.accessLevels.map((one) => ({ label: words[one] || one, value: one })),
  ]
})

/** The allowlist, grouped the way somebody thinks about it. */
const groups = computed(() => {
  const byspace = new Map()
  for (const row of props.available) {
    const key = row.space || ''
    if (!byspace.has(key)) {
      byspace.set(key, { space: key, label: row.space_label || key, rows: [] })
    }
    byspace.get(key).rows.push(row)
  }
  return [...byspace.values()]
})

const pick = (row, value) => {
  chosen[row.document_type] = value
  // Dropping a row to None drops its restriction with it, or reopening the
  // dialog would show "only their own" ticked on a row that grants nothing.
  if (!value) mine[row.document_type] = false
}

/** Fill the form from the role being edited, or empty it for a new one. */
const reset = () => {
  error.value = ''
  label.value = props.role?.role_label || ''
  description.value = props.role?.description || ''
  for (const key of Object.keys(chosen)) delete chosen[key]
  for (const key of Object.keys(mine)) delete mine[key]
  for (const grant of props.role?.grants || []) {
    chosen[grant.document_type] = grant.access
    mine[grant.document_type] = !!grant.if_owner
  }
}

watch(showing, (open) => open && reset(), { immediate: true })

const save = async () => {
  saving.value = true
  error.value = ''
  // The whole list, because `save_role` replaces rather than patches: a row
  // set back to None is a row the role loses, and saying so by omission is
  // what makes that true.
  const grants = props.available
    .filter((row) => chosen[row.document_type])
    .map((row) => ({
      space: row.space,
      document_type: row.document_type,
      access: chosen[row.document_type],
      if_owner: mine[row.document_type] ? 1 : 0,
    }))

  try {
    await workspace.saveWorkspaceRole(
      label.value.trim(), grants, description.value.trim(), props.role?.name || null,
    )
    showing.value = false
    emit('saved')
  } catch (e) {
    error.value = errorText(e)
  } finally {
    saving.value = false
  }
}
</script>
