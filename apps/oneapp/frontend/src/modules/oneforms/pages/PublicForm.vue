<template>
  <!--
    The page a stranger sees.

    `docs/ONEFORMS.md` stage 3. Not the workspace: no rail, no sidebar, no
    assistant, no notification feed, because every one of those is a window
    onto a workspace this reader has no account in — `App.vue` draws a
    `meta.public` route outside the shell for exactly that reason, and
    `Linked.vue` is the other one.

    Drawn here rather than by Frappe, whose own web form renders with Jinja
    into `templates/web.html` — its navbar, its footer, Bootstrap. All four of
    its endpoints are `allow_guest=True`, so there was never anything to work
    around; `hide_navbar` and `hide_footer` exist on `Web Form` because
    everybody who ships one reaches this conclusion.

    **Nothing here decides anything.** The access question was asked and
    answered before this drew, and the submission goes to Frappe's own
    `accept`, which asks it again.
  -->
  <!-- `form-page` is the fourth hook, and it exists because `body` is not the
       one that shows: this div carries a background utility and paints over it,
       so a theme setting "behind the form" has to reach here. -->
  <div class="flex h-full min-h-0 flex-col overflow-y-auto bg-surface-gray-1" data-slot="form-page">
    <div v-if="loading" class="grid flex-1 place-items-center">
      <LoadingIndicator class="size-5 text-ink-muted" />
    </div>

    <!--
      No such form, not published, expired key, wrong key. One sentence for all
      four, and the same one the server gives: out here the difference between
      them is a fact about somebody's workspace that a stranger has no business
      being told.
    -->
    <div v-else-if="!form" class="grid flex-1 place-items-center p-6">
      <div class="max-w-sm text-center">
        <p class="text-base-medium text-ink-primary">{{ __('This form is not available') }}</p>
        <p class="mt-1.5 text-p-base text-ink-secondary">
          {{ __('It may have been taken down, or the link may have expired. Ask whoever sent it for a new one.') }}
        </p>
      </div>
    </div>

    <!-- Sent. The page it becomes rather than a toast over the form: what
         somebody wants after pressing Send is to know it arrived, and a
         message that fades is the one thing that cannot say so. -->
    <div v-else-if="sent" class="grid flex-1 place-items-center p-6">
      <div class="max-w-md text-center" data-slot="form-sent">
        <Icon name="lucide-circle-check" class="mx-auto size-8 text-ink-muted" :aria-hidden="true" />
        <p class="mt-3 text-base-medium text-ink-primary">
          {{ sent.title || __('Sent') }}
        </p>
        <p class="mt-1.5 text-p-base text-ink-secondary">{{ sent.said }}</p>
      </div>
    </div>

    <!--
      What this key has already sent, where the form offers it. Above the form
      and not beside it: a supplier who opens their link wants to see what they
      sent before they send another, and the list is short by construction —
      the key's own `references` and nothing else.
    -->
    <Panel
      v-else-if="listing.length"
      pad="loose"
      class="mx-auto mb-auto mt-6 w-full max-w-xl sm:mt-10"
      data-slot="form-theirs"
    >
      <h1 class="text-xl-semibold text-ink-primary">{{ list.title }}</h1>
      <div class="mt-3 flex flex-col gap-1">
        <div
          v-for="one in listing"
          :key="one.name"
          class="flex items-center gap-3 border-b border-outline-gray-1 py-2 last:border-0"
        >
          <span
            v-for="column in list.columns"
            :key="column.fieldname"
            class="min-w-0 flex-1 truncate text-sm text-ink-secondary"
          >{{ one[column.fieldname] }}</span>
        </div>
      </div>
      <Button
        class="mt-4"
        :label="__('Send another')"
        data-slot="form-another"
        @click="showing = false"
      />
    </Panel>

    <!--
      A card on a page rather than a form against the window. Frappe's own
      renderer draws one and it is not decoration: a form with no edge reads as
      part of whatever site is around it, and there is no site around this one
      — so without the edge it reads as an unfinished page.

      Top-anchored rather than centred. `my-auto` put it halfway down a phone
      with the heading below the fold's worth of nothing, and a form is read
      from the top: `mb-auto` keeps the space underneath instead.
    -->
    <Panel
      v-else
      ref="paper"
      as="form"
      ground="base"
      pad="loose"
      class="mx-auto mb-auto mt-6 flex w-full max-w-xl flex-col gap-4 sm:mt-10"
      data-slot="public-form"
      @submit.prevent="send"
    >
      <img
        v-if="form.said.banner_image"
        :src="form.said.banner_image"
        alt=""
        class="w-full rounded-6"
      />
      <h1 class="text-xl-semibold text-ink-primary" data-slot="form-title">{{ form.said.title }}</h1>
      <!-- `v-html` because an introduction is a Text Editor field and a
           paragraph with a link in it is the ordinary thing to write there.
           Escaped server-side by `sanitize_html` in `oneforms/public.py`,
           which says why it is not enough that only an admin can set it: this
           page is served to strangers, so a script tag here would run in
           *their* browser. -->
      <!-- eslint-disable-next-line vue/no-v-html -- sanitised server-side -->
      <div v-if="form.said.introduction_text" class="prose prose-sm max-w-none" data-slot="form-introduction" v-html="form.said.introduction_text" />

      <!--
        Where they are, when there is more than one step. A bar of dots rather
        than "3 of 5": the question somebody abandoning a long form is asking
        is how much is left, and a count answers it in arithmetic while a bar
        answers it at a glance.
      -->
      <div
        v-if="pages.length > 1"
        class="flex items-center gap-1.5 pb-1"
        data-slot="form-progress"
        :aria-label="__('Step {0} of {1}', [at + 1, pages.length])"
      >
        <span
          v-for="(step, index) in pages"
          :key="index"
          class="h-1 flex-1 rounded-full"
          :class="index <= at ? WALKED : TO_COME"
        />
      </div>

      <template v-for="(section, index) in here.sections" :key="index">
        <!-- A heading, not a caption. A section break is where the person who
             built the form said one subject ends and another starts, and a
             small grey label above a field reads as that field's. -->
        <h2
          v-if="section.label"
          class="pt-2 text-base-medium text-ink-primary"
          :data-slot="`form-section-${index}`"
        >
          {{ section.label }}
        </h2>
        <div
          class="grid gap-4"
          :class="ACROSS[Math.min(section.columns.length, 4)]"
          :data-slot="`form-row-${index}`"
        >
          <div v-for="(column, side) in section.columns" :key="side" class="flex flex-col gap-4">
            <template v-for="field in column" :key="field.fieldname">
              <Select
                v-if="field.fieldtype === 'Select' || field.choices"
                v-model="values[field.fieldname]"
                :label="field.label"
                :description="field.description"
                :required="Boolean(field.reqd)"
                :options="choices(field)"
                :data-slot="`field-${field.fieldname}`"
              />
              <FileField
                v-else-if="ATTACHES.includes(field.fieldtype)"
                v-model="values[field.fieldname]"
                :field="field"
                :most="form.said.max_attachment_size || 0"
              />
              <Checkbox
                v-else-if="field.fieldtype === 'Check'"
                v-model="values[field.fieldname]"
                :label="field.label"
                :data-slot="`field-${field.fieldname}`"
              />
              <FormControl
                v-else
                v-model="values[field.fieldname]"
                :type="control(field.fieldtype)"
                :label="field.label"
                :description="field.description"
                :placeholder="field.placeholder"
                :required="Boolean(field.reqd)"
                :max="field.max_value || undefined"
                :data-slot="`field-${field.fieldname}`"
              />
            </template>
          </div>
        </div>
      </template>

      <!--
        The field nobody sees. Off-screen rather than `display: none`, because
        a script that skips hidden inputs is a script that skips this one; the
        label exists for whoever is listening to the page and `aria-hidden`
        keeps it out of the reading order. `oneforms/guarding.py` is the rest.
      -->
      <label v-if="form.trap" class="sr-only" aria-hidden="true">
        {{ __('Leave this empty') }}
        <FormControl
          v-model="trap"
          type="text"
          tabindex="-1"
          autocomplete="off"
          :data-slot="`field-${form.trap}`"
        />
      </label>

      <ErrorMessage v-if="failed" :message="failed" />

      <!-- Back is not a step of its own: a form nobody can go back through is
           a form people abandon rather than correct. Send only on the last
           page, because a Send beside a Next is two ways to lose the rest. -->
      <div class="flex items-center gap-2 pt-1">
        <Button
          v-if="at > 0"
          :label="__('Back')"
          data-slot="form-back"
          @click="at -= 1"
        />
        <Button
          v-if="at < pages.length - 1"
          variant="solid"
          :label="__('Next')"
          data-slot="form-next"
          @click="onward"
        />
        <Button
          v-else
          variant="solid"
          type="submit"
          :label="form.said.button_label || __('Send')"
          :loading="sending"
          data-slot="form-send"
        />
      </div>
    </Panel>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'

