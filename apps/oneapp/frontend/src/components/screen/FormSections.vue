<template>
  <div class="flex flex-col gap-5">
    <section
      v-for="(section, index) in sections"
      :key="index"
      class="flex flex-col gap-4"
      :class="index && !section.hide_border ? 'border-t border-outline-gray-1 pt-5' : ''"
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
        class="grid gap-x-4 gap-y-4"
        :class="GRID[Math.min(section.columns.length, 3)]"
      >
        <div v-for="(column, at) in section.columns" :key="at" class="flex flex-col gap-4">
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
          <div
            v-for="field in column"
            v-show="!rules(field).hidden"
            :key="field.fieldname"
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
              :field="shaped(field)"
              :space-code="spaceCode"
              :screen="screen"
              :is-new="isNew"
              :states="states"
              :doctype="doctype"
              :docname="values.name || ''"
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
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Button, Icon, Tooltip } from '@/ui'
import FieldControl from './FieldControl.vue'
import { fieldRules, sectionCollapsed } from '../../lib/rules'
import { workspace } from '../../lib/workspace'

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
  /** The doctype's Document States, so a Select's options carry their glyph. */
  states: { type: Array, default: () => [] },
})

// The draft, written into per field. A model rather than a prop: the object is
// the caller's and every control edits one key of it, so passing it down as a
// prop and writing to it is the mutation eslint is right to refuse.
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

// A submitted record is editable only in the fields marked `allow_on_submit`.
// The docstatus is on the record rather than on the field, which is why this
// reads the values rather than the spec — and why the record endpoint carries
// `docstatus` even though it is never a column. Without it a submitted record
// offers every field and has every save refused, which is the worst of the
// three possible answers because it looks like it worked.
const frozen = (field) => Number(values.value?.docstatus) === 1 && !field.allow_on_submit

// The doctype's own rules, against the record as it stands right now — so a
// field appears the moment the field it depends on says so, rather than after
// a save. Read on every render because that is what "as it stands right now"
// means; the evaluator is a few dozen comparisons and the alternative is a
// watcher per field per rule.
const rules = (field) => fieldRules(field, values.value)

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
