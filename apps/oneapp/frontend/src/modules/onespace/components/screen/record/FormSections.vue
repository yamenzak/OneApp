<template>
  <!--
    Spacing, which on a form is not decoration.

    A doctype like Project has fifty-odd fields in three or four sections, and
    at `gap-4` between fields and `gap-5` between sections nothing said where
    one group ended. The steps are separated rather than merely present: 24px
    between fields, 40px between sections, and the rule that starts a section
    sits 40px off the one above.
  -->
  <div class="flex flex-col gap-10">
    <section
      v-for="(section, index) in sections"
      :key="index"
      class="flex flex-col gap-5"
      :class="index && !section.hide_border ? 'border-t border-outline-gray-1 pt-10' : ''"
    >
      <!-- A heading only where the doctype wrote one: Frappe's own forms leave
           the first section unlabelled more often than not.

           A collapsible section gets the same heading as a button, because a
           separate chevron beside it is a second target for one action. -->
      <Button
        v-if="section.label && section.collapsible"
        variant="ghost"
        size="sm"
        class="-ms-2 self-start"
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
        The doctype's own columns, side by side where there is room and stacked
        where there is not. `sm:` and not the pane's own width: a pane can be
        dragged narrower than the breakpoint, and below it there is no room for
        columns at any pane width.
      -->
      <!-- `v-show` for the same reason the fields use it: a folded section
           still holds values. -->
      <div
        v-show="!folded(index, section)"
        class="grid gap-x-8 gap-y-6"
        :class="GRID[Math.min(section.columns.length, 3)]"
      >
        <!--
          `min-w-0` because a grid item's minimum width is `auto`, which is its
          content's minimum — so one wide thing inside a form column makes the
          whole column that wide. A five-column child grid is 1200px, and
          without this it pushed the pane's own scroller out with it.
        -->
        <div
          v-for="(column, at) in section.columns"
          :key="at"
          class="flex min-w-0 flex-col gap-6"
        >
          <!--
            The field's own icon, in a gutter beside the control rather than
            inside its label: only some of frappe-ui's controls have a `label`
            slot, so putting it there would silently drop the label from the
            rest.
          -->
          <!--
            `v-show`, not `v-if`: a field the doctype hides by rule is still a
            field this record has a value for, and unmounting the control drops
            what was typed the moment the rule flips. The desk keeps it mounted
            too.
          -->
          <!--
            What the doctype's author wrote between the fields: a Heading is a
            subtitle over the next few, an HTML block the sentence explaining
            why they are being asked for.
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
              rather than from a customer, and "trusted because of where it came
              from" is the sentence before every stored-XSS write-up.
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
              No icon gutter here. The field's type icon goes inside its label —
              see FieldLabel — because a gutter is a column: it aligned the icon
              to the *control* and indented every label past the section
              heading.
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
              :ai="ai[field.fieldname] || null"
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
              under it: `show_description_on_click` is Frappe saying the
              description is too long to print, `documentation_url` a link
              somebody wrote for this moment.

              Here rather than inside FieldControl because only some frappe-ui
              controls take a `description` and none takes a tooltip.
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
import { computed, onBeforeUnmount, ref } from 'vue'
import DOMPurify from 'dompurify'
import { Button, Icon, Tooltip } from '@/ui'
import FieldControl from '@/modules/onespace/components/screen/fields/FieldControl.vue'
import { fieldRules, sectionCollapsed } from '@/modules/onespace/lib/screen/rules'
import { workspace } from '@/shared/lib/workspace'

// Indexed by how many columns the section has, because Tailwind needs the class
// name in the source to emit it. Four or more is three: past that a form column
// is narrower than the words in it, and Frappe's own forms stop at three.
const GRID = ['', '', 'md:grid-cols-2', 'md:grid-cols-3']

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
  /** The record's `_ai`: fieldname → what wrote the value there. Absent on a
   *  record nothing wrote, which is nearly all of them. */
  ai: { type: Object, default: () => ({}) },
})

// The draft, written into per field. A model rather than a prop: the object is
// the caller's and every control edits one key of it.
const emit = defineEmits(['reload'])

const values = defineModel('values', { type: Object, required: true })

/**
 * A field was written, and a Link may fill in others.
 *
 * `fetch_from` is `<link fieldname>.<field on the target>`, and Frappe applies
 * it on save whatever wrote the record — so this changes no outcome, only when
 * you see it. Without it a form shows an empty Company box, somebody types into
 * it, and the save quietly replaces what they typed.
 *
 * Best effort: a failed lookup leaves the field as it was and the save still
 * fills it.
 */
