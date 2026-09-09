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
        What the colours mean. Occupancy is an ordinal state with a name for
        each step — seats free, standing, crush — and a legend is what keeps it
        from being colour alone, which is the one thing a fleet map must not
        be.
      -->
      <div
        class="pointer-events-auto absolute bottom-[7.5rem] start-4 z-10 rounded-6 border border-outline-gray-2 bg-surface-elevation-2 shadow-sm"
        data-slot="network-legend"
      >
        <button
          type="button"
          class="flex w-full items-center gap-2 px-3 py-2 text-sm font-medium text-ink-gray-7"
          @click="legendOpen = !legendOpen"
        >
          <Icon :name="legendOpen ? 'lucide-chevron-down' : 'lucide-chevron-right'" class="size-3.5" />
          {{ __('How full') }}
        </button>
        <div v-show="legendOpen" class="flex flex-col gap-1.5 px-3 pb-3">
          <div
            v-for="band in occupancy"
            :key="band.key"
            class="flex items-center gap-2 text-xs text-ink-gray-6"
          >
            <span
              class="size-2.5 shrink-0 rounded-full ring-2 ring-outline-elevation-2"
              :style="{ backgroundColor: band.ink }"
            />
            <span>{{ band.label }}</span>
            <span v-if="band.floor > 0" class="ms-auto tabular-nums text-ink-gray-4">
              {{ band.floor }}%+
            </span>
          </div>
          <div class="mt-1 flex items-center gap-2 border-t border-outline-gray-1 pt-2 text-xs text-ink-gray-6">
            <span class="size-2.5 shrink-0 rounded-full border-2 border-outline-amber-3 bg-surface-elevation-2" />
            <span>{{ __('Stop nobody declared') }}</span>
          </div>
        </div>
      </div>

      <!--
        One vehicle, opened. Its day is fetched and drawn behind it, which is
        the whole of "where has this thing been" and is a question a dispatcher
        asks before any other.
      -->
      <div
        v-if="chosen"
        class="pointer-events-auto absolute end-4 top-[5.5rem] z-10 w-64 rounded-6 border border-outline-gray-2 bg-surface-elevation-2 p-3 shadow-lg"
        data-slot="network-vehicle"
      >
        <div class="flex items-start gap-2">
          <span
            class="mt-0.5 inline-flex h-5 shrink-0 items-center rounded-4 px-1.5 text-xs font-semibold text-white"
            :style="{ backgroundColor: inkOfLine(chosen.line) }"
          >{{ shortNameOf(chosen.line) }}</span>
          <div class="min-w-0 flex-1">
            <p class="truncate text-sm font-medium text-ink-gray-8">{{ chosen.vehicle }}</p>
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

        <Button
          class="mt-3 w-full"
          :variant="following ? 'solid' : 'subtle'"
          :label="following ? __('Following') : __('Follow it')"
          icon-left="lucide-crosshair"
          @click="following = !following"
        />
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
          <Select
            v-model="onlyLine"
            :options="lineOptions"
            :placeholder="__('Every line')"
            class="w-44"
          />

          <div class="ms-auto flex items-center gap-3">
            <!-- The fleet's occupancy mix, as one bar. Four seconds of glance
                 answers "is the network under pressure right now". -->
            <div class="hidden items-center gap-1.5 sm:flex" data-slot="network-mix">
              <div class="flex h-2 w-24 overflow-hidden rounded-full bg-surface-gray-2">
                <div
                  v-for="part in mix"
                  :key="part.key"
                  class="h-full"
                  :style="{ width: `${part.share}%`, backgroundColor: part.ink }"
                  :title="`${part.label}: ${part.count}`"
                />
              </div>
              <span class="tabular-nums text-xs text-ink-gray-5">
                {{ __('{0} vehicles', [String(drawn.length)]) }}
              </span>
            </div>

            <div class="flex items-baseline gap-2">
              <span class="tabular-nums text-xl font-semibold leading-none text-ink-gray-9">
                {{ clockLabel }}
              </span>
              <Badge v-if="livemode" theme="green" :label="__('Live')" />
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
              :opacity="bar.past ? 0.5 : 0.2"
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

import { Badge, Button, Icon, Select } from '@/ui'
import EmptyState from '@/shared/components/EmptyState.vue'
import { __ } from '@/shared/lib/runtime/translate'
import { network } from '@/modules/onemobility/lib/api'
import { between, blend, prepare } from '@/modules/onemobility/lib/motion'
import { bearingBetween, easeBearing, vehicleMarker } from '@/modules/onemobility/lib/markers'
import {
  casingInk,
  delayInk,
  lineInk,
  occupancyBand,
  occupancyInk,
  occupancyScale,
  OCCUPANCY,
} from '@/modules/onemobility/lib/palette'
import { tokenInk } from '@/modules/onespace/lib/screen/ink'
import { attribution, quietTiles, styleFor, whenLoaded } from '@/modules/onespace/lib/screen/basemap'

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
const ready = ref(false)
const failed = ref(false)
const lines = ref([])
const stops = ref([])
const days = ref([])
const day = ref('')
const onlyLine = ref('')
const livemode = ref(true)
const position = ref(1000)
const drawn = ref([])
const service = ref([])
const legendOpen = ref(true)
const selected = ref('')
const following = ref(false)
const playing = ref(false)
const speed = ref(1)

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

