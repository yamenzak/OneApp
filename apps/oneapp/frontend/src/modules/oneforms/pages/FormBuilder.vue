<template>
  <!--
    One form, built.

    `docs/ONEFORMS.md` stage 2. A `Web Form Field` is **chosen from the
    doctype** — its `fieldname` is a Select of the target's own fields — so
    this is not a field factory. It is "which of these, in what order, said
    how", which is a smaller and more honest thing than a survey builder and is
    why a form over Job Applicant makes a Job Applicant.

    The interaction is `bwhtech/forms_pro`'s and none of its code is: its
    builder is a grid over its own `Form Field`, with a row, a column and a
    cell index on each, and `Web Form Field` has none of those. Porting it
    would have been porting its schema.

    Three columns, and they are the three questions: what could go on
    (the doctype), what is on (the form), and what this one says (the field, or
    the form itself when nothing is picked).

    Drag is the browser's own, like `printing/BuilderZone.vue` — the same
    gesture in the same product, and no library for it.
  -->
  <PageHeader>
    <Trail :items="crumbs" />
  </PageHeader>

  <!--
    The controls in a bar of their own rather than in the header, because
    `PageHeader` takes the trail and nothing else — it is where you *are*, and
    what you can do here belongs with the thing you are doing it to.
  -->
  <div class="flex shrink-0 flex-wrap items-center gap-2 px-4 pt-4" data-slot="builder-bar">
    <span class="min-w-0 flex-1 truncate text-xs text-ink-muted">/{{ page.route }}</span>
    <Badge
      :theme="page.published ? 'green' : 'gray'"
      variant="subtle"
      :label="page.published ? __('Live') : __('Draft')"
    />
    <Button
      :label="page.published ? __('Take down') : __('Publish')"
      :loading="publishing"
      data-slot="builder-publish"
      @click="togglePublished"
    />
    <Button
      :label="__('Look')"
      data-slot="builder-look"
      @click="looking = true"
    />
    <Button
      :label="__('Style')"
      data-slot="builder-style"
      @click="styling = true"
    />
    <Button
      variant="solid"
      :label="__('Save')"
      :loading="saving"
      :disabled="!dirty"
      data-slot="builder-save"
      @click="save"
    />
  </div>

  <div class="flex min-h-0 flex-1 gap-3 p-4" data-slot="form-builder">
    <!-- What could go on. The doctype's own fields, and the two breaks that
         belong to no doctype. -->
    <Panel class="flex w-52 shrink-0 flex-col gap-1 overflow-y-auto" pad="tight">
      <p class="px-1 pb-1 text-p-xs font-medium uppercase tracking-wide text-ink-muted">
        {{ __('Layout') }}
      </p>
      <!-- eslint-disable-next-line vue/no-restricted-html-elements -- a thing you pick up rather than press; <Button> lays its content out in one row and a drag chip is two lines, and `draggable` on it would be an attribute fighting a component -->
      <button
        v-for="one in page.breaks"
        :key="one"
        type="button"
        draggable="true"
        class="rounded-6 border border-dashed border-outline-gray-2 px-2 py-1 text-start text-xs text-ink-secondary"
        data-slot="builder-break"
        @dragstart="carry($event, { kind: 'break', fieldtype: one })"
      >
        {{ one }}
      </button>

      <p class="px-1 pb-1 pt-3 text-p-xs font-medium uppercase tracking-wide text-ink-muted">
        {{ page.doc_type }}
      </p>
      <p v-if="!spare.length" class="px-1 text-xs text-ink-muted">
        {{ __('Every field is already on the form.') }}
      </p>
      <!-- eslint-disable-next-line vue/no-restricted-html-elements -- a thing you pick up rather than press; <Button> lays its content out in one row and a drag chip is two lines, and `draggable` on it would be an attribute fighting a component -->
      <button
        v-for="one in spare"
        :key="one.fieldname"
        type="button"
        draggable="true"
        class="rounded-6 border border-outline-gray-1 px-2 py-1 text-start text-xs text-ink-secondary"
        data-slot="builder-spare"
        @dragstart="carry($event, { kind: 'field', fieldname: one.fieldname })"
        @dblclick="add(one.fieldname)"
      >
        <span class="block truncate">{{ one.label }}</span>
        <span class="block truncate text-2xs text-ink-muted">{{ one.fieldtype }}</span>
      </button>
    </Panel>

    <!-- What is on, in the order it will read. -->
    <Panel
      class="flex min-w-0 flex-1 flex-col gap-1 overflow-y-auto"
      pad="tight"
      @dragover.prevent
      @drop.prevent="drop($event, fields.length)"
    >
      <EmptyState
        v-if="!fields.length"
        icon="lucide-inbox"
        :title="__('Nothing on this form yet')"
        :description="__('Drag a field in from the left, or double-click one.')"
      />
      <div
        v-for="(field, at) in fields"
        :key="field.key"
        draggable="true"
        class="rounded-6 border px-2 py-1.5"
        :class="at === picked ? PICKED : PLAIN"
        :data-slot="`builder-row-${field.fieldname}`"
        @click="picked = at"
        @dragstart="carry($event, { kind: 'move', at })"
        @dragover.prevent.stop
        @drop.prevent.stop="drop($event, at)"
      >
        <span class="flex items-center gap-2">
          <Icon name="lucide-grip-vertical" class="size-3 shrink-0 text-ink-muted" :aria-hidden="true" />
          <span class="min-w-0 flex-1 truncate text-sm text-ink-primary">
            {{ field.label || field.fieldtype }}
          </span>
          <Badge v-if="field.reqd" variant="subtle" :label="__('Required')" />
          <span class="shrink-0 text-xs text-ink-muted">{{ field.fieldtype }}</span>
          <Button
            variant="ghost"
            icon="lucide-x"
            :label="__('Take this off the form')"
            :tooltip="__('Take off')"
            @click.stop="remove(at)"
          />
        </span>
      </div>
    </Panel>

    <!-- What this one says — the picked field, or the form when none is. -->
    <Panel class="flex w-72 shrink-0 flex-col gap-3 overflow-y-auto" pad="tight">
      <template v-if="chosen">
        <FormControl
          v-model="chosen.label"
          type="text"
          :label="__('Label')"
          @update:model-value="touch"
        />
        <FormControl
          v-model="chosen.placeholder"
          type="text"
          :label="__('Placeholder')"
          @update:model-value="touch"
        />
        <FormControl
          v-model="chosen.description"
          type="textarea"
          :label="__('Help text')"
          @update:model-value="touch"
        />
        <FormControl
          v-model="chosen.default"
          type="text"
          :label="__('Default')"
          @update:model-value="touch"
        />
        <!-- Required is the doctype's when the doctype insists: the server
             keeps it on whatever the form says, so offering the switch would
             be offering a control that silently does nothing. -->
        <Checkbox
          v-model="chosen.reqd"
          :disabled="Boolean(required(chosen.fieldname))"
          :label="__('Required')"
          @update:model-value="touch"
        />
        <Checkbox v-model="chosen.read_only" :label="__('Read only')" @update:model-value="touch" />

        <!--
          Branching. A comparison rather than code — `oneforms/showing.py` is
          the grammar and the reason: Frappe's `depends_on` holds JavaScript
          and its renderer evals it, and this product does not run a customer's
          code in a stranger's browser.
        -->
        <FormControl
          v-model="chosen.depends_on"
          type="text"
          :label="__('Only ask this when')"
          :placeholder="ASKED_WHEN"
          :description="__('A comparison, like {0}. Leave it empty to always ask.', [ASKED_WHEN])"
          data-slot="builder-when"
          @update:model-value="touch"
        />
        <FormControl
          v-if="LIMITED.includes(chosen.fieldtype)"
          v-model="chosen.max_length"
          type="number"
          :label="__('Longest answer')"
          @update:model-value="touch"
        />
        <FormControl
          v-if="NUMERIC.includes(chosen.fieldtype)"
          v-model="chosen.max_value"
          type="number"
          :label="__('Largest number')"
          @update:model-value="touch"
        />
      </template>

      <template v-else>
        <FormControl
          v-model="settings.title"
          type="text"
          :label="__('Name')"
          @update:model-value="touch"
        />
        <FormControl
          v-model="settings.introduction_text"
          type="textarea"
          :label="__('Introduction')"
          @update:model-value="touch"
        />
        <FormControl
          v-model="settings.button_label"
          type="text"
          :label="__('Button')"
          @update:model-value="touch"
        />
        <FormControl
          v-model="settings.success_message"
          type="textarea"
          :label="__('After it is sent')"
          @update:model-value="touch"
        />

        <!-- Nothing is uploaded separately: a file rides inline in the
             submission, so this is the size of the whole POST and is worth
             being a number somebody set rather than one they met. -->
        <FormControl
          v-model="settings.max_attachment_size"
          type="number"
          :label="__('Largest file, in MB')"
          data-slot="builder-attachment-size"
          @update:model-value="touch"
        />

        <p class="pt-2 text-p-xs font-medium uppercase tracking-wide text-ink-muted">
          {{ __('Who can reach it') }}
        </p>
        <!-- Three switches and they are not independent: anyone means no
             sign-in, which is Frappe's own rule and the server keeps it. -->
        <Checkbox v-model="settings.anonymous" :label="__('Anyone with the link')" @update:model-value="touch" />
        <Checkbox
          v-model="settings.login_required"
          :disabled="Boolean(settings.anonymous)"
          :label="__('Must be signed in')"
          @update:model-value="touch"
        />
        <Checkbox v-model="settings.key_required" :label="__('Only by invitation')" @update:model-value="touch" />
        <Checkbox v-model="settings.allow_edit" :label="__('They can change it afterwards')" @update:model-value="touch" />
        <Checkbox v-model="settings.allow_multiple" :label="__('They can send more than one')" @update:model-value="touch" />
        <Checkbox v-model="settings.show_list" :label="__('They can see their own')" @update:model-value="touch" />

        <!-- And which of them they see. Not optional: with none set, Frappe
             falls back to the doctype's list-view fields and resolves every
             Link in them against Guest — which answers "You don't have
             permission to access…" to somebody holding a good key. A Link is
             the one thing that cannot go here, so it is not offered. -->
        <div v-if="settings.show_list" class="flex flex-col gap-1" data-slot="builder-columns">
          <p class="text-p-xs font-medium uppercase tracking-wide text-ink-muted">
            {{ __('What they see in that list') }}
          </p>
          <Checkbox
            v-for="one in page.columnable"
            :key="one.fieldname"
            :model-value="columns.includes(one.fieldname)"
            :label="one.label || one.fieldname"
            :disabled="!columns.includes(one.fieldname) && columns.length >= MOST_COLUMNS"
            @update:model-value="pickColumn(one.fieldname, $event)"
          />
          <p class="text-2xs text-ink-muted">
            {{ __('Up to {0}. None chosen shows the first few.', [MOST_COLUMNS]) }}
          </p>
        </div>
        <!-- Off unless somebody turns it on. An internal request filed through
             a keyed link has already been acknowledged by the page; a public
             application form is the case this is for. Deliberately does not
             carry their answers — `oneforms/invite.confirm`. -->
        <Checkbox
          v-model="settings.custom_onespace_reply"
          :label="__('Write back to confirm it arrived')"
          data-slot="builder-confirm"
          @update:model-value="touch"
        />

        <!--
          On the customer's own site. `allowed_embedding_domains` is Frappe's
          own field and has been on this form since stage 1 with nothing to set
          it — a form that cannot be embedded is a form people link away to.
        -->
        <p class="pt-2 text-p-xs font-medium uppercase tracking-wide text-ink-muted">
          {{ __('On another site') }}
        </p>
        <FormControl
          v-model="settings.allowed_embedding_domains"
          type="textarea"
          :label="__('Sites that may embed it')"
          :description="__('One per line, like shop.example.com. Empty means none.')"
          data-slot="builder-embedding"
          @update:model-value="touch"
        />
        <div v-if="settings.allowed_embedding_domains" class="flex items-center gap-2">
          <span class="min-w-0 flex-1 truncate text-xs text-ink-muted">{{ embed }}</span>
          <Button
            variant="ghost"
            icon="lucide-copy"
            :label="__('Copy the embed code')"
            :tooltip="__('Copy the embed code')"
            data-slot="builder-embed"
            @click="copy(embed)"
          />
        </div>

    <!-- Who it was sent to. Only where it is a form you are sent: an
         invitation to an open page is a link anybody already had, and the
         server refuses to make one. -->
        <div
          v-if="settings.key_required"
          class="flex flex-col gap-2 pt-2"
          data-slot="builder-invites"
        >
      <p class="text-p-xs font-medium uppercase tracking-wide text-ink-muted">
        {{ __('Invitations') }}
      </p>
      <FormControl
        v-model="inviting"
        type="email"
        :placeholder="__('Their address')"
        @keyup.enter="sendInvite"
      />
      <Button
        :label="__('Send an invitation')"
        :loading="sendingInvite"
        data-slot="builder-invite"
        @click="sendInvite"
      />
      <p v-if="!invites.length" class="text-xs text-ink-muted">
        {{ __('Nobody has been invited yet.') }}
      </p>
      <div
        v-for="one in invites"
        :key="one.name"
        class="flex items-center gap-1 border-b border-outline-gray-1 pb-1 last:border-0"
      >
        <span class="min-w-0 flex-1 truncate text-xs text-ink-secondary">
          {{ one.first_used_on ? __('Answered') : __('Not answered yet') }}
        </span>
        <Button
          variant="ghost"
          icon="lucide-copy"
          :label="__('Copy the link')"
          :tooltip="__('Copy the link')"
          @click="copy(one.url)"
        />
        <Button
          variant="ghost"
          icon="lucide-x"
          :label="__('Take this link back')"
          :tooltip="__('Take it back')"
          @click="uninvite(one)"
        />
      </div>
        </div>
      </template>
    </Panel>
  </div>

  <!--
    The page's own stylesheet, in OneCode's editor. Its own door rather than a
    box in the settings column, because it is code on a page strangers load:
    the server refuses an `@import`, a `url()` to another site and anything
    that closes the element, and each refusal is a sentence to read rather
    than a field that went red.

    CSS and not JavaScript, and that is not caution. `client_script` is written
    against `frappe.web_form.on(...)` — a runtime Frappe's own Jinja page has
    and this Vue one does not — so a script saved here would be dead code
    somebody had written. `oneforms/service.py` says the rest.
  -->
  <!--
    The six settings, for the person who wants their logo at the top rather
    than a stylesheet. Both doors write `custom_css`: `theming.py` owns a block
    between two markers and leaves whatever was written by hand around it.
  -->
  <LookPanel v-model="looking" :name="name" :theme="theme" @saved="restyled" />

  <CodeDialog
    v-model="styling"
    :value="css"
    language="css"
    :label="__('Styling')"
    @apply="restyle"
  />
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'

