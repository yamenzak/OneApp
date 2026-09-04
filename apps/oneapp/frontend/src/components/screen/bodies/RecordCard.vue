<template>
  <!--
    One record, as a card. The hover card over a link, the card on a board and
    the card in a grid are the same thing: an identity, then the few fields
    worth reading without opening the record.

    Which few is not ours to choose — `in_preview` is a flag a doctype sets on
    its own fields, once, and every surface pointing at that doctype gets the
    same answer. That is what makes a board card good for free: a doctype whose
    author marked three fields worth previewing already described its card.

    Two shapes, and one of them has two layouts:

      * `panel` — a hover card. Labels in a narrow column of their own, because
        five stacked label/value pairs read as ten unrelated lines and the same
        five in two columns read as a record.
      * `tile` — a board or grid card. No labels: three bands — who it is, what
        it says, and how it is doing — separated by hairlines, which is what
        Frappe CRM's kanban card is and it is right. Values stack one per line
        rather than wrapping into a paragraph: a card of five values run
        together is a sentence nobody wrote, and a column of five is a record.
      * `tile` **with a cover** — a gallery card. The picture is not a band on
        the card, it *is* the card: everything else sits over it, the way every
        gallery of things with pictures has ever worked. See `cover`.
  -->

  <!--
    A gallery card: the picture, and what is on it.

    `aspect-square` on the content rather than a height on the card, because an
    aspect ratio is a preference and not a cage — a card whose caption runs to
    six fields grows taller instead of clipping them, and the picture, being
    absolutely placed, still covers whatever height that turns out to be.

    Three decisions, all of them about the fact that the surface here is
    somebody's photograph rather than a card:

      * **Dark, not light.** The caption sits in a gradient to black with white
        type on it, which is how every product that puts words on a picture
        does it — a white band across a photograph reads as chrome stuck on
        top, and the first version of this looked exactly like that.
      * **Nothing behind the top row.** Its three things are small, white and
        shadowed; a second band up there would frame the picture out of its own
        card.
      * **The fields are pills**, not the cells a list draws. A cell's ink and
        its chip belong to a light surface; over a photograph they are a grey
        nobody can read. The *text* is the same text — `lib/cells.js` answers
        that once for both — and a status keeps its colour by going solid,
        which is the one badge variant that reads on anything.
  -->
  <div v-if="!isPanel && cover" class="relative overflow-hidden rounded-6">
    <div
      data-slot="card-cover"
      class="absolute inset-0 flex items-center justify-center bg-black/70"
    >
      <img
        v-if="record.image"
        :src="record.image"
        :alt="plainText(record.label) || String(record.value || '')"
        class="size-full object-cover"
      />
      <!--
        No picture, and still a frame: the record's initial on the same square.
        Its siblings have pictures, and a gallery whose empty cards collapse to
        nothing jumps every time somebody uploads a photograph.
      -->
      <!--
        Dark, like every other card in this gallery. The chrome over a picture
        is white with a shadow; a light square under the same chrome is a card
        whose date and heart have vanished, which is what a grey one did.
      -->
      <span v-else class="text-4xl font-medium uppercase text-white/40">{{ initial }}</span>
    </div>

    <div class="relative flex aspect-square flex-col justify-between">
      <!--
        How the record is doing, along the top: when it last moved on the left,
        then how many have said something, who it is on, and whether this one
        is yours at the right. The same row the other tile ends with — one
        component, one set of rules about what a zero means and what the heart
        is called — in white.
      -->
      <div class="p-3">
        <RowMeta
          spread
          inverse
          :meta="meta || {}"
          :people="people"
          @like="emit('like')"
        />
      </div>

      <!--
        Who it is, and what it says, along the bottom — where a caption goes on
        a photograph, and out of the middle of the picture.
      -->
      <div class="bg-gradient-to-t from-black/80 via-black/50 to-transparent px-3 pb-3 pt-10">
        <!--
          The caption is the control: two lines of type over a photograph.
          `Button` would bring its own padding, height and label layout to a
          thing that is none of those. See the row in NotificationList for the
          same exception and the same reason.
        -->
        <!-- eslint-disable-next-line vue/no-restricted-html-elements -->
        <button
          type="button"
          class="block w-full min-w-0 text-left"
          @click.stop="emit('open')"
        >
          <!-- The name, and the id under it where the name is not already the
               id. A record that has no title of its own is named by its id, and
               printing that twice is not more informative than once. -->
          <span class="block truncate text-p-base font-semibold text-white">
            {{ plainText(record.label) || record.value }}
          </span>
          <span v-if="subtitle" class="block truncate text-p-xs text-white/70">
            {{ subtitle }}
          </span>
        </button>

        <div v-if="fields.length" class="mt-2 flex flex-wrap items-center gap-1.5">
          <template v-for="field in fields" :key="field.fieldname">
            <!-- A status keeps the doctype's own colour. Solid rather than
                 subtle, because a pastel badge on a photograph is a smudge. -->
            <Badge
              v-if="field.cell === 'badge'"
              :theme="valueTheme(field.value, states)"
              :label="String(field.value)"
              variant="solid"
            >
              <template #prefix>
                <Icon
                  :name="valueIcon(field.value, states)"
                  class="size-3"
                  :aria-hidden="true"
                />
              </template>
            </Badge>
            <span
              v-else
              class="max-w-full truncate rounded-full bg-white/20 px-2 py-0.5 text-p-xs text-white backdrop-blur-sm"
            >
              {{ cellText(field, field.value, formats, links[field.fieldname]) }}
            </span>
          </template>
        </div>
      </div>
    </div>
  </div>

  <div v-else :class="frame">
    <!--
      Panel: not a control. Nothing on a hover card is pressable — it is what
      appears *because* you are already pointing at the link.
    -->
    <div v-if="isPanel" class="p-3">
      <RecordChip :record="record" />
    </div>

    <!--
      Tile: the card's one keyboard target, and its accessible name. The card
      itself is a click surface — the whole tile opens the record, the same way
      a list row does — and a click surface is not reachable by keyboard, so the
      title is the real control. Exactly the arrangement the list already uses:
      the row is a div, the title inside it is a button.

      `.stop` because the tile's own handler would otherwise fire too and open
      the record twice.
    -->
    <!--
      Same exception, same reason: the record's identity — a face, a name and
      an id — is what you press, and it is a block rather than a label.
    -->
    <!-- eslint-disable-next-line vue/no-restricted-html-elements -->
    <button
      v-else
      type="button"
      class="flex min-w-0 text-left"
      @click.stop="emit('open')"
    >
      <RecordChip :record="record" />
    </button>

    <Divider v-if="isPanel && (loading || fields.length)" />

    <div v-if="isPanel" class="p-3">
      <LoadingText v-if="loading" text="Loading" />

      <!-- A hover card: labels beside values. -->
      <dl
        v-else-if="fields.length"
        class="grid grid-cols-[7rem_1fr] items-baseline gap-x-3 gap-y-2"
      >
        <template v-for="field in fields" :key="field.fieldname">
          <dt class="truncate text-p-sm text-ink-gray-5">{{ field.label }}</dt>
          <dd class="flex min-w-0 items-center">
            <FieldCell
              :column="field"
              :value="field.value"
              :states="states"
              :links="links"
            />
          </dd>
        </template>
      </dl>

      <span v-else class="text-p-sm text-ink-gray-5">Nothing else to show.</span>
    </div>

    <!-- A tile: one value per line, each truncated in its own row so a long
         one shortens itself rather than widening the card. -->
    <template v-else-if="fields.length">
      <Divider />
      <div class="flex flex-col gap-2">
        <div
          v-for="field in fields"
          :key="field.fieldname"
          class="flex min-w-0 items-center"
        >
          <FieldCell
            :column="field"
            :value="field.value"
            :states="states"
            :links="links"
            class="min-w-0"
          />
        </div>
      </div>
    </template>

    <!--
      How the record is doing: when it last moved, how many people have said
      something, who it is on, and whether this one is yours. The same four the
      list shows at the end of every row — they cost nothing to carry, they are
      already on the row, and a card that drops them is a card saying less than
      the list it came from for no reason.

      Only where the caller has them. A hover card is one record fetched on its
      own and has no row meta to show.
    -->
    <!--
      Tags, where the record has any. Above the meta band rather than among the
      fields: a tag is not a value of the record, it is what somebody called
      it — and on a card that is the one thing worth reading before the fields.

      Every card, not only where a Tags column was added: the tags are already
      on the row, and a board is not a place people go to configure columns.
    -->
    <div v-if="!isPanel && tags.length" class="flex flex-wrap items-center gap-1 px-3 pb-1">
      <Badge
        v-for="tag in tags"
        :key="tag"
        :label="tag"
        theme="gray"
        variant="subtle"
      />
    </div>

    <template v-if="!isPanel && meta">
      <Divider />
      <RowMeta spread :meta="meta" :people="people" @like="emit('like')" />
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Badge, Divider, Icon, LoadingText } from '@/ui'
import FieldCell from './FieldCell.vue'
import RecordChip from '../record/RecordChip.vue'
import RowMeta from './RowMeta.vue'
import { plainText } from '../../../lib/format'
import { cellText } from '../../../lib/cells'
import { valueIcon, valueTheme } from '../../../lib/fields'
import { session } from '../../../lib/session'

