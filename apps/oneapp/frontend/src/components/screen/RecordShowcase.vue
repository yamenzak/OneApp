<template>
  <!--
    The top of a record that is a place rather than a form.

    A project is a building, a contract value, a percentage done and the
    variation orders hanging off it. Rendering that as a column of labelled
    inputs is technically a record page and practically a filing cabinet — so
    where a screen declares a showcase, this is what opening one looks like.

    Nothing here is about construction. The manifest says which field is the
    eyebrow, which is the badge, which three numbers matter and what hangs off
    this record; a customer, a property or a case would declare the same shape
    and get the same page. See `oneapp_core/showcase.py`.

    Black and white here rather than the grey tokens, and it is the one place in
    the product that is right: the surface is somebody's photograph, which is
    the same colour in both themes, and `surface-gray-7` inverts between them —
    a dark ground in one and a pale band in the other. The gallery card over a
    photograph made the same call for the same reason.
  -->
  <section
    data-slot="showcase"
    class="relative -mx-4 -mt-4 mb-4 overflow-hidden bg-black"
  >
    <!--
      The photographs, one at a time, crossfading, behind the whole of this.

      Absolutely placed against the section rather than against a band at the
      top of it, which is the difference between a hero and a banner: the
      artwork runs the full height and the row of cards sits *on* it, fading
      into black at the bottom the way every streaming service does it. It was
      a fixed-height strip with a black panel under it, and the seam showed.

      Stacked and crossfaded rather than swapping one <img>'s `src`, because
      swapping flashes white between two large images — and a hero that blinks
      every six seconds is worse than one that does not move.
    -->
    <div class="absolute inset-0">
      <img
        v-for="(image, at) in images"
        :key="image.file_url"
        :src="image.file_url"
        :alt="image.file_name"
        data-slot="showcase-image"
        class="absolute inset-0 size-full object-cover transition-opacity duration-1000"
        :class="at === shown ? 'opacity-100' : 'opacity-0'"
      />

      <!-- Nothing filed against it yet. The gradient alone, which reads as a
           deliberate cover rather than as a picture that failed to load. -->
      <div
        v-if="!images.length"
        class="absolute inset-0 bg-gradient-to-br from-white/10 to-white/0"
      />

      <!--
        The scrim, and it is one gradient over the whole section rather than one
        per band. Two of them met at the boundary between the words and the
        cards, and a lighter wash starting directly under a darker one is a seam
        across somebody's building.

        The stops are placed rather than left at thirds, and that is the whole
        of the tuning: solid black through the bottom quarter, where the cards
        are and where a card row wants a ground, easing to nothing by the top,
        where the photograph is meant to be a photograph. Left at thirds it was
        a even wash — half the building dimmed and the cards still floating
        over a lit facade.

        Plus a horizontal one, so the left edge stays legible over a bright sky.
      -->
      <div class="absolute inset-0 bg-gradient-to-t from-black from-25% via-black/45 via-60% to-transparent" />
      <div class="absolute inset-0 bg-gradient-to-r from-black/70 to-transparent" />
    </div>

    <!--
      And everything that is read, in normal flow over it — so the section is
      as tall as its content and the artwork follows, rather than the content
      being pinned inside a height somebody picked.

      Two columns on a desktop: the name on the left with the whole left side to
      itself, and what hangs off this record standing up the right. It was one
      column with the cards in a row underneath, and the row pushed the name up
      into the middle of the picture — the title of the thing you opened had the
      least room of anything on the page. Bottom-aligned, both of them, because
      that is where a caption sits on a photograph.

      One column below `sm`, and the rail keeps its shape rather than turning
      back into a row: two layouts is two things to keep right, and a phone
      scrolls down anyway.
    -->
    <div
      class="relative flex flex-col gap-6 p-4 sm:flex-row sm:items-end sm:gap-10 sm:p-6"
      :class="compact ? 'min-h-48' : 'min-h-64 sm:min-h-96'"
    >
      <div class="flex min-w-0 flex-1 flex-col justify-end gap-3">
        <span
          v-if="eyebrow"
          data-slot="showcase-eyebrow"
          class="truncate text-p-xs uppercase tracking-widest text-white/70"
        >
          {{ eyebrow }}
        </span>

        <!--
          The name, in the one face in this product that is not the interface
          face, and in capitals with a little tracking — which is what a title
          card is, and what the interface face at 36px is not. See the
          `@font-face` rules in `src/index.css` for the two files behind it.

          No weight class: the face has one weight and asking for semibold gets
          a browser-synthesised bold, which on a heavy condensed grotesque is a
          smear. `text-wrap: balance` so a two-line name breaks where a person
          would break it rather than leaving one word alone on the second line,
          and bigger than the interface face would be set: a condensed face at
          36px reads smaller than the UI face at 36px, so matching the number
          matches nothing.

          `uppercase` is safe on every script here: Arabic has no case, so a
          bilingual title is capitalised in the half that has capitals.
        -->
        <h1
          data-slot="showcase-title"
          dir="auto"
          class="text-balance font-display uppercase leading-none tracking-wide text-white"
          :class="compact ? 'text-3xl' : 'text-3xl sm:text-5xl'"
        >
          {{ title }}
        </h1>

        <div class="flex flex-wrap items-center gap-x-6 gap-y-2">
          <StateBadge v-if="badge" :label="badge" :states="states" />
          <!--
            The two or three numbers somebody opens the record to read, drawn
            by the same formatter every list cell uses — so a contract value
            reads the same here as it does in the column it came from.
          -->
          <div
            v-for="fact in facts"
            :key="fact.field"
            data-slot="showcase-fact"
            class="flex flex-col"
          >
            <span class="text-p-xs uppercase tracking-wide text-white/60">
              {{ fact.label }}
            </span>
            <span class="text-p-base font-medium tabular-nums text-white">
              {{ fact.text || '—' }}
            </span>
          </div>
        </div>
      </div>

      <!--
        Which photograph, and a way to pick one. Dots rather than arrows: there
        are two or three of these, not twenty, and an arrow implies a sequence
        that matters.

        The top right corner of the artwork, which is the one place on this
        section that is only ever the picture: the words are bottom left, the
        rail is bottom right — it is bottom-aligned and capped, so it cannot
        reach up here — and a control that belongs to the photograph should not
        sit inside either of them.

        On its own dark pill, because the corner it has been given is the one
        part of the section the scrim barely reaches: white dots at 40% over a
        bright sky are three smudges and a fourth you cannot find. The same
        answer the rail got, at the size this needs.
      -->
      <div
        v-if="images.length > 1"
        class="absolute right-4 top-4 z-10 flex items-center gap-1.5 rounded-full bg-black/40 px-2 py-1.5 backdrop-blur-sm sm:right-6 sm:top-6"
      >
        <!--
          An eight-pixel dot. `Button` is a control with a height, a padding
          and a label slot, and none of the three survives being shrunk to
          this — the same exception the gallery card's caption takes, for the
          same reason. It keeps the label: the dot says which photograph in the
          only way a two-pixel target can, which is to a screen reader.
        -->
        <!-- eslint-disable-next-line vue/no-restricted-html-elements -->
        <button
          v-for="(image, at) in images"
          :key="image.file_url"
          type="button"
          data-slot="showcase-dot"
          :aria-label="`Show ${image.file_name}`"
          class="size-2 rounded-full transition-colors"
          :class="at === shown ? 'bg-white' : 'bg-white/40'"
          @click="pick(at)"
        />
      </div>

      <!--
        What hangs off this record, standing up the right-hand side.

        One panel rather than a stack of floating rows. The scrim is weighted
        to the bottom of the section — that is where the words are — so the top
        of this column sits over an unscrimmed sky, and rows drawn as glass
        over that were four grey shapes with white text on them. A single dark
        panel gives the whole rail a ground wherever it lands on the picture.

        Rows rather than the poster cards this used to be: a column of six
        posters is a wall, and what somebody scanning a list of variation orders
        reads is the name and where it stands, not a thumbnail of a building
        they are already looking at. The monogram gives each row an anchor, and
        carries a picture on a screen whose records have one.

        Capped and scrolled rather than allowed to grow: three of these on one
        job and eleven on another, and neither should decide how tall the top of
        the page is.
      -->
      <div
        v-if="children.length && !compact"
        data-slot="showcase-children"
        class="flex w-full shrink-0 flex-col gap-2 rounded-6 bg-black/50 p-3 backdrop-blur-sm sm:w-80"
      >
        <div class="flex items-center gap-2">
          <Icon v-if="childIcon" :name="childIcon" class="size-4 text-white/70" />
          <span class="text-p-sm font-medium text-white/70">{{ childLabel }}</span>
          <span class="text-p-sm text-white/40">{{ children.length }}</span>
          <!--
            Add one. In the rail's own corner, because this is the only place in
            the product that knows which record a new one hangs off — the
            alternative is making it from the list and remembering to set the
            parent by hand, which is where every orphaned variation comes from.

            `Button` here rather than the bare element the cards use: it is a
            control of the ordinary size and shape, and the only thing unusual
            about it is that it is white on a dark panel.
          -->
          <Button
            v-if="canAddChild"
            class="ms-auto !text-white hover:!bg-white/15"
            data-slot="showcase-add-child"
            icon="lucide-plus"
            variant="ghost"
            :label="`Add a ${singularChild.toLowerCase()}`"
            :tooltip="`Add a ${singularChild.toLowerCase()}`"
            @click="emit('add', {
              screen: childScreen,
              field: showcase.children.field,
              value: record.name,
            })"
          />
        </div>

        <!--
          A plain scroller, not `FadedScroll`: its vertical edge is a wash from
          `surface-base`, which over a dark panel is a pale band rather than a
          fade. A half-row at the cut is the honest version of the same signal.
        -->
        <div class="-mx-1 max-h-56 overflow-y-auto overscroll-contain px-1">
          <div class="flex flex-col">
            <!--
              The row is the control. `Button` would bring its own height,
              padding and label layout to a thing that is a square and two
              lines of type — the same exception, and the same reason, as the
              caption on a gallery card.
            -->
            <!-- eslint-disable-next-line vue/no-restricted-html-elements -->
            <button
              v-for="one in children"
              :key="one.name"
              type="button"
              data-slot="showcase-child"
              :data-name="one.name"
              class="flex items-center gap-3 rounded-4 p-2 text-left transition-colors hover:bg-white/15"
              @click="emit('open', { screen: childScreen, name: one.name })"
            >
              <span
                class="flex size-9 shrink-0 items-center justify-center overflow-hidden rounded-4 bg-white/10"
              >
                <img
                  v-if="one.image"
                  :src="one.image"
                  :alt="one.label"
                  class="size-full object-cover"
                />
                <span v-else class="text-p-sm font-medium uppercase text-white/50">
                  {{ one.label.slice(0, 1) }}
                </span>
              </span>
              <span class="flex min-w-0 flex-col">
                <span dir="auto" class="truncate text-p-sm font-medium text-white">
                  {{ one.label }}
                </span>
                <span class="truncate text-p-xs text-white/50">
                  {{ one.detail || one.name }}
                </span>
              </span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { Button, Icon } from '@/ui'