import { Badge, Button, Checkbox, FormControl, Icon, PageHeader } from '@/ui'

import CodeDialog from '@/modules/onecode/components/CodeDialog.vue'
import LookPanel from '@/modules/oneforms/components/LookPanel.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import Panel from '@/shared/components/Panel.vue'
import Trail from '@/shared/components/Trail.vue'
import { useCrumbs } from '@/shared/composables/useCrumbs'
import { workspace } from '@/shared/lib/workspace'
import { notifyError, notifySuccess } from '@/shared/lib/runtime/notify'
import { nameOf } from '@/shared/lib/brand/naming'
import { __ } from '@/shared/lib/runtime/translate'

//: Hoisted, because a class compared inside a `:class` is a name Tailwind's
//: JIT never sees — `tests/token_audit.py` reads for exactly this.
const PICKED = 'border-outline-gray-4 bg-surface-gray-1'
const PLAIN = 'border-outline-gray-1'

//: What a condition looks like, shown rather than described. A grammar
//: explained in prose is a grammar people get wrong once each.
const ASKED_WHEN = 'status == "Open"'

//: Which fieldtypes the two limits mean anything for. `max_length` on a date
//: and `max_value` on a name are controls that do nothing, and a panel of
//: those is a panel people stop reading.
//: What fits on a phone, which is where a supplier opens the link somebody
//: mailed them. `oneforms/service.LIST_COLUMNS` is the same number.
const MOST_COLUMNS = 4

