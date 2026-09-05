<template>
  <!--
    Spacing, which on a form is not decoration.

    A doctype like Project has fifty-odd fields and Frappe puts them in three or
    four sections, so what a person meets is a wall. At `gap-4` between fields
    and `gap-5` between sections the two gaps were within a few pixels of each
    other, and nothing on the screen said where one group ended — the eye had to
    read every label to find the one it wanted.

    So the steps are now separated rather than merely present: 24px between
    fields, 40px between sections, and the rule that starts a section sits 40px
    off the one above. It is the same information and it costs a screenful of
    height on the longest doctypes; a form somebody can scan is worth the scroll.
  -->
  <div class="flex flex-col gap-10">
    <section
      v-for="(section, index) in sections"
      :key="index"
      class="flex flex-col gap-5"
      :class="index && !section.hide_border ? 'border-t border-outline-gray-1 pt-10' : ''"
    >
      <!-- A heading only where the doctype wrote one. Frappe's own forms leave
           the first section unlabelled more often than not, and "Details" over
           the first four fields of every record is a word that says nothing.

           A collapsible section gets the same heading as a button, because the
           heading is the only thing on the row worth pressing and a separate
           chevron beside it is a second target for one action. -->
      <Button
        v-if="section.label && section.collapsible"
        variant="ghost"
        size="sm"
        class="-ml-2 self-start"
        :aria-expanded="!folded(index, section)"
        @click="toggle(index)"
      >
        <span
          class="flex items-center gap-1.5 text-p-xs font-medium uppercase tracking-wide text-ink-gray-5"
        >
          <Icon
            :name="folded(index, section) ? 'lucide-chevron-right' : 'lucide-chevron-down'"
            class="size-3.5"
            :aria-hidden="true"
          />
          {{ section.label }}
        </span>
      </Button>
      <h3
        v-else-if="section.label"
        class="text-p-xs font-medium uppercase tracking-wide text-ink-gray-5"
      >
        {{ section.label }}
      </h3>

      <!--
        The doctype's own columns, side by side where there is room for them
        and stacked where there is not. A Column Break is the third of Frappe's
        three layout fields and used to be dropped, so a doctype whose author
        put four fields in two columns got one tall column of four.

        `sm:` and not the pane's own width: a record pane can be dragged
        narrower than the breakpoint, and a two-column form in 360px is two
        columns of hyphens. The breakpoint is the honest bound — below it there
        is no room for columns at any pane width.
      -->
      <!-- `v-show` for the same reason the fields use it: a folded section
           still holds values, and unmounting it would drop what was typed
           there the moment somebody folded it. -->
      <div
        v-show="!folded(index, section)"
        class="grid gap-x-8 gap-y-6"
        :class="GRID[Math.min(section.columns.length, 3)]"
      >
        <!--
          `min-w-0` because a grid item's minimum width is `auto`, which is its
          content's minimum — so one wide thing inside a form column makes the
          whole column that wide and the form runs off the side of the pane.
          The child table is the thing: a five-column grid is 1200px, and
          without this it pushed the section, the tab and the pane's own
          scroller out with it instead of scrolling inside its own box.
        -->
        <div
          v-for="(column, at) in section.columns"
          :key="at"
          class="flex min-w-0 flex-col gap-6"
        >
          <!--
            The field's own icon, in a gutter beside the control rather than
            inside its label. Only some of frappe-ui's controls have a `label`
            slot — DatePicker and Duration do not — so putting it there would
            give most fields an icon and silently drop the label from the rest.
            A gutter is uniform, and the control keeps its own label/for pair.
          -->
          <!--
            `v-show`, not `v-if`: a field the doctype hides by rule is still a
            field this record has a value for, and unmounting the control drops
            what was typed into it the moment the rule flips. The desk keeps it
            mounted too.
          -->
          <!--
            What the doctype's author wrote between the fields. A Heading is a
            subtitle over the next few; an HTML block is usually the sentence
            explaining why they are being asked for. Both were dropped until
            now — they are layout fields, and the form only kept what it could
            find a column for — so a form was missing exactly the annotations
            its author added to make it readable.
          -->
          <template v-for="field in column" :key="field.fieldname">
            <h4
              v-if="field.note === 'heading'"
              v-show="!rules(field).hidden"
              data-slot="form-heading"
              class="text-p-base font-medium text-ink-gray-8"
            >
              {{ field.label }}
            </h4>
            <!--
              Sanitised before it is drawn. It comes from a doctype definition
              rather than from a customer, and "trusted because of where it
              came from" is the sentence before every stored-XSS write-up. The
              reader already carries DOMPurify for mail.
            -->
            <!-- eslint-disable vue/no-v-html -->
            <div
              v-else-if="field.note === 'html'"
              v-show="!rules(field).hidden"
              data-slot="form-html"
              class="text-p-sm text-ink-gray-6 [&_a]:underline [&_p]:mb-2"
              v-html="safe(field.html)"
            />
            <!-- eslint-enable vue/no-v-html -->
            <div
              v-else
              v-show="!rules(field).hidden"
              class="flex gap-2"
            >
            <!--
              No icon gutter here any more. The field's type icon goes inside
              its label — see FieldLabel — because a gutter is a column: it
              aligned the icon to the *control* rather than to the label, and
              it indented every label and every input in the form past the
              section heading, leaving a ragged empty channel down the side.
            -->
            <FieldControl
              :model-value="values[field.fieldname]"
              @update:model-value="wrote(field, $event)"
              @reload="emit('reload')"
              :field="shaped(field)"
              :space-code="spaceCode"
              :screen="screen"
              :is-new="isNew"
              :states="states"
              :doctype="doctype"
              :docname="docname || values.name || ''"
              :doc="values"
              :disabled="
                disabled ||
                !field.editable ||
                locked(field) ||
                frozen(field) ||
                rules(field).readOnly
              "
              class="min-w-0 flex-1"
            />
            <!--
              What the doctype has to say about the field that does not belong
              under it. `show_description_on_click` is Frappe saying the
              description is too long to print, and `documentation_url` is a
              link somebody wrote for exactly this moment.

              Here rather than inside FieldControl because only some of
              frappe-ui's controls take a `description`, and none of them takes
              a tooltip — the guard says so. This row already has a gutter and
              owns the field's layout, so the affordance belongs on it.
            -->
            <Tooltip
              v-if="field.show_description_on_click && field.description"
              :text="field.description"
            >
              <Icon
                name="lucide-info"
                class="mt-5 size-3.5 shrink-0 text-ink-gray-4"
                role="img"
                aria-label="About this field"
              />
            </Tooltip>
            <a
              v-if="field.documentation_url"
              :href="field.documentation_url"
              target="_blank"
              rel="noopener noreferrer"
              class="mt-5 shrink-0 text-ink-gray-4 hover:text-ink-gray-6"
              aria-label="Documentation for this field"
            >
              <Icon name="lucide-circle-help" class="size-3.5" :aria-hidden="true" />
            </a>
            </div>
          </template>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import DOMPurify from 'dompurify'