import { Button, Checkbox, ErrorMessage, FormControl, Icon, LoadingIndicator, Select } from '@/ui'

import { pageOf, pagesOf } from '@/modules/oneforms/lib/layout'
import { answered, asked } from '@/modules/oneforms/lib/showing'
import FileField from '@/modules/oneforms/components/FileField.vue'
import Panel from '@/shared/components/Panel.vue'
import { callMethod } from '@/shared/lib/runtime/resource'
import { errorText } from '@/shared/lib/runtime/errors'
import { __ } from '@/shared/lib/runtime/translate'

//: A Frappe fieldtype against the control that takes it. Everything absent
//: from here is a text box, which is the honest default: a form over a doctype
//: somebody customised may carry a fieldtype this table has never seen, and a
//: text box that saves is better than a page that does not draw.
const CONTROLS = {
  'Small Text': 'textarea',
  Text: 'textarea',
  'Long Text': 'textarea',
  Int: 'number',
  Float: 'number',
  Currency: 'number',
  Percent: 'number',
  Date: 'date',
  Datetime: 'datetime-local',
  Time: 'time',
  Password: 'password',
  Phone: 'tel',
}

//: Hoisted, because a class compared inside a `:class` is a name Tailwind's
//: JIT never sees — `tests/token_audit.py` reads for exactly this.
const WALKED = 'bg-surface-gray-7'
const TO_COME = 'bg-surface-gray-3'

