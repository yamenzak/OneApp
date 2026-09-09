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
    `h-full` and not `flex-1`: a component screen is mounted inside the shell's
    own scroll container, which is not a flex column — so `flex-1` resolved to
    a height of zero and the map drew perfectly into nothing. `min-h` is the
    floor for the day somebody mounts this somewhere with no height at all.
  -->
  <div class="relative h-full min-h-[28rem] w-full" data-slot="network">
    <!--
      `h-full w-full`, not `absolute inset-0`: maplibre-gl.css declares
      `.maplibregl-map { position: relative }` at the same specificity as
      Tailwind's `.absolute` and is loaded after it, so the moment the library's
      stylesheet arrives the container stops being positioned, `inset-0` stops
      meaning anything, and the height collapses to zero — a map drawn into
      MapLibre's 400x300 fallback canvas with no error said anywhere.
    -->
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

    <!-- The clock. Past on the left, now on the right, one control. -->
    <div
      v-if="ready && lines.length"
      class="pointer-events-auto absolute inset-x-4 bottom-4 z-10 flex flex-col gap-2 rounded-6 border border-outline-gray-2 bg-surface-base p-3"
      data-slot="network-clock"
    >
      <div class="flex flex-wrap items-center gap-2">
        <Button
          :variant="livemode ? 'solid' : 'subtle'"
          :label="__('Live')"
          icon-left="radio"
          @click="goLive"
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
        <div class="ms-auto flex items-center gap-2 text-sm text-ink-gray-6">
          <span class="tabular-nums font-medium text-ink-gray-8">{{ clockLabel }}</span>
          <Badge v-if="livemode" theme="green" :label="__('Live')" />
          <Badge v-else theme="blue" :label="__('Replay')" />
          <span>{{ __('{0} vehicles', [String(drawn.length)]) }}</span>
        </div>
      </div>

      <!-- A range is the one native control with no frappe-ui equivalent and
           no sane substitute: a scrubber is a drag along a line, and a
           listbox of moments is not the same gesture. -->
      <input
        v-model.number="position"
        type="range"
        min="0"
        max="1000"
        class="h-1.5 w-full cursor-pointer rounded-full bg-surface-gray-3"
        :aria-label="__('Time of day')"
        :disabled="livemode"
        @input="onScrub"
      >
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { Badge, Button, Select } from '@/ui'
import EmptyState from '@/shared/components/EmptyState.vue'
import { __ } from '@/shared/lib/runtime/translate'
import { network } from '@/modules/onemobility/lib/api'
import { between, blend, prepare } from '@/modules/onemobility/lib/motion'
import { paintable, tokenInk } from '@/modules/onespace/lib/screen/ink'
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

let map = null
let library = null
let poller = null
let frame = null
let sizes = null
const shapes = new Map()
const seen = new Map()
const painted = new Map()

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
const clockLabel = computed(() => {
  if (livemode.value) return __('Now')
  const total = Math.round(minuteOfDay.value)
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
})

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
    const at = blend(painted.get(vehicle), along, span ? 0.25 : 1)
    painted.set(vehicle, at)

    features.push({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: at },
      properties: {
        vehicle,
        line: latest.line,
        stale: latest.stale ? 1 : 0,
        // Occupancy drives the colour, and -1 means nobody counted — which is
        // not empty and must not be drawn as empty.
        occupancy: latest.occupancy ?? -1,
      },
    })
  }

  map.getSource('vehicles').setData({ type: 'FeatureCollection', features })
  frame = requestAnimationFrame(paint)
}

function onScrub() {
  livemode.value = false
  scrubTo()
}

let scrubbing = null
function scrubTo(where) {
  if (where !== undefined) position.value = Math.round(where * 1000)
  // One request per settle, not one per pixel of drag.
  clearTimeout(scrubbing)
  scrubbing = setTimeout(pull, 120)
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
  position.value = 1000
  pull()
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

  map.addSource('lines', { type: 'geojson', data: lineFeatures() })
  map.addLayer({
    id: 'lines',
    type: 'line',
    source: 'lines',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': ['get', 'colour'], 'line-width': 4, 'line-opacity': 0.85 },
  })

  map.addSource('stops', { type: 'geojson', data: stopFeatures() })
  map.addLayer({
    id: 'stops',
    type: 'circle',
    source: 'stops',
    paint: {
      'circle-radius': 3.5,
      'circle-color': ground(),
      'circle-stroke-width': 2,
      // An inferred stop — one a vehicle stopped at and no feed declared — is
      // drawn differently and never quietly promoted into the network.
      'circle-stroke-color': [
        'case', ['==', ['get', 'status'], 'Inferred'], '#f59e0b', '#3f3f46',
      ],
    },
  })

  map.addSource('vehicles', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
  map.addLayer({
    id: 'vehicles',
    type: 'circle',
    source: 'vehicles',
    paint: {
      'circle-radius': 7,
      'circle-color': [
        'case',
        ['<', ['get', 'occupancy'], 0], '#94a3b8',
        ['>=', ['get', 'occupancy'], 80], '#dc2626',
        ['>=', ['get', 'occupancy'], 55], '#f59e0b',
        '#16a34a',
      ],
      // A stale position is drawn hollow. Never as though it were live.
      'circle-opacity': ['case', ['==', ['get', 'stale'], 1], 0.35, 1],
      'circle-stroke-width': 2,
      'circle-stroke-color': ground(),
    },
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
      padding: { top: 64, right: 64, bottom: 140, left: 64 },
      duration: 0,
      maxZoom: 14,
    })
  }
}

function lineFeatures() {
  const features = []
  for (const line of lines.value) {
    if (!line.shape?.coordinates?.length) continue
    features.push({
      type: 'Feature',
      geometry: line.shape,
      properties: { name: line.name, colour: paintable(line.colour, '#0284c7') },
    })
  }
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
    poller = setInterval(() => { if (livemode.value) pull() }, LIVE_EVERY)
  } catch {
    failed.value = true
    ready.value = true
  }
})

onBeforeUnmount(() => {
  sizes?.disconnect()
  clearInterval(poller)
  clearTimeout(scrubbing)
  cancelAnimationFrame(frame)
  map?.remove()
  map = null
})
</script>