import { Button, Icon, Tooltip } from '@/ui'
import FieldControl from '../fields/FieldControl.vue'
import { fieldRules, sectionCollapsed } from '../../../lib/rules'
import { workspace } from '../../../lib/workspace'

// Indexed by how many columns the section has, because Tailwind needs the
// class name in the source to emit it — `grid-cols-${n}` is a string that
// produces no CSS. Four columns or more is three: past that a form column is
// narrower than the words in it, and Frappe's own forms stop at three too.
const GRID = ['', '', 'sm:grid-cols-2', 'sm:grid-cols-3']

const props = defineProps({
  sections: { type: Array, default: () => [] },
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  disabled: { type: Boolean, default: false },
  isNew: { type: Boolean, default: false },
  /** What the record is, for the fields that attach files to it. */
  doctype: { type: String, default: '' },
  /** Its id. Not `values.name` — the draft holds docfields, and `name` is not
      one of them. */
  docname: { type: String, default: '' },
  /** The doctype's Document States, so a Select's options carry their glyph. */
  states: { type: Array, default: () => [] },
})

// The draft, written into per field. A model rather than a prop: the object is
// the caller's and every control edits one key of it, so passing it down as a
// prop and writing to it is the mutation eslint is right to refuse.
const emit = defineEmits(['reload'])

