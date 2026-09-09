<template>
  <!--
    The network, and one clock.

    The screen the whole product is for: every line drawn, every stop on it,
    and the fleet moving — live when the clock says now, and running through a
    past day when it does not. **One surface with two clocks**, deliberately:
    two would drift into two products, and the pitch is that they are the same
    view. See `apps/oneapp/oneapp/onemobility/README.md` §4.

    The escape hatch's first honest use. A map of a moving fleet with a time
    scrubber is not a way of looking at a list, so it is not a view type.
  -->
  <!--
    `h-full w-full`, not `absolute inset-0`: maplibre-gl.css declares
    `.maplibregl-map { position: relative }` at the same specificity as
    Tailwind's `.absolute` and is loaded after it, so the moment the library's
    stylesheet arrives the container stops being positioned, `inset-0` stops
    meaning anything, and the height collapses to zero — a map drawn into
    MapLibre's 400x300 fallback canvas with no error said anywhere.
  -->
  <div class="relative h-full min-h-[32rem] w-full overflow-hidden" data-slot="network">
    <div v-show="!failed" ref="canvas" class="h-full w-full" />

    <EmptyState
      v-if="failed"
      icon="lucide-map"
      :title="__('The map could not be drawn')"
      :description="__('Nothing on this screen depends on an outside service, so this is ours to fix.')"
    />
    <EmptyState
      v-else-if="ready && !lines.length"
      icon="lucide-route"
      :title="__('No network yet')"
      :description="__('Connect a source and load a timetable, and the lines appear here.')"
    />

    <template v-if="ready && lines.length">
      <!--
        The controls, as a rail under the zoom, and the key as a key. They were
        one card and it had become a control panel with a scrollbar in which the
        thing a reader wanted — what does this colour mean — was below the fold.
      -->
      <MapControls
        v-model:overlay="overlay"
        v-model:show-routes="showRoutes"
        v-model:show-stops="showStops"
        v-model:show-vehicles="showVehicles"
        :overlay-options="overlayOptions"
        :isolated="isolated"
        :styles="markerStyles"
        :may-style="mayStyle"
        :ground="mapPrefs"
        :grounds="mapStyles"
        @clear-isolate="isolate(null)"
        @style="restyle"
        @ground="reground"
      />

      <MapLegend
        :overlay="overlayNow"
        :ramp="scaleInks"
        :low="scaleLow"
        :high="scaleHigh"
        :drawn="shapesHere"
        :show-stops="showStops"
        :show-vehicles="showVehicles && !ahead"
        :isolated="isolated"
        :expected="expectedNote"
      />

      <!--
        One vehicle, opened. Its day is fetched and drawn behind it, which is
        the whole of "where has this thing been" and is a question a dispatcher
        asks before any other.
      -->
      <div
        v-if="chosen"
        class="pointer-events-auto absolute bottom-[11.5rem] end-4 z-10 w-64 rounded-6 border
               border-outline-gray-2 bg-surface-elevation-2 p-3 shadow-lg"
        data-slot="network-vehicle"
      >
        <div class="flex items-start gap-2">
          <span
            class="mt-0.5 inline-flex h-5 shrink-0 items-center rounded-4 px-1.5 text-xs font-semibold text-white"
            :style="{ backgroundColor: inkOfLine(chosen.line) }"
          >{{ shortNameOf(chosen.line) }}</span>
          <div class="min-w-0 flex-1">
            <p class="truncate text-sm font-medium text-ink-gray-8">
              <span v-if="emojiOfLine(chosen.line)">{{ emojiOfLine(chosen.line) }}</span>
              {{ chosen.vehicle }}
            </p>
            <p class="truncate text-xs text-ink-gray-5">{{ nameOfLine(chosen.line) }}</p>
          </div>
          <Button
            variant="ghost"
            icon="lucide-x"
            :label="__('Close')"
            :tooltip="__('Close')"
            @click="choose('')"
          />
        </div>

        <div class="mt-3 flex flex-col gap-1">
          <div class="flex items-baseline justify-between text-xs">
            <span class="text-ink-gray-5">{{ __('How full') }}</span>
            <span class="font-medium text-ink-gray-8">{{ occupancyOf(chosen) }}</span>
          </div>
          <!-- A bar rather than a number alone: a percentage of capacity is a
               proportion, and a proportion drawn is read faster than one read. -->
          <div class="h-1.5 w-full overflow-hidden rounded-full bg-surface-gray-2">
            <div
              class="h-full rounded-full"
              :style="{
                width: `${Math.max(0, Math.min(100, chosen.occupancy ?? 0))}%`,
                backgroundColor: occupancyInk(chosen.occupancy),
              }"
            />
          </div>
        </div>

        <div class="mt-3 grid grid-cols-2 gap-2">
          <div class="rounded-4 bg-surface-gray-1 p-2">
            <p class="text-xs text-ink-gray-5">{{ __('Against the timetable') }}</p>
            <p class="tabular-nums text-sm font-medium" :style="{ color: delayInk(chosen.delay_s) }">
              {{ delayLabel(chosen.delay_s) }}
            </p>
          </div>
          <div class="rounded-4 bg-surface-gray-1 p-2">
            <p class="text-xs text-ink-gray-5">{{ __('Last heard') }}</p>
            <p class="tabular-nums text-sm font-medium text-ink-gray-8">
              {{ chosen.stale ? __('Stale') : __('Just now') }}
            </p>
          </div>
        </div>

        <div class="mt-3 flex gap-2">
          <Button
            class="flex-1"
            :variant="following ? 'solid' : 'subtle'"
            :label="following ? __('Following') : __('Follow it')"
            icon-left="lucide-crosshair"
            @click="following = !following"
          />
          <!-- Following moves the *map*; this dims the network. Two different
               questions — where is it going, and which of these forty is it —
               and answering both with one button was the first version. -->
          <Button
            variant="subtle"
            icon="lucide-eye"
            :tooltip="__('Show this one alone')"
            :aria-label="__('Show this one alone')"
            @click="isolate({ kind: 'vehicle', name: chosen.vehicle, label: chosen.vehicle })"
          />
        </div>
      </div>

      <!--
        The clock. Past on the left, now on the right, one control — and a
        track that says where the day has service in it, so dragging is aimed
        rather than blind.
      -->
      <div
        class="pointer-events-auto absolute inset-x-4 bottom-4 z-10 flex flex-col gap-2 rounded-6 border border-outline-gray-2 bg-surface-elevation-2 px-3 py-2.5 shadow-lg"
        data-slot="network-clock"
      >
        <div class="flex flex-wrap items-center gap-2">
          <Button
            :variant="livemode ? 'solid' : 'subtle'"
            :label="__('Live')"
            icon-left="lucide-radio"
            @click="goLive"
          />
          <Button
            :variant="playing ? 'solid' : 'subtle'"
            :icon="playing ? 'lucide-pause' : 'lucide-play'"
            :label="playing ? __('Pause') : __('Play the day')"
            :tooltip="playing ? __('Pause') : __('Play the day')"
            :disabled="livemode"
            @click="togglePlay"
          />
          <Button
            variant="subtle"
            :label="`${speed}×`"
            :disabled="livemode"
            @click="cycleSpeed"
          />
          <Select
            v-model="day"
            :options="dayOptions"
            :placeholder="__('A day')"
            class="w-40"
          />
          <!--
            The same bar Insights carries, and the same server-side vocabulary
            behind it — see `FacetBar.vue`. The map used to take a line and
            Insights took a line separately, which is how one filter becomes
            two slightly different filters nobody notices disagreeing.
          -->
          <FacetBar
            v-model="facets"
            :facets="offered"
            :unavailable="unavailable"
          />

          <div class="ms-auto flex items-center gap-3">
            <!-- The fleet's occupancy mix, as one bar. Four seconds of glance
                 answers "is the network under pressure right now". The *bar*
                 folds away on a phone and the count does not: a hundred pixels
                 of stacked colour is the first thing to lose when there is no
                 room, and how many vehicles are out there is the last. -->
            <div class="hidden items-center sm:flex" data-slot="network-mix">
              <div class="flex h-2 w-24 overflow-hidden rounded-full bg-surface-gray-2">
                <div
                  v-for="part in mix"
                  :key="part.key"
                  class="h-full"
                  :style="{ width: `${part.share}%`, backgroundColor: part.ink }"
                  :title="`${part.label}: ${part.count}`"
                />
              </div>
            </div>
            <span class="tabular-nums text-xs text-ink-gray-5">
              {{ __('{0} vehicles', [String(drawn.length)]) }}
            </span>

            <div class="flex items-baseline gap-2">
              <span
                class="tabular-nums text-xl font-semibold leading-none text-ink-gray-9"
                data-slot="network-time"
              >{{ clockLabel }}</span>
              <Badge v-if="livemode" theme="green" :label="__('Live')" />
              <!-- Not the day, because the day is not what is being said. A
                   moment past now is a claim rather than a record, and the
                   badge is the only place on the clock that can say which. -->
              <Badge v-else-if="ahead" theme="amber" :label="__('Expected')" />
              <Badge v-else theme="blue" :label="dayLabel" />
            </div>
          </div>
        </div>

        <!--
          The track. An SVG of how much service each hour holds, the hour ruler
          under it, and the range input laid over the top — one control, three
          things said. `pointer-events-none` on the drawing so every press
          still lands on the input.
        -->
        <div class="relative h-10 w-full select-none" data-slot="network-track">
          <svg
            class="pointer-events-none absolute inset-x-0 top-0 h-7 w-full"
            :viewBox="`0 0 ${TRACK_W} 28`"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <rect
              v-for="bar in density"
              :key="bar.hour"
              :x="bar.x"
              :y="28 - bar.h"
              :width="bar.w"
              :height="bar.h"
              :rx="1.5"
              :fill="bar.past ? accent : muted"
              :opacity="bar.later ? 0.12 : bar.past ? 0.5 : 0.2"
            />
            <!--
              Where the present is, on a day that has one. The scrubber runs
              through it rather than stopping at it — that is the point of §7a —
              so the boundary has to be drawn or dragging past it is a silent
              change of what the map means.
            -->
            <line
              v-if="nowX !== null"
              :x1="nowX" :x2="nowX" y1="0" y2="28"
              :stroke="accent" stroke-width="1" stroke-dasharray="3 3" opacity="0.6"
            />
            <line
              :x1="handleX" :x2="handleX" y1="0" y2="28"
              :stroke="accent" stroke-width="2" stroke-linecap="round"
            />
            <circle :cx="handleX" cy="28" r="4" :fill="accent" />
          </svg>

          <!--
            The input is the whole strip and draws nothing: the bars above are
            the track and the line through them is the handle. A native range
            laid over its own painted background gives two tracks and two
            handles, which is one control pretending to be two.
          -->
          <!--
            A native range, deliberately. frappe-ui ships no slider, and the two
            things this control has to do are exactly what a native range does
            for free and a div does badly: drag with a pointer, and step with
            the arrow keys from a focus ring a screen reader announces.
            Everything visible is the SVG above; this is the input behind it.
          -->
          <!-- eslint-disable-next-line vue/no-restricted-html-elements -->
          <input
            v-model.number="position"
            type="range"
            min="0"
            max="1000"
            class="scrub absolute inset-x-0 top-0 h-7 w-full cursor-pointer appearance-none bg-transparent"
            :aria-label="__('Time of day')"
            :disabled="livemode"
            @input="onScrub"
          >

          <div class="pointer-events-none absolute inset-x-0 bottom-0 flex justify-between">
            <span
              v-for="tick in ticks"
              :key="tick"
              class="tabular-nums text-[10px] leading-none text-ink-gray-4"
            >{{ tick }}</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { Badge, Button, Select } from '@/ui'