const props = defineProps({
  /** { value, label, id, image, description } — the shape the server returns. */
  record: { type: Object, required: true },
  /** `[{ fieldname, label, fieldtype, value, … }]`, already resolved. */
  fields: { type: Array, default: () => [] },
  /** The target doctype's Document States, so a status reads in its colour. */
  states: { type: Array, default: () => [] },
  /**
   * The row's resolved links, keyed by fieldname. A board card draws fields
   * straight off a list row, where a Link is an id and the label for it came
   * back beside it; a hover card's fields arrive already resolved and pass
   * nothing here.
   */
  links: { type: Object, default: () => ({}) },
  /** `row._meta` — when it moved, how many comments, whether it is liked. */
  meta: { type: Object, default: null },
  /** `row._assigned` — who it is on, already resolved to faces and names. */
  people: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  shape: { type: String, default: 'panel' },
  /**
   * Whether the record's picture is the subject of this card.
   *
   * The caller's answer, not this component's: it depends on the *screen*
   * rather than on the record. A grid over a doctype that declares an
   * `image_field` is a gallery and every card gets a cover, the ones with no
   * picture included — otherwise a page of contacts where two have photographs
   * is two tall cards among twenty short ones.
   */
  cover: { type: Boolean, default: false },
})

const emit = defineEmits(['open', 'like'])