const values = defineModel('values', { type: Object, required: true })

/**
 * A field was written, and a Link may fill in others.
 *
 * `fetch_from` on a docfield is `<link fieldname>.<field on the target>`, and
 * Frappe applies it on save whatever wrote the record. So this changes no
 * outcome — only when you see it. Without it a form shows an empty Company box,
 * somebody types into it, and the save quietly replaces what they typed with
 * the value it was always going to use. The field's note said "From Customer"
 * and nothing filled it in.
 *
 * Best effort, deliberately. A failed lookup leaves the field as it was and the
 * save still fills it, which is exactly the behaviour that existed before this
 * function did — so there is nothing here worth interrupting somebody for.
 */
const wrote = async (field, next) => {
  values.value[field.fieldname] = next

  if (!['Link', 'Dynamic Link'].includes(field.fieldtype)) return
  if (!next) return

  let filled = {}
  try {
    filled = await workspace.fetched(props.spaceCode, props.screen, field.fieldname, next)
  } catch {
    return
  }

  for (const [name, spec] of Object.entries(filled || {})) {
    // Frappe's own rule, and the difference between a convenience and a form
    // that argues with you: `fetch_if_empty` fills a blank and leaves anything
    // else alone. Without it, choosing a customer would overwrite the company
    // name somebody had just corrected by hand.
    if (spec.only_if_empty && values.value[name]) continue
    values.value[name] = spec.value
  }
}

// `set_only_once` is the doctype saying a field is settled at creation. Only
// the record knows whether that has happened, so the flag travels on the field
// and the answer is made here.
const locked = (field) => !!field.set_only_once && !props.isNew

// A submitted record is editable only in the fields marked `allow_on_submit`,
// and a cancelled one is not editable at all — Frappe refuses the save either
// way, and a control that looks writable and is dropped is the worst of the
// three possible answers because it is the one that looks like it worked.
//
// The docstatus is on the record rather than on the field, which is why this
// reads the values rather than the spec — and why the record endpoint carries
// `docstatus` even though it is never a column.
const frozen = (field) => {
  const status = Number(values.value?.docstatus)
  if (status === 2) return true
  return status === 1 && !field.allow_on_submit
}

// The doctype's own rules, against the record as it stands right now — so a
// field appears the moment the field it depends on says so, rather than after
// a save. Read on every render because that is what "as it stands right now"
// means; the evaluator is a few dozen comparisons and the alternative is a
// watcher per field per rule.
const rules = (field) => fieldRules(field, values.value)

// An HTML block's markup, with anything that can run stripped out. The default
// profile: this is a paragraph of explanation, not a document, so nothing here
// wants an iframe or a form.
const safe = (html) => DOMPurify.sanitize(String(html || ''))

/**
 * Which sections this reader has opened or closed by hand.
 *
 * Keyed by index and holding only what was actually pressed, so the doctype's
 * own answer — `collapsible` and `collapsible_depends_on`, which can change as
 * the record is edited — stays in charge of every section nobody has touched.
 * Seeding this from the rule instead would freeze it at first render.
 */
const opened = ref({})

const folded = (index, section) =>
  index in opened.value ? !opened.value[index] : sectionCollapsed(section, values.value)

const toggle = (index) => {
  const sections = props.sections || []
  opened.value = {
    ...opened.value,
    [index]: folded(index, sections[index]),
  }
}

// A field the doctype makes required by rule is required, and its label says
// so the same way a `reqd` one does — the control reads `reqd`, so this is
// where the two answers become one.
const shaped = (field) => {
  const applied = rules(field)
  return applied.required === !!field.reqd ? field : { ...field, reqd: 1 }
}
</script>