import EmptyState from '@/shared/components/EmptyState.vue'
import { __ } from '@/shared/lib/runtime/translate'
import { network } from '@/modules/onemobility/lib/api'
import { basemap } from '@/shared/lib/runtime/boot'
import { settings } from '@/shared/lib/workspace/settings'
import FacetBar from '@/modules/onemobility/components/FacetBar.vue'
import MapControls from '@/modules/onemobility/components/MapControls.vue'
import MapLegend from '@/modules/onemobility/components/MapLegend.vue'
import {
  coarseFor,
  drawn as drawnArt,
  rasterise,
  FALLBACK as FALLBACK_SHAPE,
  SHAPES as ART_SHAPES,
} from '@/modules/onemobility/lib/art'
import { OVERLAYS, overlayFor } from '@/modules/onemobility/lib/layers'
import { paintSurface } from '@/modules/onemobility/lib/surface'
import { advance, at, blend, prepare, project } from '@/modules/onemobility/lib/motion'
import {
  bearingBetween,
  easeBearing,
  MODES,
  vehicleMarker,
} from '@/modules/onemobility/lib/markers'
import {
  bandInk,
  casingInk,
  delayInk,
  lineInk,
  occupancyBand,
  occupancyInk,
  OCCUPANCY,
} from '@/modules/onemobility/lib/palette'
import { tokenInk } from '@/modules/onespace/lib/screen/ink'
import {
  attribution,
  preferred,
  quietTiles,
  restyle as applyGround,
  styleFor,
  whenLoaded,
} from '@/modules/onespace/lib/screen/basemap'

defineProps({
  /** The resolved screen. Unused: this surface is not a list of records. */
  spec: { type: Object, default: () => ({}) },
})

/** How often the live clock asks the server where everything is. */
const LIVE_EVERY = 5000
/** Service day, in minutes, which is what the scrubber runs over. */
const DAY_START = 5 * 60
const DAY_END = 22 * 60
/** How often playback advances, and by how many service minutes at 1×. */
const PLAY_EVERY = 500
const PLAY_STEP = 5
const SPEEDS = [1, 4, 12]
/** The track's own coordinate space. Scaled to the element by the viewBox. */
const TRACK_W = 1000

const canvas = ref(null)
/**
 * The bitmap the analytical surface is painted into.
 *
 * Never in the document: MapLibre reads it as a texture, and putting it on the
 * page would be a second, differently-sized copy of the same thing for a reader
 * to be confused by.
 */
const field = document.createElement('canvas')
const ready = ref(false)
const failed = ref(false)
const lines = ref([])
const stops = ref([])
const days = ref([])
const day = ref('')
/**
 * What is narrowing the map. `onlyLine` is read out of it rather than kept
 * beside it: the line facet is the one the drawing itself reacts to — the rest
 * of the network dims around it — and two sources of truth for "which line" is
 * the bug this bar exists to remove.
 */
const facets = ref({})
const offered = ref([])
const unavailable = ref([])

/**
 * Which overlay is drawn, and which of the three base layers are on.
 *
 * The base layers default on because they are what the screen is; the overlay
 * defaults off because it is a question, and a map that opens already
 * answering one nobody asked is a map people have to undo before they can look.
 */
const overlay = ref('none')
const showRoutes = ref(true)
const showStops = ref(true)
const showVehicles = ref(true)

const overlayNow = computed(() => overlayFor(overlay.value))
const overlayOptions = computed(() =>
  OVERLAYS.map((one) => ({ label: one.label(), value: one.key })),
)

/** What the server said about the overlay in front: its cells, or its stops. */
const surfaceNow = ref({ cells: [], low: 0, high: 1, size: 0.001, quiet: 1, busy: 1 })
const demandNow = ref({ stops: [] })

const scaleInks = computed(() =>
  overlayNow.value.kind === 'surface'
    ? overlayNow.value.ramp()
    : [overlayNow.value.ink ? overlayNow.value.ink() : '#999999'],
)

/**
 * The ends of the key, in the unit a person reads.
 *
 * Rounded against the span rather than to a fixed place: "0.63 min" is a useful
 * end of a scale that runs to 2.47, and "36.41 %" is four characters of noise
 * on a scale that runs to 60. A legend is read at a glance and the digits past
 * the first are never the thing being glanced at.
 */
function reads(value, span) {
  const places = span >= 10 ? 0 : 1
  return Number(value || 0).toFixed(places)
}

const scaleLow = computed(() => {
  const one = overlayNow.value
  // `none` has no unit because it measures nothing. These used to be read only
  // inside a `v-if` that already knew that; they are props now, so they are
  // evaluated whether or not anything renders them.
  if (!one.unit) return ''
  const { low, high } = surfaceNow.value
  if (one.kind === 'surface') return `${reads(low, high - low)} ${one.unit()}`
  return `0 ${one.unit()}`
})
const scaleHigh = computed(() => {
  const one = overlayNow.value
  if (!one.unit) return ''
  const { low, high } = surfaceNow.value
  if (one.kind === 'surface') return `${reads(high, high - low)} ${one.unit()}`
  return `${pointHigh.value} ${one.unit()}`
})

/** The top of the circle scale: the biggest value any stop actually has. */
const pointHigh = computed(() => {
  const field = overlayNow.value.field
  if (!field) return 0
  return Math.max(0, ...demandNow.value.stops.map((one) => one[field] || 0))
})
const onlyLine = computed(() => facets.value.line || '')

/**
 * One thing, looked at alone.
 *
 * `{ kind: 'line' | 'vehicle', name, label }`, or null. Distinct from the facet
 * bar on purpose: a facet is a *question* put to the server — how did U6 run —
 * and re-asks every query on the screen. This is a way of *looking*, costs
 * nothing, and never re-fetches. Conflating them meant that picking a vehicle
 * out of a crowd re-queried a month of history.
 *
 * Everything else stays on the map rather than being removed. A network with
 * one route left on it has lost the thing that makes a route legible, which is
 * the others — so the rest goes grey and faint, and the shape of the city is
 * still there behind the answer.
 */
const isolated = ref(null)
const livemode = ref(true)
const position = ref(1000)
const drawn = ref([])
const service = ref([])
const selected = ref('')
/** The workspace's mode-to-shape mapping, for the picker. Fetched once. */
const markerStyles = ref([])
const mayStyle = ref(false)
/**
 * The workspace's basemap preferences, as the boot payload left them and as the
 * picker changes them.
 *
 * Held here rather than read from `boot` each time because the picker changes
 * them in place: the point of a vector style is that this is a live property of
 * the running map, not a reload.
 */
const mapPrefs = ref(preferred())
const mapStyles = computed(() => Object.keys(basemap?.styles || {}))

/** Our own layers, which a basemap preference must never hide. */
const OURS = [
  'surface', 'lines-casing', 'lines', 'trail', 'stops', 'stops-interchange',
  'demand', 'ghosts', 'vehicles-chosen', 'vehicles',
]