// Computed rather than a ternary in the binding. `test_every_class_emits_css`
// reads the string literals out of a `:class` and checks each is a real
// utility, so `shape === 'panel' ? 'p-3' : ''` offered it `panel` and `tile` as
// class names and it rightly said neither emits any CSS.
const isPanel = computed(() => props.shape === 'panel')

// A card's tags come from the same `_meta.tags` the list's Tags column reads,
// so a record tagged twice is not tagged once here. See `spaceview._with_meta`.
const tags = computed(() => props.meta?.tags || [])

// `gap-2.5` is the rhythm the hairlines sit in: the same space above and below
// each one, which is what makes three bands read as three bands.
const frame = computed(() => (isPanel.value ? '' : 'flex flex-col gap-2.5 p-3'))

// What stands in for a picture where there is not one. The first letter of what
// the record is called, which is what Avatar itself falls back to — the same
// answer, drawn at the size a gallery asks for.
// The id, under the name, where the name is not already the id — the server
// blanks it in exactly that case, so this is only asking whether there is a
// second thing to say. A doctype with no `title_field` names its records by
// their id, and a card printing that twice says nothing the once did not.
const subtitle = computed(() => props.record.id || '')

// How this site renders a number when the field does not say, for the pills —
// the same answer `FieldCell` reads for the cells.
const formats = computed(() => session.data?.formats || {})

const initial = computed(
  () => (plainText(props.record.label) || String(props.record.value || '')).trim().charAt(0),
)
</script>