//: Columns, by how many the section has. Written out rather than built from a
//: number for the same reason: `grid-cols-${n}` is a class that never ships.
//: Only from `md` up, which is where the shell switches — two fields side by
//: side on a phone is two fields nobody can type in, and the reader of a public
//: form is as likely to be on one as not.
const ACROSS = ['', '', 'md:grid-cols-2', 'md:grid-cols-3', 'md:grid-cols-4']

//: The two that are a file rather than a value. They go inline in the
//: submission — `FileField.vue` says why that is Frappe's design and not a
//: shortcut.
const ATTACHES = ['Attach', 'Attach Image']

const props = defineProps({ route: { type: String, required: true } })

const where = useRoute()
const form = ref(null)
const values = reactive({})
const loading = ref(true)
const sending = ref(false)
const failed = ref('')
const sent = ref(null)
const list = ref({ rows: [], columns: [], title: '' })
const showing = ref(true)
const paper = ref(null)
const at = ref(0)
const trap = ref('')

/** What this key has sent before, when there is something and it is wanted. */
const listing = computed(() => (showing.value ? list.value.rows || [] : []))

/** The key, out of the URL. A link somebody was sent carries it. */
const key = computed(() => String(where.query.key || ''))

/**
 * What is being asked, right now.
 *
 * Hidden by the form and put away by a condition are the same thing to whoever
 * is reading the page — `oneforms/lib/showing.js` answers both, and it depends
 * on `values`, so answering one question redraws the ones that were waiting on
 * it.
 */
const shown = computed(() => asked(form.value?.fields || [], values))