/**
 * Change the ground, for everybody on the workspace.
 *
 * Picking a different *style* is the one change that cannot be made in place —
 * it is a different document — so that one redraws. Labels and detail are
 * properties of layers already on the map, so they are instant, which is the
 * whole argument for vector tiles made visible in about a hundred
 * milliseconds.
 *
 * The next style's URL is resolved here rather than left to `styleFor`, which
 * reads the boot payload: that payload was written when the page loaded and
 * still names whatever the workspace had picked *then*. Hence `styles` arriving
 * as name-to-URL rather than as a list of names.
 */
async function reground(change) {
  const before = mapPrefs.value.pick
  mapPrefs.value = { ...mapPrefs.value, ...change }
  await settings.setBasemap({
    style: change.pick || '',
    labels: change.labels === undefined ? undefined : (change.labels ? 1 : 0),
    detail: change.detail || '',
  })
  if (change.pick && change.pick !== before) {
    await draw()
    return
  }
  applyGround(map, mapPrefs.value, OURS)
}

/**
 * The style this workspace's pick resolves to, as `styleFor` wants it.
 *
 * Resolved here on every draw rather than taken from `basemap.style`, which was
 * written when the page loaded: a reader who picks Bright and then goes back to
 * "Follow the instance" would otherwise be handed Bright, because that is what
 * the payload says the instance resolved to for them that morning.
 */
function chosenStyle() {
  const pick = mapPrefs.value.pick
  if (pick === 'Plain') return 'none'
  if (pick === 'Follow the instance') return 'instance'
  return (basemap?.styles || {})[pick] || ''
}

const following = ref(false)
const playing = ref(false)
const speed = ref(1)

/**
 * The scrubber's right-hand side: the same control, past the present.
 *
 * README §7a asks for this in one sentence — *past on the left, forecast on the
 * right, one control* — and the argument for it is that the gesture is already
 * learnt. Somebody who has dragged back to nine this morning does not need
 * teaching that dragging the other way is nine tomorrow morning.
 *
 * What is drawn there is **the network and not the fleet**, and that is the
 * honest limit rather than a stage left for later. A position is a thing a
 * vehicle reported; a moment that has not happened has none. Carrying ghosts
 * forward on the timetable is what §7a describes, and this model has no
 * timetable to carry them on — `stop_times` is the schedule and §3b says why we
 * do not keep it. So the routes take the colour of what the hour is expected to
 * do, the fleet layer empties, and the clock says Expected rather than pretending.
 */
const aheadAnswer = ref({})
const ghostAnswer = ref({})
/**
 * How many ghosts are actually on the map, which is not the same as how many
 * the server sent: a trip whose stops are not in the loaded network draws
 * nothing. The legend says this number rather than the answer's, so a sentence
 * about rings is a sentence about rings somebody can see — the failure it
 * catches is an id mismatch between the timetable and the stop layer, which is
 * silent in every other way.
 */
const drawnGhosts = ref(0)

let map = null
let library = null
let poller = null
let ticker = null
let frame = null
let sizes = null
const shapes = new Map()
const seen = new Map()
const painted = new Map()
const headings = new Map()

/** The wall clock, ticked so a live screen left open does not freeze at the
 *  minute it was opened. */
