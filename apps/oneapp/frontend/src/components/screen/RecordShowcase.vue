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
    -->
    <div class="relative flex h-64 flex-col justify-end gap-3 p-4 sm:h-80 sm:p-6">
      <span
        v-if="eyebrow"
        data-slot="showcase-eyebrow"
        class="truncate text-p-xs uppercase tracking-widest text-white/70"
      >
        {{ eyebrow }}
      </span>

      <!--
        The name, at a size a photograph can carry. `text-wrap: balance` so a
        two-line title breaks somewhere a person would break it rather than
        leaving one word alone on the second line.
      -->
      <h1
        data-slot="showcase-title"
        dir="auto"
        class="max-w-3xl text-balance text-2xl font-semibold leading-tight text-white sm:text-4xl"
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

      <!--
        Which photograph, and a way to pick one. Dots rather than arrows: there
        are two or three of these, not twenty, and an arrow implies a sequence
        that matters.

        Inside the words rather than at the foot of the section, which is now
        the bottom of a row of cards — the dots belong to the picture.
      -->
      <div
        v-if="images.length > 1"
        class="absolute bottom-4 right-4 flex items-center gap-1.5 sm:bottom-6 sm:right-6"
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
    </div>

    <!--
      What hangs off this record. A row of cards that scrolls sideways, which
      is the shape because there are three of these on one job and eleven on
      another and neither should change the height of the page.

      Over the photograph rather than under it, the way a streaming service
      puts its rows over the artwork: the hero is the top of the page, not a
      banner with a page after it. `relative` so it sits above the artwork
      layer, which runs behind it to the bottom edge of the section.
    -->
    <div
      v-if="children.length"
      data-slot="showcase-children"
      class="relative px-4 pb-4 sm:px-6"
    >
      <div class="mb-2 flex items-center gap-2 pt-4">
        <Icon v-if="childIcon" :name="childIcon" class="size-4 text-white/70" />
        <span class="text-p-sm font-medium text-white/70">{{ childLabel }}</span>
        <span class="text-p-sm text-white/40">{{ children.length }}</span>
      </div>
      <!--
        A plain sideways scroller, not `FadedScroll`. Its horizontal edge is a
        hairline in `outline-gray-2`, which over a photograph is a pale line
        drawn down the middle of somebody's building.
      -->
      <div class="-mx-1 overflow-x-auto overscroll-x-contain">
        <div class="flex gap-2 px-1 pb-1">
          <!--
            The card is the control. `Button` would bring its own height,
            padding and label layout to a thing that is a picture with two
            lines under it — the same exception, and the same reason, as the
            caption on a gallery card.
          -->
          <!-- eslint-disable-next-line vue/no-restricted-html-elements -->
          <button
            v-for="one in children"
            :key="one.name"
            type="button"
            data-slot="showcase-child"
            class="flex w-40 shrink-0 flex-col gap-2 rounded-6 border border-white/10 bg-white/5 p-2 text-left transition-colors hover:bg-white/10 sm:w-48"
            @click="emit('open', { screen: childScreen, name: one.name })"
          >
            <div class="flex aspect-video items-center justify-center overflow-hidden rounded-4 bg-gradient-to-br from-white/10 to-white/0">
              <img
                v-if="one.image"
                :src="one.image"
                :alt="one.label"
                class="size-full object-cover"
              />
              <span v-else class="text-2xl font-medium uppercase text-white/40">
                {{ one.label.slice(0, 1) }}
              </span>
            </div>
            <span dir="auto" class="truncate text-p-sm font-medium text-white">
              {{ one.label }}
            </span>
            <span class="truncate text-p-xs text-white/50">{{ one.detail || one.name }}</span>
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { Icon } from '@/ui'
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
})

const emit = defineEmits(['open'])

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

/** The photographs, and what hangs off this record. */
const load = async () => {
  images.value = []
  children.value = []
  shown.value = 0
  if (!props.record?.name) return

  // Newest last, so a job reads in the order it was built rather than in the
  // order somebody uploaded the folder.
  if (props.showcase?.images) {
    const found = await workspace.attachments(props.spaceCode, props.screen, props.record.name)
    images.value = (found?.files || [])
      .filter((one) => /\.(png|jpe?g|webp|gif|avif)$/i.test(one.file_name || ''))
      .slice(0, MOST)
      .reverse()
  }

  const asked = props.showcase?.children
  if (!asked?.screen || !asked?.field) return

  // The ordinary list endpoint with a narrowing filter. Which is the whole
  // point of declaring this as a screen and a field rather than as a query:
  // the space, the permissions and the filter are checked where every other
  // list checks them.
  //
  // The other screen's spec beside it, because a card here says what a row of
  // *that* screen says — its title field and its picture. Reading them off this
  // screen's spec is right only while a record's children are the same doctype
  // as the record, which is true of a variation order and of nothing else.
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
  () => load(),
  { immediate: true },
)

onBeforeUnmount(() => clearInterval(turning))
</script>
