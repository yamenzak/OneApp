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
  <div class="flex h-full min-h-0 flex-col overflow-y-auto bg-surface-base">
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
    <div v-else-if="listing.length" class="mx-auto w-full max-w-xl p-6" data-slot="form-theirs">
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
    </div>

    <form
      v-else
      class="mx-auto flex w-full max-w-xl flex-col gap-4 p-6"
      data-slot="public-form"
      @submit.prevent="send"
    >
      <img
        v-if="form.said.banner_image"
        :src="form.said.banner_image"
        alt=""
        class="w-full rounded-6"
      />
      <h1 class="text-xl-semibold text-ink-primary">{{ form.said.title }}</h1>
      <!-- `v-html` because an introduction is a Text Editor field and a
           paragraph with a link in it is the ordinary thing to write there.
           Escaped server-side by `sanitize_html` in `oneforms/public.py`,
           which says why it is not enough that only an admin can set it: this
           page is served to strangers, so a script tag here would run in
           *their* browser. -->
      <!-- eslint-disable-next-line vue/no-v-html -- sanitised server-side -->
      <div v-if="form.said.introduction_text" class="prose prose-sm max-w-none" v-html="form.said.introduction_text" />

      <template v-for="field in shown" :key="field.fieldname">
        <p
          v-if="field.fieldtype === 'Section Break'"
          class="pt-2 text-p-xs font-medium uppercase tracking-wide text-ink-muted"
        >
          {{ field.label }}
        </p>
        <Select
          v-else-if="field.fieldtype === 'Select' || field.choices"
          v-model="values[field.fieldname]"
          :label="field.label"
          :description="field.description"
          :required="Boolean(field.reqd)"
          :options="choices(field)"
          :data-slot="`field-${field.fieldname}`"
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
          :data-slot="`field-${field.fieldname}`"
        />
      </template>

      <ErrorMessage v-if="failed" :message="failed" />

      <Button
        variant="solid"
        type="submit"
        class="self-start"
        :label="form.said.button_label || __('Send')"
        :loading="sending"
        data-slot="form-send"
      />
    </form>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'

import { Button, Checkbox, ErrorMessage, FormControl, Icon, LoadingIndicator, Select } from '@/ui'

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

/** What this key has sent before, when there is something and it is wanted. */
const listing = computed(() => (showing.value ? list.value.rows || [] : []))

/** The key, out of the URL. A link somebody was sent carries it. */
const key = computed(() => String(where.query.key || ''))

/** Hidden fields are not drawn, which is what hidden means. */
const shown = computed(() => (form.value?.fields || []).filter((one) => !one.hidden))

const control = (fieldtype) => CONTROLS[fieldtype] || 'text'

/** What a Select or a resolved Link offers. */
const choices = (field) =>
  field.choices || String(field.options || '').split('\n').filter(Boolean)

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

const send = async () => {
  sending.value = true
  failed.value = ''
  try {
    sent.value = await callMethod('oneapp.oneforms.public.send', {
      route: props.route,
      key: key.value,
      values: JSON.stringify(values),
    }, { silent: true })
    if (sent.value?.url) window.location.assign(sent.value.url)
  } catch (error) {
    failed.value = errorText(error)
  } finally {
    sending.value = false
  }
}

onMounted(read)
</script>