const wrote = async (field, next) => {
  values.value[field.fieldname] = next
  derive()

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
    // else alone.
    if (spec.only_if_empty && values.value[name]) continue
    values.value[name] = spec.value
  }
  // Again, because what a Link filled in is usually what the arithmetic runs
  // on: choosing an item fills its rate, and the amount follows the rate.
  derive()
}

// Long enough that typing a quantity sends one request rather than three,
// short enough that the total lands while you are still looking at the line.
const DERIVE_PAUSE = 400

/**
 * Whether this doctype computes anything worth asking about.
 *
 * A form of eight Data fields derives nothing, and asking after every pause on
 * every screen in the product would be a request per pause to be told so. A
 * child table is the case that matters and the case the arithmetic lives in: a
 * line is width × height × qty × rate and the total under it is the sum.
 */
const derives = computed(() =>
  (props.sections || []).some((section) =>
    // A column *is* its list of fields — see the `v-for` above.
    (section.columns || []).some((column) =>
      (column || []).some((f) => f.fieldtype === 'Table' && f.child?.editable),
    ),
  ),
)

let waiting = null

/**
 * Ask the server what the document makes of what has been typed.
 *
 * The arithmetic is the doctype's own — ERPNext works a line out in its
 * controller, and its rounding is not something to have a second opinion
 * about in JavaScript — so the values go up, `validate` runs over a document
 * built in memory, and what came back different is patched in. Nothing is
 * saved; `spaceview/run.derive` rolls its savepoint back either way.
 *
 * Silent when it fails or answers nothing. A document half typed is not
 * valid yet and has no totals to give, which is not an error and not
 * something to say out loud — the save is where somebody is told.
 */
const derive = () => {
  if (!derives.value || props.disabled) return
  window.clearTimeout(waiting)
  waiting = window.setTimeout(async () => {
    let answered
    try {
      answered = await workspace.deriveRecord(
        props.spaceCode, props.screen, values.value, props.docname,
      )
    } catch {
      return
    }

    for (const [name, value] of Object.entries(answered?.values || {})) {
      values.value[name] = value
    }

    for (const [table, rows] of Object.entries(answered?.children || {})) {
      const held = values.value[table]
      if (!Array.isArray(held)) continue
      // Lined up on `idx` rather than on position: the controller may have
      // renumbered or reordered the rows, and patching by position would put
      // one line's amount on another.
      const byIdx = new Map(rows.map((one) => [one.idx, one]))
      values.value[table] = held.map((row, at) => {
        const moved = { ...(byIdx.get(row.idx ?? at + 1) || {}) }
        // `idx` came back so the rows could be lined up, not to be written.
        delete moved.idx
        return Object.keys(moved).length ? { ...row, ...moved } : row
      })
    }
  }, DERIVE_PAUSE)
}

onBeforeUnmount(() => window.clearTimeout(waiting))

// `set_only_once` is the doctype saying a field is settled at creation. Only
// the record knows whether that has happened, so the flag travels on the field
// and the answer is made here.
const locked = (field) => !!field.set_only_once && !props.isNew

// A submitted record is editable only in the fields marked `allow_on_submit`,
// and a cancelled one not at all. The docstatus is on the record rather than on
// the field, which is why this reads the values rather than the spec.
const frozen = (field) => {
  const status = Number(values.value?.docstatus)
  if (status === 2) return true
  return status === 1 && !field.allow_on_submit
}

// The doctype's own rules, against the record as it stands right now — so a
// field appears the moment the field it depends on says so. Read on every
// render, which is what "right now" means; the alternative is a watcher per
// field per rule.
const rules = (field) => fieldRules(field, values.value)

// An HTML block's markup, with anything that can run stripped out. The default
// profile: this is a paragraph of explanation, not a document.
const safe = (html) => DOMPurify.sanitize(String(html || ''))

/**
 * Which sections this reader has opened or closed by hand.
 *
 * Holding only what was actually pressed, so the doctype's own
 * `collapsible_depends_on` — which can change as the record is edited — stays
 * in charge of every section nobody has touched.
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

// A field the doctype makes required by rule is required, and its label says so
// the same way a `reqd` one does.
const shaped = (field) => {
  const applied = rules(field)
  return applied.required === !!field.reqd ? field : { ...field, reqd: 1 }
}
</script>