const wallClock = ref('')
function tickWallClock() {
  const now = new Date()
  wallClock.value =
    `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
}
tickWallClock()
const accent = computed(() => tokenInk('--surface-gray-9', '#334155'))
const muted = computed(() => tokenInk('--surface-gray-5', '#94a3b8'))

/**
 * How far ahead the day picker reaches, matching `forecast.HORIZON_DAYS`. Past
 * that the server refuses, and a control that offers a choice the server will
 * not honour is a control that teaches people not to trust it — the same rule
 * the Outlook screen's picker keeps.
 */
const AHEAD_DAYS = 14

/**
 * Which days the clock can be pointed at: the ones with observations behind
 * them, and the ones the forecast can speak about.
 *
 * The forward half used to be reachable only within today, which made it a
 * property of what hour somebody happened to open the screen — the whole
 * right-hand side of §7a was unavailable every morning before the fixture's
 * service began and every evening after it ended. A day ahead is a day the
 * timetable and the roll-up can both answer for.
 */
const dayOptions = computed(() => {
  const seen = new Set(days.value.map((one) => one.day))
  const options = days.value.map((one) => ({ label: one.day, value: one.day }))
  for (let step = 0; step <= AHEAD_DAYS; step += 1) {
    const at = new Date()
    at.setDate(at.getDate() + step)
    const iso = at.toISOString().slice(0, 10)
    if (seen.has(iso)) continue
    seen.add(iso)
    options.push({ label: iso, value: iso })
  }
  return options.sort((a, b) => (a.value < b.value ? -1 : 1))
})
const minuteOfDay = computed(
  () => DAY_START + ((DAY_END - DAY_START) * position.value) / 1000
)

/** Where the present is on the track, in service minutes. `null` on any day
 *  but today, because "now" is not a point on last Tuesday. */
const nowMinute = computed(() => {
  const [hh, mm] = (wallClock.value || '00:00').split(':').map(Number)
  return hh * 60 + mm
})
const onToday = computed(() => day.value === todayISO())
/**
 * Whether the clock is pointing at a moment that has not happened.
 *
 * Any moment after now, not only one later today. The first version compared
 * minutes within today and quietly made the whole forward half unreachable for
 * a *date* in the future: pick next Tuesday and every hour of it is ahead of
 * now, and the map was drawing observations that do not exist rather than the
 * expectations it has. A day is either before today, today — where the minute
 * decides — or after it.
 */
const ahead = computed(() => {
  if (livemode.value || !day.value) return false
  if (day.value > todayISO()) return true
  return onToday.value && minuteOfDay.value > nowMinute.value + 1
})

function todayISO() {
  const now = new Date()
  return [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, '0'),
    String(now.getDate()).padStart(2, '0'),
  ].join('-')
}
/** A clock reads the time. "Now" is what the badge beside it is for. */
const clockLabel = computed(() => {
  if (livemode.value) return wallClock.value
  const total = Math.round(minuteOfDay.value)
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
})
const dayLabel = computed(() => day.value || __('Replay'))

/** The vehicle whose card is open, as the row the last poll returned for it. */
const chosen = computed(() => drawn.value.find((one) => one.vehicle === selected.value) || null)

/** Every hour of the service window, as a bar on the track. */
const density = computed(() => {
  const hours = []
  for (let hour = Math.floor(DAY_START / 60); hour < Math.ceil(DAY_END / 60); hour++) hours.push(hour)
  const byHour = new Map((service.value || []).map((one) => [Number(one.hour), Number(one.value) || 0]))
  const most = Math.max(1, ...hours.map((hour) => byHour.get(hour) || 0))
  const width = TRACK_W / hours.length

  return hours.map((hour, at) => ({
    hour,
    x: at * width + 1,
    w: Math.max(1, width - 2),
    // A floor of two pixels, so an hour with nothing in it is still a mark on
    // the ruler rather than a gap that reads as the track ending.
    h: Math.max(2, Math.round(((byHour.get(hour) || 0) / most) * 22)),
    past: hour * 60 <= minuteOfDay.value,
    // An hour that has not happened has no service in it to draw — what the
    // bar shows there is the *history* for that hour, which is the right thing
    // to aim at and the wrong thing to draw as solidly.
    later: onToday.value && hour * 60 > nowMinute.value,
  }))
})

const handleX = computed(() => (position.value / 1000) * TRACK_W)

/** The present, in the track's own coordinates, or nothing on another day. */
const nowX = computed(() => {
  if (!onToday.value) return null
  const at = (nowMinute.value - DAY_START) / (DAY_END - DAY_START)
  return at >= 0 && at <= 1 ? at * TRACK_W : null
})

const ticks = computed(() => {
  const out = []
  for (let hour = Math.floor(DAY_START / 60); hour <= Math.ceil(DAY_END / 60); hour += 4) {
    out.push(`${String(hour).padStart(2, '0')}:00`)
  }
  return out
})

/** The fleet split by occupancy band, as shares of a single bar. */
const mix = computed(() => {
  const counts = new Map()
  for (const one of drawn.value) {
    const band = occupancyBand(one.occupancy)
    counts.set(band.key, (counts.get(band.key) || 0) + 1)
  }
  const total = drawn.value.length || 1
  return OCCUPANCY.filter((band) => counts.get(band.key))
    .map((band) => ({
      key: band.key,
      label: band.label(),
      count: counts.get(band.key),
      share: (counts.get(band.key) / total) * 100,
      ink: occupancyInk(band.floor < 0 ? -1 : band.floor),
    }))
})

function shortNameOf(name) {
  return lines.value.find((one) => one.name === name)?.short_name || '—'
}
function nameOfLine(name) {
  return lines.value.find((one) => one.name === name)?.line_name || ''
}
/** The glyph a line wears. Resolved on the server — see `onemobility/markers.py`. */
function emojiOfLine(name) {
  return lines.value.find((one) => one.name === name)?.emoji || ''
}
function inkOfLine(name) {
  const at = lines.value.findIndex((one) => one.name === name)
  return lineInk(lines.value[at], Math.max(0, at))
}
function occupancyOf(row) {
  const band = occupancyBand(row?.occupancy)
  if (band.floor < 0) return band.label()
  return `${Math.round(row.occupancy)}% · ${band.label()}`
}
function delayLabel(seconds) {
  const value = Number(seconds)
  if (!Number.isFinite(value) || !value) return __('On time')
  const minutes = Math.round(Math.abs(value) / 60)
  if (!minutes) return __('On time')
  return value > 0 ? __('{0} min late', [String(minutes)]) : __('{0} min early', [String(minutes)])
}

// Through the canvas normaliser in `ink.js`: the design tokens are `oklch()`,
// which MapLibre's style specification refuses — and it refuses the whole
// style, so one unconverted colour is a blank screen rather than a grey box.
function ground() {
  return tokenInk('--surface-gray-2', '#eceef1')
}

/**
 * What the map is claiming while the clock is past now, in one sentence.
 *
 * The count of lines and the readings behind them, because a forecast without
 * its basis is a colour somebody has to take on trust — and the first hour a
 * workspace has no history for is exactly when this has to say so rather than
 * draw every route the same neutral shade and let it read as "on time".
 */
const expectedNote = computed(() => {
  if (!ahead.value) return ''
  const lines = (aheadAnswer.value.lines || []).filter((one) => one.delay?.p85 !== null)
  if (!lines.length) return __('Nothing has run at this hour before, so there is nothing to expect yet.')
  const readings = lines.reduce((sum, one) => sum + (one.basis || 0), 0)
  const said = __('Each route wears the delay it usually reaches at this hour. {0} lines, {1} readings.',
    [String(lines.length), String(readings)])
  // And what the rings are, said in the same breath. A hollow amber marker is
  // a claim from a timetable and a filled one is a report from the road, and
  // the legend is where that distinction has to be spelled out — the map can
  // only show it.
  const ghosts = drawnGhosts.value
  return ghosts
    ? `${said} ${__('{0} rings are trips due to be running.', [String(ghosts)])}`
    : said
})

/** The moment being asked about: empty for now, else a date and a time. */
function moment() {
  if (livemode.value || !day.value) return ''
  const total = Math.round(minuteOfDay.value)
  const hh = String(Math.floor(total / 60)).padStart(2, '0')
  const mm = String(total % 60).padStart(2, '0')
  return `${day.value} ${hh}:${mm}:00`
}

/**
 * What the network is expected to do at a moment that has not happened.
 *
 * `risk` rather than a new endpoint: it already answers per line, at an hour,
 * on a weekday, with the spread and what it rests on — which is exactly what
 * the routes have to be coloured by. Reusing it also means the map and the
 * Outlook screen cannot come to disagree about what a line is expected to do,
 * which two queries over one table eventually would.
 */
async function pullAhead() {
  const when = moment()
  const facetted = JSON.stringify(facets.value)
  try {
    // Two reads, and they answer different halves of the same question: what
    // the hour is expected to cost each line, and where each trip is due to
    // be. Together rather than in sequence, because dragging the scrubber
    // fires this on every settle and a second round trip is a visible stall.
    const [risk, ghosts] = await Promise.all([
      network.risk({ when, facets: facetted }),
      network.expected({ when, facets: facetted }),
    ])
    aheadAnswer.value = risk
    ghostAnswer.value = ghosts
  } catch {
    aheadAnswer.value = {}
    ghostAnswer.value = {}
  }
  // No vehicle reported at a time that has not arrived, and a fleet left on
  // the screen from the last poll would be read as one that had.
  seen.clear()
  painted.clear()
  drawn.value = []
  paintAhead()
  paintGhosts()
}

/**
 * The routes, coloured by what the hour is expected to cost them.
 *
 * A `match` on the line's own id rather than a data join: the geometry is
 * already on the map and only its paint changes, so a forecast arriving is one
 * property set rather than a source replaced — which is what keeps dragging the
 * scrubber smooth instead of restarting the layer on every settle.
 */
function paintAhead() {
  if (!map || !map.getLayer('lines')) return
  const lines = aheadAnswer.value.lines || []
  const known = lines.filter((one) => one.id && one.delay?.p85 !== null)
  if (!known.length) return paintIsolation()

  const stops = known.flatMap((one) => [one.id, delayInk(one.delay.p85)])
  map.setPaintProperty('lines', 'line-color', [
    'match', ['get', 'name'], ...stops,
    // A line with no history keeps its own colour rather than taking the
    // middle of the scale: "we do not know" and "we expect it to be on time"
    // are different claims and only one of them is ours to make.
    ['get', 'colour'],
  ])
}

/**
 * Where each trip is *due* to be, drawn as a ghost.
 *
 * The server answers with two stops and a fraction rather than a position —
 * see `timetable.expected` — so the geometry happens here, where the drawn
 * shape of every line already lives and where `motion.js` already knows how to
 * put a point on one. Sending coordinates instead would be a second geometry
 * implementation that can disagree with the first about where a route goes.
 *
 * Projected onto the shape rather than interpolated between the two stops: a
 * straight line between consecutive stops cuts every corner, and on a route
 * that loops around a park it draws a vehicle through the middle of it.
 */
function paintGhosts() {
  if (!map || !map.getSource('ghosts')) return
  if (!ahead.value) {
    map.getSource('ghosts').setData({ type: 'FeatureCollection', features: [] })
    drawnGhosts.value = 0
    return
  }

  const where = new Map(
    stops.value
      .filter((one) => one.latitude || one.longitude)
      .map((one) => [one.name, [one.longitude, one.latitude]]),
  )

  const features = []
  for (const ghost of ghostAnswer.value.ghosts || []) {
    const from = where.get(ghost.from_stop)
    const to = where.get(ghost.to_stop)
    if (!from || !to) continue

    const shape = shapes.get(ghost.line) || null
    let point
    if (shape) {
      const a = project(shape.points, shape.along, from[0], from[1])
      const b = project(shape.points, shape.along, to[0], to[1])
      point = at(shape.points, shape.along, a + (b - a) * ghost.t)
    }
    // A line with no drawn shape — a feed with no `shapes.txt`, a VDV delivery
    // whose stop list is all the geometry there is — still gets a ghost, on
    // the straight line the map is already drawing for it.
    if (!point) {
      point = [from[0] + (to[0] - from[0]) * ghost.t, from[1] + (to[1] - from[1]) * ghost.t]
    }

    features.push({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: point },
      properties: {
        trip: ghost.trip_key,
        line: ghost.line,
        bearing: bearingBetween(from, to),
        mode: coarseFor(markerOf(ghost.line)),
      },
    })
  }
  map.getSource('ghosts').setData({ type: 'FeatureCollection', features })
  drawnGhosts.value = features.length
}

async function pull() {
  if (ahead.value) return pullAhead()
  paintGhosts()
  // Back on ground that has happened: the routes take their own colours again.
  // Without this a line keeps the colour of a forecast while the map draws
  // observations, which is the worst of the two states to be in.
  paintIsolation()
  try {
    const answer = await network.at({
      when: moment(),
      facets: JSON.stringify(facets.value),
    })
    unavailable.value = answer.unavailable || []
    const now = performance.now()
    for (const one of answer.vehicles || []) {
      const before = seen.get(one.vehicle)
      seen.set(one.vehicle, {
        previous: before?.latest || null,
        latest: one,
        // What the tween runs over. In live mode it is the poll interval; when
        // scrubbing there is nothing to tween — the answer *is* the moment.
        from: now,
        span: livemode.value ? LIVE_EVERY : 0,
      })
    }
    // A vehicle that has left the answer has left the screen. Keeping it would
    // leave a ghost sitting where it was an hour ago.
    const alive = new Set((answer.vehicles || []).map((v) => v.vehicle))
    for (const key of [...seen.keys()]) if (!alive.has(key)) seen.delete(key)
    drawn.value = answer.vehicles || []
  } catch {
    // A dropped poll is not an error worth a toast: the next one is five
    // seconds away and the map still shows the last known truth.
  }
}

function paint() {
  if (!map || !map.getSource('vehicles')) return

  const now = performance.now()
  const features = []
  for (const [vehicle, state] of seen) {
    const { previous, latest, from, span } = state
    const shape = shapes.get(latest.line) || null
    const k = span ? (now - from) / span : 1
    const moved = advance(shape, previous, latest, k)
    const along = moved?.point || [latest.lon, latest.lat]
    // Ease onto the computed point rather than teleporting when a poll lands.
    const was = painted.get(vehicle)
    const at = blend(was, along, span ? 0.25 : 1)
    painted.set(vehicle, at)

    // Which way it is facing: the direction of the *route* under it, not the
    // direction it happened to move last frame. A vehicle standing at a stop
    // still faces down the road, and one that has just appeared faces the way
    // it is about to go rather than north. Frame-to-frame movement is the
    // fallback, for a vehicle whose line has no shape to follow.
    const facing = moved?.bearing ?? bearingBetween(was, at)
    // Eased the short way round, so a vehicle crossing north does not spin
    // through the compass.
    const heading = easeBearing(headings.get(vehicle), facing, span ? 0.3 : 1)
    headings.set(vehicle, heading)

    features.push({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: at },
      properties: {
        vehicle,
        line: latest.line,
        stale: latest.stale ? 1 : 0,
        bearing: heading,
        band: occupancyBand(latest.occupancy).key,
        // Both: `mode` names one of the seven squat silhouettes and `shape`
        // one of the thirty-three drawings, and the layer steps between them.
        mode: coarseFor(markerOf(latest.line)),
        shape: markerOf(latest.line),
        chosen: vehicle === selected.value ? 1 : 0,
      },
    })

    if (following.value && vehicle === selected.value) map.easeTo({ center: at, duration: 400 })
  }

  map.getSource('vehicles').setData({ type: 'FeatureCollection', features })
  frame = requestAnimationFrame(paint)
}

function onScrub() {
  livemode.value = false
  playing.value = false
  scrubTo()
}

let scrubbing = null
function scrubTo(where) {
  if (where !== undefined) position.value = Math.round(where * 1000)
  // One request per settle, not one per pixel of drag.
  clearTimeout(scrubbing)
  scrubbing = setTimeout(pull, 120)
}

function togglePlay() {
  if (livemode.value) return
  playing.value = !playing.value
}

function cycleSpeed() {
  speed.value = SPEEDS[(SPEEDS.indexOf(speed.value) + 1) % SPEEDS.length]
}

// Watched rather than `@change` on the Select: frappe-ui's Select emits
// `update:modelValue` and `update:open`, and nothing else. A `@change` on it is
// a listener for an event that is never raised — the day changes, and the map
// goes on showing the one before.
watch(day, () => scrubTo(0.5))
// And the line filter, which had no handler at all: in live mode the poller
// would have picked it up within five seconds, and in replay it never would.
watch(facets, () => {
  pull()
  // The overlay is narrowed by the same bar, and its answer is a different
  // query — a line chosen on the map has to re-ask where *that* line runs late,
  // not filter a grid built for the whole network.
  demandNow.value = { stops: [] }
  if (overlayNow.value.kind !== 'none') pullOverlay()
}, { deep: true })

const route = useRoute()
const router = useRouter()

/**
 * The chosen overlay lives in the URL as well as in the ref.
 *
 * Same reason the facets do on Insights: "the corridor where U6 loses its time"
 * is a thing worth sending to somebody, and a screenshot is not a link. It is
 * read once on arrival and written on every change, so the back button walks
 * the layers rather than leaving the screen.
 */
watch(overlay, (key) => {
  const query = { ...route.query }
  if (key === 'none') delete query.overlay
  else query.overlay = key
  router.replace({ query }).catch(() => {})

  if (overlayNow.value.kind === 'none') drawOverlay()
  else pullOverlay()
})

/**
 * Re-bin when the zoom crosses a bucket, and only then. `moveend` fires on
 * every pan; comparing the bucket rather than the zoom is what keeps a drag
 * across a city from being twenty identical queries.
 */
function onZoomed() {
  if (overlayNow.value.kind !== 'surface') return
  if (gridFor(map.getZoom()) === gridNow) return
  pullOverlay()
}

/**
 * The three base layers. Every one of them is more than a single MapLibre layer
 * — a route is its casing and its line, a vehicle is its halo and its marker —
 * so the toggle names the group rather than the id.
 */
const BASE_LAYERS = {
  routes: ['lines-casing', 'lines'],
  stops: ['stops', 'stops-interchange'],
  vehicles: ['vehicles', 'vehicles-chosen'],
}

/**
 * Look at one thing alone: full colour on it, grey and faint on everything else.
 *
 * Monochrome rather than hidden, and that is the whole design. A route drawn
 * alone on a blank ground has lost its context — which junctions it crosses,
 * which corridor it shares — and those are exactly what somebody isolating it
 * is usually trying to see. So the network stays, in one grey, at a fifth of
 * the opacity: present as geography, gone as information.
 */
function isolate(what) {
  isolated.value = what || null
  paintIsolation()
  if (map?.getSource('lines')) map.getSource('lines').setData(lineFeatures())
}

/**
 * The paint expressions that carry it. Set here rather than at layer creation
 * because they change with what is chosen, and rebuilding a layer to change a
 * colour is how a map comes to flicker.
 */
function paintIsolation() {
  if (!map || !map.getLayer('lines')) return
  const one = isolated.value
  const grey = tokenInk('--ink-gray-4', '#a1a1aa')

  // A vehicle belongs to a line, so isolating a vehicle isolates its line too:
  // the road it is on is the first thing anybody looks at next.
  const line = one?.kind === 'line' ? one.name : lineOfVehicle(one?.name)

  map.setPaintProperty('lines', 'line-color',
    line ? ['case', ['==', ['get', 'name'], line], ['get', 'colour'], grey] : ['get', 'colour'])
  // Faint, not gone. Dimmed far enough that nothing competes with the answer,
  // and not so far that the city disappears — which is the failure mode of
  // every "show only this" that hides instead of fading.
  map.setPaintProperty('lines', 'line-opacity',
    line
      ? ['case', ['==', ['get', 'name'], line], 1, 0.3]
      : ['case', ['==', ['get', 'dimmed'], 1], 0.18, 1])

  for (const layer of ['stops', 'stops-interchange']) {
    if (map.getLayer(layer)) map.setPaintProperty(layer, 'circle-opacity', one ? 0.35 : 1)
  }
  if (map.getLayer('vehicles')) {
    map.setPaintProperty('vehicles', 'icon-opacity', vehicleOpacity())
  }
}

/**
 * How solid a vehicle marker is: stale is faint, and so is everything that is
 * not the thing being looked at. One expression rather than two layers, because
 * a second symbol layer for forty markers is a second placement pass.
 */
function vehicleOpacity() {
  const one = isolated.value
  const live = ['case', ['==', ['get', 'stale'], 1], 0.4, 1]
  if (!one) return live
  const mine = one.kind === 'vehicle'
    ? ['==', ['get', 'vehicle'], one.name]
    : ['==', ['get', 'line'], one.name]
  return ['case', mine, live, 0.2]
}

function lineOfVehicle(vehicle) {
  if (!vehicle) return ''
  return drawn.value.find((one) => one.vehicle === vehicle)?.line || ''
}

/**
 * Draw a mode as a different shape, and show it immediately.
 *
 * Written to the server first and applied locally after, rather than
 * optimistically: this is a workspace-wide change and a picker that showed a
 * shape nobody else could see would be lying about what it had done. The round
 * trip is one small write and the map redraws in the same frame it returns.
 */
async function restyle({ mode, shape, emoji }) {
  await network.setMarkerStyle({ mode, shape: shape || '', emoji_glyph: emoji || '' })
  for (const line of lines.value) {
    if (String(line.mode || '').toLowerCase() === String(mode).toLowerCase()) {
      // Only where the line has not overridden its mode: a heritage tram stays
      // a tram, and a line with its own glyph keeps it, when the whole Bus
      // fleet is redrawn.
      if (shape && !line.marker_shape) line.marker = shape
      if (emoji && !line.emoji_own) line.emoji = emoji
    }
  }
  for (const one of markerStyles.value) {
    if (one.mode !== mode) continue
    if (shape) one.shape = shape
    if (emoji) one.emoji = emoji
  }
  // The squat silhouettes are already registered for all seven; the artwork for
  // a shape nobody was running has to be rasterised now.
  if (shape) await registerArt([shape])
  lines.value = [...lines.value]
}

function showGroup(group, on) {
  if (!map) return
  for (const id of BASE_LAYERS[group]) {
    if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none')
  }
}

watch(showRoutes, (on) => showGroup('routes', on))
watch(showStops, (on) => showGroup('stops', on))
watch(showVehicles, (on) => showGroup('vehicles', on))

function goLive() {
  livemode.value = true
  playing.value = false
  position.value = 1000
  pull()
}

/** Open a vehicle, and fetch the day it has had. */
async function choose(vehicle) {
  selected.value = vehicle
  if (!vehicle) following.value = false
  if (map?.getSource('trail')) {
    map.getSource('trail').setData({ type: 'FeatureCollection', features: [] })
  }
  if (!vehicle || !day.value) return

  try {
    const path = await network.track({ vehicle, day: day.value })
    const coordinates = (path.lon || []).map((lon, at) => [lon, path.lat[at]])
      .filter(([lon, lat]) => lon || lat)
    if (coordinates.length > 1 && map?.getSource('trail')) {
      map.getSource('trail').setData({
        type: 'FeatureCollection',
        features: [{ type: 'Feature', geometry: { type: 'LineString', coordinates }, properties: {} }],
      })
    }
  } catch {
    // A vehicle with no stored day is not an error — it is a vehicle that
    // started reporting this morning.
  }
}

/**
 * MapLibre sizes its canvas from the container at construction and does not
 * always notice later. A screen that mounts before its parent has settled
 * gets a map drawn into a canvas three hundred pixels tall inside a container
 * of eight hundred — no error, no warning, just most of the map missing.
 *
 * So: wait for a real size before constructing, and watch for changes after.
 */
function whenSized(element) {
  return new Promise((resolve) => {
    if (element?.clientHeight) return resolve()
    const observer = new ResizeObserver(() => {
      if (!element.clientHeight) return
      observer.disconnect()
      resolve()
    })
    observer.observe(element)
    // A container that never gets a height should not hang the screen.
    setTimeout(() => { observer.disconnect(); resolve() }, 2000)
  })
}

/** One drawn marker per occupancy band, registered under that band's name. */
/**
 * One image per mode per occupancy band — six by five, drawn once at load.
 *
 * Thirty small canvases sounds like a lot and is about four milliseconds; the
 * alternative is one image and a separate badge layer, which costs a second
 * symbol layer and a second label for every vehicle on screen. The silhouette
 * is doing the work that a badge would: what a person picks out of forty
 * moving markers is the *outline*, and a tram differs from a bus in exactly the
 * two ways that survive being sixteen pixels tall.
 */
function registerMarkers() {
  const ring = casingInk()
  const ratio = Math.min(3, Math.max(1, window.devicePixelRatio || 1))
  for (const mode of MODES) {
    for (const band of OCCUPANCY) {
      const id = `vehicle-${mode}-${band.key}`
      if (map.hasImage(id)) map.removeImage(id)
      map.addImage(
        id,
        vehicleMarker(mode, occupancyInk(band.floor < 0 ? -1 : band.floor), ring, ratio),
        // `pixelRatio` is style-image *metadata* and belongs in the third
        // argument. Passed inside the image it is silently ignored, and every
        // marker draws at twice the size it was meant to.
        { pixelRatio: ratio },
      )
    }
  }
}

/**
 * The drawn artwork, rasterised for the shapes this network actually runs.
 *
 * Only those: thirty-three shapes across five bands is a hundred and sixty-five
 * images, and a network of buses will never use a hundred and fifty of them.
 * Rasterising an SVG means letting the browser lay it out, so each one is an
 * image load — cheap, but not free enough to do for a catalogue.
 */
async function registerArt(shapes) {
  // At least two: these only appear once a marker is thirty pixels or more,
  // which is where the detail in them is the point, and at that size the
  // difference between a two- and a three-times bitmap is visible.
  const ratio = Math.min(3, Math.max(2, window.devicePixelRatio || 1))
  const jobs = []
  for (const shape of shapes) {
    if (!drawnArt(shape)) continue
    for (const band of OCCUPANCY) {
      const id = `art-${shape}-${band.key}`
      if (map.hasImage(id)) continue
      jobs.push(
        // Forty points, the same box the canvas markers are drawn in, so
        // `icon-size` means one thing on both sides of the step. Rasterised at
        // the device ratio and declared at it: `pixelRatio` is how many image
        // pixels go to a CSS pixel, so getting it wrong scales every marker.
        rasterise(shape, occupancyInk(band.floor < 0 ? -1 : band.floor), 40, ratio)
          .then((image) => {
            // The map may have gone away while the browser was laying out an
            // SVG — this screen is left and re-entered like any other.
            if (map && !map.hasImage(id)) map.addImage(id, image, { pixelRatio: ratio })
          })
          .catch(() => {}),
      )
    }
  }
  await Promise.all(jobs)
}

/**
 * The legend's shape key: one drawing per mode this network actually runs.
 *
 * Off the *resolved* marker rather than the mode, so a workspace that draws
 * its Rail as a tram gets a key with a tram in it. `markers.py` decides;
 * this only reports.
 */
const shapesHere = computed(() => {
  const found = new Set(lines.value.map((one) => markerOf(one)))
  return ART_SHAPES.filter((shape) => found.has(shape))
})

/**
 * The overlay's data, fetched when it is chosen and when the facets move under
 * it. Nothing is asked for while the overlay is off — these are the two
 * heaviest questions this screen can put to the server, and a map that pays for
 * them before anybody has asked one is a slow map for no reason.
 */
async function pullOverlay() {
  const one = overlayNow.value
  const params = { facets: JSON.stringify(facets.value) }
  if (one.kind === 'surface') {
    gridNow = gridFor(map?.getZoom() ?? 11)
    surfaceNow.value = await network.surface({ ...params, kind: one.key, precision: gridNow })
  } else if (one.kind === 'points' && !demandNow.value.stops.length) {
    demandNow.value = await network.demand(params)
  }
  drawOverlay()
}

/**
 * How fine the grid should be for the zoom being looked at.
 *
 * A hundred-metre cell is the right resolution for asking which junction loses
 * the time, and it is invisible from across a city — at that zoom it is two
 * pixels, under an eight-pixel route line. The first version drew the whole
 * surface underneath the network and looked, convincingly, like nothing had
 * happened.
 *
 * So the bin follows the view: kilometre cells for the shape of a city,
 * hundred-metre for a district, ten-metre once a street fills the screen. Three
 * buckets rather than a continuous function, so panning about at one zoom does
 * not re-ask the server for an answer it already has.
 */
function gridFor(zoom) {
  if (zoom < 12) return 2
  if (zoom < 14.5) return 3
  return 4
}

let gridNow = 2

function demandFeatures() {
  const field = overlayNow.value.field
  return {
    type: 'FeatureCollection',
    features: (demandNow.value.stops || [])
      .filter((one) => (one[field] || 0) > 0)
      .map((one) => ({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [one.lon, one.lat] },
        properties: { label: one.label, value: one[field] || 0 },
      })),
  }
}

/**
 * Repaint the overlay layers for whatever is chosen.
 *
 * The colour and the radius are set here rather than at layer creation because
 * both depend on the range the *data* came back with — a scale fixed at build
 * time would put a whole city in one step of the ramp the first time somebody
 * narrowed to one line.
 */
function drawOverlay() {
  if (!map || !map.getSource('surface')) return
  const one = overlayNow.value

  map.setLayoutProperty('surface', 'visibility', one.kind === 'surface' ? 'visible' : 'none')
  map.setLayoutProperty('demand', 'visibility', one.kind === 'points' ? 'visible' : 'none')

  if (one.kind === 'surface') {
    // Colour, coverage and where it goes, all decided in one pass over the
    // cells — see `lib/surface.js`. The alpha is how much has been seen there,
    // because colour is already carrying the measure.
    const corners = paintSurface(field, surfaceNow.value, one.ramp())
    if (corners) {
      map.getSource('surface').setCoordinates(corners)
      // The source only re-reads the canvas when it is told to; nothing about
      // drawing into it is something MapLibre can observe.
      map.getSource('surface').play()
      map.getSource('surface').pause()
    }
  }

  if (one.kind === 'points') {
    map.getSource('demand').setData(demandFeatures())
    const top = Math.max(1, pointHigh.value)
    map.setPaintProperty('demand', 'circle-color', one.ink())
    // Area, not radius, tracks the value: a circle twice as wide reads as four
    // times as much, which is what a square root keeps honest.
    map.setPaintProperty('demand', 'circle-radius', [
      'interpolate', ['linear'], ['sqrt', ['get', 'value']], 0, 3, Math.sqrt(top), 26,
    ])
  }
}

/**
 * Which silhouette a line is drawn with.
 *
 * Resolved on the server — `onemobility/markers.py` applies the workspace's
 * own mode-to-shape mapping and any per-line override — so this reads an
 * answer rather than deciding one. `bodyFor` is the floor under it: a line
 * from a feed older than the mapping still gets a drawing.
 */
function markerOf(line) {
  const found = typeof line === 'string' ? lines.value.find((one) => one.name === line) : line
  const asked = String(found?.marker || found?.mode || '').toLowerCase()
  // The drawing's own name, or the plain van. Never `bodyFor` here: that
  // answers with one of the seven squat silhouettes, and this is the finer
  // question. The server resolves this properly — `markers.BY_MODE` — so this
  // only catches a line older than the mapping.
  return drawnArt(asked) ? asked : FALLBACK_SHAPE
}

async function draw() {
  await whenSized(canvas.value)
  const module = await import('maplibre-gl')
  await import('maplibre-gl/dist/maplibre-gl.css')
  library = module.default || module

  // The basemap is the engine's, not this space's: `lib/screen/basemap.js` is
  // where the product decides where tiles come from, so the map view type and
  // this screen are never drawn on two different grounds.
  map = new library.Map({
    container: canvas.value,
    style: styleFor(ground(), chosenStyle()),
    center: [13.4, 52.52],
    zoom: 11,
    // Credit goes top-left: the bottom of this screen is the clock, and an
    // attribution behind a control is not an attribution.
    attributionControl: false,
  })
  map.addControl(
    new library.AttributionControl({ compact: true, customAttribution: attribution() }),
    'top-left',
  )
  quietTiles(map)
  map.addControl(new library.NavigationControl({ showCompass: false }), 'top-right')
  sizes = new ResizeObserver(() => map?.resize())
  sizes.observe(canvas.value)
  await whenLoaded(map, ground())

  // What the workspace has said about its ground, applied to the style that is
  // actually on the map. Before our own layers go down, so `OURS` below is only
  // about the calls that happen *after* a picker changes something.
  applyGround(map, mapPrefs.value)

  registerMarkers()
  // Not awaited: the squat silhouettes are already registered, so the map draws
  // immediately and the artwork appears as it finishes — which is before
  // anybody has zoomed in far enough to see it.
  registerArt(shapesHere.value)

  const casing = casingInk()

  // The surface goes down *first*, so every route, stop and vehicle sits on top
  // of it. It is the ground the network runs over, and a grid painted above the
  // lines would be a grid that hides them.
  // A canvas rather than a polygon per cell. The bins are still bins — the mean
  // inside one is what the colour means — but the *edges* were an artefact of
  // where the grid happened to fall, drawn as though they were a place where
  // the network changes. `lib/surface.js` says how the field is smoothed.
  //
  // `coordinates` are replaced on every answer; these four are a placeholder,
  // because a canvas source cannot be added without them.
  map.addSource('surface', {
    type: 'canvas',
    canvas: field,
    coordinates: [[0, 1], [1, 1], [1, 0], [0, 0]],
    animate: false,
  })
  map.addLayer({
    id: 'surface',
    type: 'raster',
    source: 'surface',
    layout: { visibility: 'none' },
    // Linear, which is where most of the smoothing comes from: the canvas is
    // one pixel per cell and the GPU interpolates it up to the screen. Nearest
    // would put every hard edge straight back.
    paint: { 'raster-opacity': 1, 'raster-resampling': 'linear', 'raster-fade-duration': 0 },
  })

  map.addSource('lines', { type: 'geojson', data: lineFeatures() })

  // The casing, and then the line. Every transit map draws a route this way,
  // and it is not decoration: it is what keeps two routes legible where they
  // run together, and what stops a dark red line dissolving into the ground.
  map.addLayer({
    id: 'lines-casing',
    type: 'line',
    source: 'lines',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: {
      'line-color': casing,
      'line-width': ['interpolate', ['linear'], ['zoom'], 10, 8, 14, 15, 16, 22],
      'line-opacity': 0.95,
    },
  })
  map.addLayer({
    id: 'lines',
    type: 'line',
    source: 'lines',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: {
      'line-color': ['get', 'colour'],
      'line-width': ['interpolate', ['linear'], ['zoom'], 10, 4.5, 14, 9, 16, 13],
      // The filtered-out lines stay, faintly. A network with one route left on
      // it has lost the thing that makes a route legible, which is the others.
      'line-opacity': ['case', ['==', ['get', 'dimmed'], 1], 0.18, 1],
    },
  })

  // The trail of the vehicle that is open, under the stops so a terminus is
  // never hidden by it.
  map.addSource('trail', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
  map.addLayer({
    id: 'trail',
    type: 'line',
    source: 'trail',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: {
      'line-color': tokenInk('--surface-gray-9', '#334155'),
      'line-width': 2,
      'line-opacity': 0.5,
      'line-dasharray': [1, 2],
    },
  })

  map.addSource('stops', { type: 'geojson', data: stopFeatures() })
  map.addLayer({
    id: 'stops',
    type: 'circle',
    source: 'stops',
    paint: {
      // An interchange is drawn bigger. Every printed transit map does this and
      // it is not decoration — it is the thing somebody working out a journey
      // is scanning for. What makes it possible here is that the number is now
      // *observed*: `arrivals.py` counts the lines that have actually had a
      // vehicle stand at each stop, and this model has no timetable relation
      // that could have said so.
      'circle-radius': [
        'interpolate', ['linear'], ['zoom'],
        10, ['case', ['>', ['get', 'served'], 1], 6.5, 3.5],
        14, ['case', ['>', ['get', 'served'], 1], 10, 5.5],
        16, ['case', ['>', ['get', 'served'], 1], 13, 7.5],
      ],
      'circle-color': casing,
      'circle-stroke-width': [
        'interpolate', ['linear'], ['zoom'],
        10, 2, 14, ['case', ['>', ['get', 'served'], 1], 3.5, 2.5],
        16, ['case', ['>', ['get', 'served'], 1], 4.5, 3],
      ],
      // An inferred stop — one a vehicle stopped at and no feed declared — is
      // drawn differently and never quietly promoted into the network.
      'circle-stroke-color': [
        'case',
        ['==', ['get', 'status'], 'Inferred'], tokenInk('--ink-amber-3', '#f59e0b'),
        tokenInk('--ink-gray-7', '#3f3f46'),
      ],
    },
  })

  // The interchange's inner ring. A second, smaller circle inside the first —
  // the double ring a transit map draws where lines meet — rather than a
  // thicker stroke, because a thick stroke at three lines and at seven looks
  // the same and this does not.
  map.addLayer({
    id: 'stops-interchange',
    type: 'circle',
    source: 'stops',
    filter: ['>', ['get', 'served'], 1],
    paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 2.5, 14, 4, 16, 5.5],
      'circle-color': tokenInk('--ink-gray-7', '#3f3f46'),
    },
  })

  // The stop overlay sits above the routes and below the vehicles: it is a
  // property *of* the network rather than the ground under it, and a live
  // vehicle must never be hidden by a month of history.
  map.addSource('demand', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
  map.addLayer({
    id: 'demand',
    type: 'circle',
    source: 'demand',
    layout: { visibility: 'none' },
    paint: {
      'circle-radius': 6,
      'circle-color': casing,
      'circle-opacity': 0.55,
      'circle-stroke-width': 1,
      'circle-stroke-color': casing,
    },
  })

  // Where a trip is *due* to be, when the clock has been dragged past now.
  //
  // Below the live fleet and drawn as an outline rather than as a marker,
  // which is the whole point: a ghost is a claim from a timetable and a
  // vehicle is a report from the road, and a map that draws them the same way
  // is a map that has quietly stopped distinguishing them. Amber, the colour
  // the legend and the badge already use for what is expected.
  map.addSource('ghosts', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
  map.addLayer({
    id: 'ghosts',
    type: 'circle',
    source: 'ghosts',
    paint: {
      // Bigger than a stop and hollower, because that is the whole reading:
      // at a glance a ghost has to be neither a stop nor a vehicle. A stop is
      // a small solid dot with a dark edge; this is a wide pale ring in the
      // amber the badge and the legend already use for what is expected.
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 5, 14, 9],
      'circle-color': tokenInk('--surface-white', '#ffffff'),
      'circle-opacity': 0.35,
      'circle-stroke-width': 2.5,
      'circle-stroke-color': tokenInk('--surface-amber-3', '#f59e0b'),
    },
  })

  map.addSource('vehicles', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
  // The ring under the chosen one. A separate layer rather than a second
  // marker image, so opening a vehicle does not have to redraw every icon.
  map.addLayer({
    id: 'vehicles-chosen',
    type: 'circle',
    source: 'vehicles',
    filter: ['==', ['get', 'chosen'], 1],
    paint: {
      'circle-radius': 20,
      'circle-color': tokenInk('--surface-gray-9', '#334155'),
      'circle-opacity': 0.12,
      'circle-stroke-width': 2,
      'circle-stroke-color': tokenInk('--surface-gray-9', '#334155'),
      'circle-stroke-opacity': 0.5,
    },
  })
  map.addLayer({
    id: 'vehicles',
    type: 'symbol',
    source: 'vehicles',
    layout: {
      // Two sets of images, and the zoom picks which.
      //
      // Below thirteen a marker is twenty-odd pixels on its long axis and eight
      // across, and the drawn artwork — which is a real vehicle seen from above,
      // at real proportions — is a tick at that size. `markers.js`'s squat
      // silhouettes are deliberately wrong about proportion for exactly this
      // reason, the way a printed transit map is. Above it the artwork is
      // thirty pixels and up, which is where its detail starts being the point.
      //
      // Settled by rendering every shape at every size the map actually draws.
      'icon-image': [
        'step', ['zoom'],
        ['concat', 'vehicle-', ['get', 'mode'], '-', ['get', 'band']],
        13, ['concat', 'art-', ['get', 'shape'], '-', ['get', 'band']],
      ],
      // The bitmap is forty points on its long side so a bus has room to be a
      // bus; on the map it wants to be about half a stop's width, not twice it.
      // The step at thirteen lands on 0.78, which is thirty-one pixels.
      'icon-size': ['interpolate', ['linear'], ['zoom'], 10, 0.55, 13, 0.78, 16, 0.95],
      'icon-rotate': ['get', 'bearing'],
      'icon-rotation-alignment': 'map',
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
    },
    // A stale position is drawn faint. Never as though it were live.
    paint: { 'icon-opacity': ['case', ['==', ['get', 'stale'], 1], 0.4, 1] },
  })

  map.on('zoomend', onZoomed)

  map.on('click', 'vehicles', (event) => {
    const hit = event.features?.[0]
    if (hit?.properties?.vehicle) choose(hit.properties.vehicle)
  })

  // A click on a route looks at it alone. The one interaction a transit map
  // has always had and this one did not: forty overlapping lines and no way to
  // pull one out of them without going to another screen and narrowing.
  map.on('click', 'lines', (event) => {
    const hit = event.features?.[0]
    const line = hit && lines.value.find((one) => one.name === hit.properties.name)
    if (!line) return
    // The same route again puts everything back. A mode you can enter and not
    // leave by the way you entered it is a mode people learn to avoid.
    const already = isolated.value?.kind === 'line' && isolated.value.name === line.name
    isolate(already ? null : {
      kind: 'line',
      name: line.name,
      label: [line.emoji, line.short_name || line.line_name || line.name]
        .filter(Boolean).join(' '),
    })
  })

  // And a click on the ground clears it, which is what every map has taught
  // people that clicking nothing does.
  map.on('click', (event) => {
    if (!isolated.value) return
    const hit = map.queryRenderedFeatures(event.point, {
      layers: ['lines', 'vehicles', 'stops'].filter((one) => map.getLayer(one)),
    })
    if (!hit.length) isolate(null)
  })
  map.on('mouseenter', 'vehicles', () => { map.getCanvas().style.cursor = 'pointer' })
  map.on('mouseleave', 'vehicles', () => { map.getCanvas().style.cursor = '' })

  // A stop says its name on hover. There is no text layer available — the
  // style carries no `glyphs` URL and MapLibre needs one for any label — so
  // the name is an HTML popup, which is better anyway: it wears the product's
  // own type rather than a font baked into a tileset.
  const popup = new library.Popup({ closeButton: false, closeOnClick: false, offset: 12 })

  /**
   * One hover handler for all three, because a hover is one behaviour and
   * three copies of it is three chances for one of them to stop closing.
   *
   * `card` builds the HTML; `where` says where to anchor it — a stop and a
   * vehicle are points and have their own coordinates, a route is a line and
   * has none, so the pointer is the only honest anchor for it.
   */
  const onHover = (layer, card, where) => {
    map.on('mousemove', layer, (event) => {
      const hit = event.features?.[0]
      if (!hit) return
      map.getCanvas().style.cursor = 'pointer'
      popup.setLngLat(where ? where(hit, event) : event.lngLat).setHTML(card(hit)).addTo(map)
    })
    map.on('mouseleave', layer, () => {
      map.getCanvas().style.cursor = ''
      popup.remove()
    })
  }

  // A stop, a vehicle and a route each say the thing a person is hovering to
  // find out — which stop, which vehicle and how full, which line — rather
  // than one generic tooltip that says the id three times.
  onHover('stops', stopCard, (hit) => hit.geometry.coordinates)
  onHover('vehicles', vehicleCard, (hit) => hit.geometry.coordinates)
  onHover('lines', lineCard)

  const bounds = new library.LngLatBounds()
  let any = false
  for (const stop of stops.value) {
    if (!stop.latitude && !stop.longitude) continue
    bounds.extend([stop.longitude, stop.latitude])
    any = true
  }
  // More room at the bottom than the sides: the clock floats over it, and a
  // terminus drawn underneath the clock is a terminus nobody can see.
  if (any) {
    map.fitBounds(bounds, {
      padding: { top: 56, right: 56, bottom: 150, left: 56 },
      duration: 0,
      maxZoom: 14,
    })
  }
}

/** Escaped, because a stop name comes from a feed somebody else wrote. */
/**
 * The three hover cards.
 *
 * Built as HTML strings rather than as components, because MapLibre's Popup
 * takes markup and mounting a Vue component per hover would be a mount and an
 * unmount on every pixel of a drag across a network. Every value that reaches
 * one goes through `escapeHtml` — a stop is named by a customer's feed, and a
 * feed is not a trusted author.
 */
function stopCard(hit) {
  const served = Number(hit.properties.served || 0)
  const lines = served > 1
    ? __('{0} lines stop here', [served])
    : (served === 1 ? __('One line stops here') : __('Nothing has stopped here yet'))
  const inferred = hit.properties.status === 'Inferred'
    ? `<p class="text-2xs text-ink-amber-3">${escapeHtml(__('Nobody declared this stop'))}</p>`
    : ''
  return `<div class="flex flex-col gap-0.5">
    <p class="text-xs font-medium text-ink-gray-8">
      ${escapeHtml(hit.properties.emoji || '')} ${escapeHtml(hit.properties.label || '')}
    </p>
    <p class="text-2xs text-ink-gray-5">${escapeHtml(lines)}</p>${inferred}</div>`
}

function vehicleCard(hit) {
  const line = lines.value.find((one) => one.name === hit.properties.line)
  const found = drawn.value.find((one) => one.vehicle === hit.properties.vehicle)
  const band = occupancyBand(found?.occupancy)
  return `<div class="flex flex-col gap-0.5">
    <p class="text-xs font-medium text-ink-gray-8">
      ${escapeHtml(line?.emoji || '')} ${escapeHtml(hit.properties.vehicle || '')}
    </p>
    <p class="text-2xs text-ink-gray-5">${escapeHtml(line?.line_name || '')}</p>
    <p class="flex items-center gap-1 text-2xs text-ink-gray-6">
      <span style="background:${escapeHtml(bandInk(band))}"
            class="inline-block size-1.5 rounded-full"></span>
      ${escapeHtml(band.label())}
      ${found ? `&middot; ${escapeHtml(delayLabel(found.delay_s))}` : ''}
    </p></div>`
}

function lineCard(hit) {
  const line = lines.value.find((one) => one.name === hit.properties.name)
  if (!line) return ''
  const running = drawn.value.filter((one) => one.line === line.name).length
  return `<div class="flex flex-col gap-0.5">
    <p class="flex items-center gap-1.5 text-xs font-medium text-ink-gray-8">
      <span style="background:${escapeHtml(hit.properties.colour || '#888')}"
            class="inline-block size-2 rounded-full"></span>
      ${escapeHtml(line.emoji || '')}
      ${escapeHtml(line.short_name || '')} ${escapeHtml(line.line_name || '')}
    </p>
    <p class="text-2xs text-ink-gray-5">${escapeHtml(
      __('{0} out right now', [running]),
    )}</p></div>`
}

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (one) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[one]))
}

function lineFeatures() {
  const features = []
  lines.value.forEach((line, at) => {
    if (!line.shape?.coordinates?.length) return
    features.push({
      type: 'Feature',
      geometry: line.shape,
      properties: {
        name: line.name,
        colour: lineInk(line, at),
        dimmed: onlyLine.value && onlyLine.value !== line.name ? 1 : 0,
      },
    })
  })
  return { type: 'FeatureCollection', features }
}

function stopFeatures() {
  return {
    type: 'FeatureCollection',
    features: stops.value
      .filter((one) => one.latitude || one.longitude)
      .map((one) => ({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [one.longitude, one.latitude] },
        properties: {
          name: one.name,
          label: one.stop_name,
          emoji: one.emoji || '',
          status: one.status,
          // How many lines have actually been seen here — observed, not
          // declared. See `network.py`'s `_served`.
          served: one.served || 0,
        },
      })),
  }
}

// Filtering repaints the routes rather than removing them, so the one being
// looked at stands out of its network instead of standing alone.
watch(onlyLine, () => {
  if (map?.getSource('lines')) map.getSource('lines').setData(lineFeatures())
})

watch(playing, (on) => {
  clearInterval(ticker)
  if (!on) return
  ticker = setInterval(() => {
    const step = (PLAY_STEP * speed.value * 1000) / (DAY_END - DAY_START)
    const next = position.value + step
    if (next >= 1000) {
      position.value = 1000
      playing.value = false
    } else {
      position.value = next
    }
    pull()
  }, PLAY_EVERY)
})

onMounted(async () => {
  try {
    const [drawnNetwork, when, choices, styles] = await Promise.all([
      network.shape(), network.days(), network.offered(), network.markerStyles(),
    ])
    lines.value = drawnNetwork.lines || []
    stops.value = drawnNetwork.stops || []
    days.value = when.days || []
    day.value = days.value[0]?.day || ''
    offered.value = choices.facets || []
    markerStyles.value = styles.styles || []
    mayStyle.value = !!styles.may_write

    for (const line of lines.value) {
      const shape = prepare(line.shape)
      if (shape) shapes.set(line.name, shape)
    }

    ready.value = true
    if (!lines.value.length) return

    await draw()
    await pull()

    // After `draw`, because choosing an overlay paints one and there is nothing
    // to paint on until the map is up.
    const asked = String(route.query.overlay || '')
    if (asked && asked !== 'none' && OVERLAYS.some((one) => one.key === asked)) overlay.value = asked

    // The scrubber's own track, which is the aggregate tier read for a second
    // purpose — the same numbers the Insights screen plots. Fetched after the
    // map is up because nothing on this screen waits for it.
    network.rhythm({ days_back: 30 })
      .then((answer) => { service.value = answer.service_by_hour || [] })
      .catch(() => {})

    // Nothing running right now — night, a weekend, or a workspace whose feed
    // has stopped. Rather than an empty map with a Live badge on it, drop into
    // replay at the busiest part of the most recent day it has. An operator
    // opening this at three in the morning should see their network, not a
    // grey rectangle that is technically correct.
    if (!drawn.value.length && days.value.length) {
      livemode.value = false
      position.value = Math.round(((8 * 60 + 30 - DAY_START) / (DAY_END - DAY_START)) * 1000)
      await pull()
    }

    frame = requestAnimationFrame(paint)
    poller = setInterval(() => {
      tickWallClock()
      if (livemode.value) pull()
    }, LIVE_EVERY)
  } catch {
    failed.value = true
    ready.value = true
  }
})

onBeforeUnmount(() => {
  sizes?.disconnect()
  clearInterval(poller)
  clearInterval(ticker)
  clearTimeout(scrubbing)
  cancelAnimationFrame(frame)
  map?.remove()
  map = null
})
</script>

<style scoped>
/*
 * A native range with its own paint turned off.
 *
 * The scrubber's track is the SVG above it — hours of service, and where in
 * the day the handle is — so the input contributes the gesture and nothing
 * visible. There is no way to say that in utility classes: a range's track and
 * thumb are shadow pseudo-elements, and `appearance-none` alone leaves the
 * thumb drawn.
 */
.scrub::-webkit-slider-runnable-track { background: transparent; height: 100%; }
.scrub::-moz-range-track { background: transparent; height: 100%; }
.scrub::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 18px;
  height: 28px;
  background: transparent;
  cursor: grab;
}
.scrub::-moz-range-thumb {
  width: 18px;
  height: 28px;
  border: 0;
  background: transparent;
  cursor: grab;
}
.scrub:active::-webkit-slider-thumb { cursor: grabbing; }
.scrub:disabled { cursor: default; }
</style>