import StateBadge from './StateBadge.vue'
import { cellText } from '../../lib/cells'
import { session } from '../../lib/session'
import { workspace } from '../../lib/workspace'

const props = defineProps({
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  /** The record, as the form holds it. */
  record: { type: Object, required: true },
  /** What the screen says about itself — columns, states, title field. */
  spec: { type: Object, default: () => ({}) },
  /** The declaration. See `oneapp_core/showcase.py`. */
  showcase: { type: Object, default: () => ({}) },
  title: { type: String, default: '' },
  /**
   * Whether this is the top of a page or the top of something opened over one.
   *
   * A hero is most of a screenful, and in a drawer that is most of the drawer —
   * so a peeked record gets the same page, shorter, with the rail left out. The
   * rail is what hangs off *this* record, and a reader one level down came here
   * from a list of exactly that.
   */
  compact: { type: Boolean, default: false },
  /**
   * Bumped by the host when something was added to the rail.
   *
   * The rail is a list this component fetched, and a record created into it
   * from outside is a row it has no other way to hear about.
   */
  revision: { type: Number, default: 0 },
})

const emit = defineEmits(['open', 'add'])

// How long one photograph holds before the next. Six seconds: long enough to
// look at a building, short enough that somebody waiting sees it change.
const HOLD = 6000