const LIMITED = ['Data', 'Small Text', 'Text', 'Long Text', 'Text Editor', 'Phone']
const NUMERIC = ['Int', 'Float', 'Currency', 'Percent', 'Rating']

const props = defineProps({ name: { type: String, required: true } })

const page = reactive({ doc_type: '', route: '', published: 0, breaks: [],
                        available: [], columnable: [] })
const settings = reactive({})
const fields = ref([])
const picked = ref(-1)
const dirty = ref(false)
const columns = ref([])
const invites = ref([])
const inviting = ref('')
const sendingInvite = ref(false)
const saving = ref(false)
const publishing = ref(false)
const styling = ref(false)
const looking = ref(false)
const css = ref('')
const theme = ref({})

const crumbs = useCrumbs(
  { label: nameOf('oneforms'), route: { name: 'Forms' } },
  computed(() => ({ label: settings.title || props.name })),
)

const chosen = computed(() => fields.value[picked.value] || null)

/**
 * The snippet somebody pastes into their own page.
 *
 * Built here rather than sent, because everything in it is already known to the
 * browser and a second spelling of a URL is one that goes stale.
 */
const embed = computed(() =>
  `<iframe src="${window.location.origin}/one/f/${page.route}" `
  + 'style="width:100%;height:720px;border:0" title="'
  + (settings.title || '').replace(/"/g, '') + '"></iframe>')

/** What the doctype has that is not on the form yet. */
const spare = computed(() => {
  const on = new Set(fields.value.map((one) => one.fieldname))
  return (page.available || []).filter((one) => !on.has(one.fieldname))
})

/** Whether the doctype itself insists on that field. */
const required = (fieldname) =>
  (page.available || []).find((one) => one.fieldname === fieldname)?.reqd || 0

const touch = () => { dirty.value = true }

/** One column on or off, in the order they were chosen. */
const pickColumn = (fieldname, on) => {
  columns.value = on
    ? [...columns.value, fieldname].slice(0, MOST_COLUMNS)
    : columns.value.filter((one) => one !== fieldname)
  touch()
}

/** A row on the form, from a doctype field or a break. */
let made = 0
const row = (one) => ({ key: `row-${(made += 1)}`, ...one })

const read = async () => {
  try {
    const answer = await workspace.formRead(props.name)
    Object.assign(page, {
      doc_type: answer.doc_type, route: answer.route,
      published: answer.published, breaks: answer.breaks,
      available: answer.available,
      columnable: answer.columnable || [],
    })
    columns.value = answer.list_columns || []
    css.value = answer.css || ''
    theme.value = answer.theme || {}
    Object.assign(settings, answer.settings || {})
    fields.value = (answer.fields || []).map(row)
    picked.value = -1
    dirty.value = false
    if (settings.key_required) await readInvites()
  } catch (error) {
    notifyError(error)
  }
}

const readInvites = async () => {
  try {
    invites.value = (await workspace.formInvitations(props.name))?.rows || []
  } catch {
    // A form that is not keyed answers nothing, which is not a failure worth a
    // toast over a page that is otherwise working.
    invites.value = []
  }
}

const sendInvite = async () => {
  sendingInvite.value = true
  try {
    const made = await workspace.formInvite(props.name, inviting.value, {}, '')
    inviting.value = ''
    await readInvites()
    // The link is the invitation and the letter is a copy of it, so a
    // workspace with no outgoing account still gets one — said here, because
    // "sent" and "made, go and send it" are different things to have done.
    if (made?.to && !made?.mailed) {
      notifyError(__('The link is made, but it could not be mailed. Copy it and send it yourself.'))
    }
  } finally {
    sendingInvite.value = false
  }
}

const uninvite = async (one) => {
  await workspace.formUninvite(one.name)
  await readInvites()
}

/** The link, on the clipboard, for sending by hand. */
const copy = async (url) => {
  try {
    await navigator.clipboard.writeText(url)
    notifySuccess(__('Copied'))
  } catch {
    notifyError(__('This browser would not let us copy it.'))
  }
}

// What is being dragged, held here rather than in the event: `dataTransfer`
// stringifies, and a round trip through JSON for a move inside one list is a
// conversion that can only go wrong.
let carrying = null
const carry = (event, what) => {
  carrying = what
  event.dataTransfer.effectAllowed = 'move'
  // Set anyway, because Firefox will not start a drag without it.
  event.dataTransfer.setData('text/plain', what.kind)
}

const drop = (event, at) => {
  const what = carrying
  carrying = null
  if (!what) return

  if (what.kind === 'move') {
    const [moved] = fields.value.splice(what.at, 1)
    fields.value.splice(what.at < at ? at - 1 : at, 0, moved)
  } else if (what.kind === 'break') {
    fields.value.splice(at, 0, row({ fieldtype: what.fieldtype, fieldname: '', label: '' }))
  } else {
    const field = (page.available || []).find((one) => one.fieldname === what.fieldname)
    if (!field) return
    fields.value.splice(at, 0, row({
      fieldname: field.fieldname, fieldtype: field.fieldtype,
      label: field.label, reqd: field.reqd,
    }))
  }
  picked.value = -1
  dirty.value = true
}

/** Double-click puts it at the end, for anybody who would rather not drag. */
const add = (fieldname) => {
  carrying = { kind: 'field', fieldname }
  drop(null, fields.value.length)
}

const remove = (at) => {
  fields.value.splice(at, 1)
  picked.value = -1
  dirty.value = true
}

const save = async () => {
  saving.value = true
  try {
    await workspace.formLayout(props.name, fields.value)
    await workspace.formSettings(props.name, { ...settings, list_columns: columns.value })
    notifySuccess(__('Saved'))
    await read()
  } catch (error) {
    notifyError(error)
  } finally {
    saving.value = false
  }
}

/**
 * The stylesheet, saved on its own.
 *
 * Not folded into Save, because it is checked by different rules and a refusal
 * has to say which one it broke — a page that answered "Saved" for the fields
 * and swallowed "no @import" for the CSS would be a page that lied.
 */
const restyle = async (next) => {
  try {
    const answer = await workspace.formStyle(props.name, next)
    css.value = answer.css || ''
    notifySuccess(__('Saved'))
  } catch (error) {
    notifyError(error)
  }
}

/** What the Look panel saved, back into both the editor and the panel. */
const restyled = (answer) => {
  css.value = answer?.css || ''
  theme.value = answer?.theme || {}
}

const togglePublished = async () => {
  publishing.value = true
  try {
    await workspace.formPublish(props.name, !page.published)
    await read()
  } finally {
    publishing.value = false
  }
}

onMounted(read)
</script>