/** The rows read as steps, sections and columns — `oneforms/lib/layout.js`. */
const pages = computed(() => pagesOf(shown.value))

/** The step being drawn. Never undefined: an empty form draws an empty step. */
const here = computed(() => pages.value[at.value] || { sections: [] })

const control = (fieldtype) => CONTROLS[fieldtype] || 'text'

/** What a Select or a resolved Link offers. */
const choices = (field) =>
  field.choices || String(field.options || '').split('\n').filter(Boolean)

/**
 * The form's own stylesheet, put into the document.
 *
 * An element in `document.head` rather than a `<style>` in the template: this
 * is a route of its own with nothing else on the page, so there is nothing to
 * scope it away from, and a style block inside a template is a thing Vue's
 * single-file parser has opinions about. Taken away with the component, so
 * navigating off a styled form does not leave its rules behind.
 *
 * Checked server-side, not here — `service.check_css` refuses an `@import`, a
 * `url()` to another site and anything that would close the element. A guard
 * in the browser would be a guard on the wrong side of the wire.
 */
let sheet = null
const dress = (css) => {
  if (!css) return
  sheet = sheet || document.head.appendChild(document.createElement('style'))
  sheet.textContent = css
}

onBeforeUnmount(() => {
  sheet?.remove()
  sheet = null
})

const read = async () => {
  try {
    form.value = await callMethod(
      'oneapp.oneforms.public.page',
      { route: props.route, key: key.value },
      { silent: true, method: 'GET' },
    )
    for (const field of form.value.fields || []) {
      if (field.default != null) values[field.fieldname] = field.default
    }
    dress(form.value.css)
    at.value = 0
    if (form.value.said.show_list && key.value) await theirs()
  } catch {
    // Said in the page rather than as a toast, and said the same way for every
    // reason it could have failed.
    form.value = null
  } finally {
    loading.value = false
  }
}

/**
 * The documents this key may look at.
 *
 * Silent and swallowed: a form whose list is not set up, or a key with nothing
 * against it yet, should draw the form rather than an error — the list is an
 * extra, and the form is the point.
 */
const theirs = async () => {
  try {
    list.value = await callMethod(
      'oneapp.oneforms.invite.theirs',
      { route: props.route, key: key.value },
      { silent: true, method: 'GET' },
    )
  } catch {
    list.value = { rows: [], columns: [], title: '' }
  }
}

/**
 * On to the next step, if this one is filled in.
 *
 * The browser's own validation rather than ours: every control carries
 * `required` already, and only the current step is in the document, so
 * `reportValidity` asks exactly the right question and puts the message where
 * the reader is looking. A second implementation would be a second set of
 * rules about what counts as an email address.
 */
const onward = () => {
  // `$el`, because the ref is on a component: `Panel` renders the `<form>` and
  // `reportValidity` is the element's.
  const element = paper.value?.$el
  if (element?.reportValidity && !element.reportValidity()) return
  failed.value = ''
  at.value += 1
}

/**
 * The step holding whatever the server complained about.
 *
 * A refusal naming a field is no use on page three of four — the reader is
 * told something is wrong with a question they cannot see. Matched on the
 * label because that is what the message says and what they read.
 */
const blame = (said) => {
  const named = shown.value.find(
    (one) => one.label && String(said).includes(one.label))
  if (named) at.value = pageOf(pages.value, named.fieldname)
}

const send = async () => {
  sending.value = true
  failed.value = ''
  try {
    sent.value = await callMethod('oneapp.oneforms.public.send', {
      route: props.route,
      key: key.value,
      stamp: form.value?.stamp || '',
      values: JSON.stringify({
        ...answered(form.value?.fields || [], values),
        // Empty unless something that is not a person filled it in.
        [form.value?.trap || '_website']: trap.value,
      }),
    }, { silent: true })
    if (sent.value?.url) window.location.assign(sent.value.url)
  } catch (error) {
    failed.value = errorText(error)
    blame(failed.value)
  } finally {
    sending.value = false
  }
}

onMounted(read)
</script>