// Enough to know there is more than one, and few enough that the dots stay a
// row rather than a ruler.
const MOST = 8

// How many of the things hanging off this record the strip carries. A row of
// cards is a glance at what is there, not the list of it — and the tabs under
// the hero are where the list lives.
const KEPT = 24

const images = ref([])
const children = ref([])
// The child screen as it describes itself — its title field, its picture, and
// whether this person may add one. Null until the rail has loaded.
const childSpec = ref(null)
const shown = ref(0)
let turning = null

const columns = computed(() => props.spec?.all_columns || props.spec?.columns || [])
const states = computed(() => props.spec?.states || [])
const formats = computed(() => session.data?.formats || {})

const column = (fieldname) => columns.value.find((one) => one.fieldname === fieldname)

const eyebrow = computed(() => {
  const field = props.showcase?.eyebrow_field
  return field ? String(props.record?.[field] || '') : ''
})

const badge = computed(() => {
  const field = props.showcase?.badge_field
  return field ? String(props.record?.[field] || '') : ''
})

/**
 * The facts, formatted the way the same value is formatted in a list.
 *
 * Through `cellText` rather than printed raw: a contract value that reads
 * `1115646.0` in the hero and `1,115,646.00` in the column it came from is two
 * different numbers as far as anybody reading is concerned.
 */