const occupancy = computed(() => occupancyScale())
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

const dayOptions = computed(() =>
  days.value.map((one) => ({ label: one.day, value: one.day }))
)
const lineOptions = computed(() => [
  { label: __('Every line'), value: '' },
  ...lines.value.map((one) => ({ label: `${one.short_name} · ${one.line_name}`, value: one.name })),
])

const minuteOfDay = computed(
  () => DAY_START + ((DAY_END - DAY_START) * position.value) / 1000
)
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
  }))
})

const handleX = computed(() => (position.value / 1000) * TRACK_W)

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

/** The moment being asked about: empty for now, else a date and a time. */
function moment() {
  if (livemode.value || !day.value) return ''
  const total = Math.round(minuteOfDay.value)
  const hh = String(Math.floor(total / 60)).padStart(2, '0')
  const mm = String(total % 60).padStart(2, '0')
  return `${day.value} ${hh}:${mm}:00`
}

async function pull() {
  try {
    const params = { when: moment() }
    if (onlyLine.value) params.line = onlyLine.value
    const answer = await network.at(params)
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
    const along = between(shape, previous, latest, k) || [latest.lon, latest.lat]
    // Ease onto the computed point rather than teleporting when a poll lands.
    const was = painted.get(vehicle)
    const at = blend(was, along, span ? 0.25 : 1)
    painted.set(vehicle, at)

    // Which way it is facing, from where it has just been. Eased the short way
    // round, so a vehicle crossing north does not spin through the compass.
    const heading = easeBearing(headings.get(vehicle), bearingBetween(was, at), span ? 0.3 : 1)
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
watch(onlyLine, () => pull())

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
function registerMarkers() {
  const ring = casingInk()
  const ratio = Math.min(3, Math.max(1, window.devicePixelRatio || 1))
  for (const band of OCCUPANCY) {
    const id = `vehicle-${band.key}`
    if (map.hasImage(id)) map.removeImage(id)
    map.addImage(
      id,
      vehicleMarker(occupancyInk(band.floor < 0 ? -1 : band.floor), ring, ratio),
      // `pixelRatio` is style-image *metadata* and belongs in the third
      // argument. Passed inside the image it is silently ignored, and every
      // marker draws at twice the size it was meant to.
      { pixelRatio: ratio },
    )
  }
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
    style: styleFor(ground()),
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

  registerMarkers()

  const casing = casingInk()
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
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 4, 14, 6, 16, 8],
      'circle-color': casing,
      'circle-stroke-width': ['interpolate', ['linear'], ['zoom'], 10, 2, 14, 2.5, 16, 3],
      // An inferred stop — one a vehicle stopped at and no feed declared — is
      // drawn differently and never quietly promoted into the network.
      'circle-stroke-color': [
        'case',
        ['==', ['get', 'status'], 'Inferred'], tokenInk('--ink-amber-3', '#f59e0b'),
        tokenInk('--ink-gray-7', '#3f3f46'),
      ],
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
      'icon-image': ['concat', 'vehicle-', ['get', 'band']],
      'icon-size': ['interpolate', ['linear'], ['zoom'], 10, 0.9, 14, 1.1, 16, 1.3],
      'icon-rotate': ['get', 'bearing'],
      'icon-rotation-alignment': 'map',
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
    },
    // A stale position is drawn faint. Never as though it were live.
    paint: { 'icon-opacity': ['case', ['==', ['get', 'stale'], 1], 0.4, 1] },
  })

  map.on('click', 'vehicles', (event) => {
    const hit = event.features?.[0]
    if (hit?.properties?.vehicle) choose(hit.properties.vehicle)
  })
  map.on('mouseenter', 'vehicles', () => { map.getCanvas().style.cursor = 'pointer' })
  map.on('mouseleave', 'vehicles', () => { map.getCanvas().style.cursor = '' })

  // A stop says its name on hover. There is no text layer available — the
  // style carries no `glyphs` URL and MapLibre needs one for any label — so
  // the name is an HTML popup, which is better anyway: it wears the product's
  // own type rather than a font baked into a tileset.
  const popup = new library.Popup({ closeButton: false, closeOnClick: false, offset: 10 })
  map.on('mouseenter', 'stops', (event) => {
    const hit = event.features?.[0]
    if (!hit) return
    map.getCanvas().style.cursor = 'pointer'
    popup
      .setLngLat(hit.geometry.coordinates)
      .setHTML(`<span class="text-xs font-medium">${escapeHtml(hit.properties.label || '')}</span>`)
      .addTo(map)
  })
  map.on('mouseleave', 'stops', () => {
    map.getCanvas().style.cursor = ''
    popup.remove()
  })

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
        properties: { name: one.name, label: one.stop_name, status: one.status },
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
    const [drawnNetwork, when] = await Promise.all([network.shape(), network.days()])
    lines.value = drawnNetwork.lines || []
    stops.value = drawnNetwork.stops || []
    days.value = when.days || []
    day.value = days.value[0]?.day || ''

    for (const line of lines.value) {
      const shape = prepare(line.shape)
      if (shape) shapes.set(line.name, shape)
    }

    ready.value = true
    if (!lines.value.length) return

    await draw()
    await pull()

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