const facts = computed(() =>
  (props.showcase?.facts || []).map((fact) => {
    const found = column(fact.field)
    return {
      field: fact.field,
      label: fact.label || found?.label || fact.field,
      text: found ? cellText(found, props.record?.[fact.field], formats.value) : '',
    }
  }),
)

const childLabel = computed(() => props.showcase?.children?.label || 'Related')
const childIcon = computed(() => props.showcase?.children?.icon || '')
const childScreen = computed(() => props.showcase?.children?.screen || props.screen)

// Whether this person may add one, as that screen answered it — not as this
// screen did. A reader who may open a job and not create one gets the rail and
// no plus, which is the same answer its own list would give them.
const canAddChild = computed(() => !!childSpec.value?.can_create)

// One of them, in the words the child screen uses. `singular` is the manifest's
// own answer where a screen gives one — "Variation" for a label of
// "Variations" — and the label with its s taken off where it does not, which is
// right far more often than it is wrong.
const singularChild = computed(
  () => childSpec.value?.singular || childLabel.value.replace(/s$/i, ''),
)

/** The photographs, and what hangs off this record. */
/**
 * The photographs. Keyed on which record this is and nothing else.
 *
 * Separate from the children below, and that separation is the point: adding a
 * variation reloads the rail, and if the two shared a loader it would blank the
 * hero and fetch the same three photographs again to do it.
 */
const loadImages = async () => {
  images.value = []
  shown.value = 0
  if (!props.record?.name || !props.showcase?.images) return

  // Newest last, so a job reads in the order it was built rather than in the
  // order somebody uploaded the folder.
  const found = await workspace.attachments(props.spaceCode, props.screen, props.record.name)
  images.value = (found?.files || [])
    .filter((one) => /\.(png|jpe?g|webp|gif|avif)$/i.test(one.file_name || ''))
    .slice(0, MOST)
    .reverse()
}

/** What hangs off this record, and what a row of it looks like. */
const loadChildren = async () => {
  children.value = []
  childSpec.value = null
  const asked = props.showcase?.children
  if (!props.record?.name || !asked?.screen || !asked?.field) return

  // The ordinary list endpoint with a narrowing filter. Which is the whole
  // point of declaring this as a screen and a field rather than as a query:
  // the space, the permissions and the filter are checked where every other
  // list checks them.
  //
  // The other screen's spec beside it, because a card here says what a row of
  // *that* screen says — its title field, its picture, and whether this person
  // may add one. Reading them off this screen's spec is right only while a
  // record's children are the same doctype as the record, which is true of a
  // variation order and of nothing else.
  const [spec, found] = await Promise.all([
    workspace.screenSpec(props.spaceCode, asked.screen),
    workspace.screenRows(
      props.spaceCode,
      asked.screen,
      { filters: [[asked.field, '=', props.record.name]] },
      '',
      { start: 0, limit: KEPT },
    ),
  ])

  childSpec.value = spec || null
  const rows = found?.rows || []
  const titleField = spec?.title_field || 'name'
  const imageField = spec?.image_field || ''
  // The first column that is not the name: on a variation that is its stage or
  // its value, which is what somebody scanning a row of cards is reading.
  const first = (found?.columns || []).find(
    (one) => one.fieldname !== titleField && one.fieldname !== '__activity',
  )
  children.value = rows.map((row) => ({
    name: row.name,
    label: String(row[titleField] || row.name),
    image: imageField ? row[imageField] || '' : '',
    detail: first ? cellText(first, row[first.fieldname], formats.value, row._links?.[first.fieldname]) : '',
  }))
}

const pick = (at) => {
  shown.value = at
  // Restarted rather than left running: a person who just chose a photograph
  // should get the full six seconds with it, not whatever was left.
  turn()
}

const turn = () => {
  clearInterval(turning)
  if (images.value.length < 2) return
  turning = setInterval(() => {
    shown.value = (shown.value + 1) % images.value.length
  }, HOLD)
}

watch(images, turn)
watch(
  () => [props.record?.name, props.showcase],
  () => {
    loadImages()
    loadChildren()
  },
  { immediate: true },
)

// And the rail on its own, when the host says something was added to it. A
// number rather than a signal, because "it changed" is all this needs to know
// and a number is the smallest thing that can say it.
watch(() => props.revision, loadChildren)

onBeforeUnmount(() => clearInterval(turning))
</script>
