<template>
  <!--
    The map: the same rows, drawn where they are.

    A view type rather than one space's screen, because "these records have a
    position" is a fact about a doctype and not about transit — a depot, an
    address, an incident and a stop are all this. What is *not* here is a live
    fleet with a time scrubber; that is a product surface and belongs to the
    space that has one. See `apps/oneapp/oneapp/onemobility/README.md` §7.

    MapLibre GL, BSD-3, loaded on demand: a workspace that never opens a map
    never pays for it.
  -->
  <div class="relative min-h-0 flex-1" data-slot="map">
    <EmptyState
      v-if="!placed"
      icon="lucide-map"
      :title="__('Nowhere to put a pin')"
      :description="__('This screen shows a map, but no field on it says where a record is.')"
    />
    <EmptyState
      v-else-if="ready && !features.length"
      icon="lucide-map-pin-off"
      :title="__('Nothing to place')"
      :description="__('None of these records has a position yet.')"
    />
    <!-- `v-show` and not `v-else`: the map draws into this element on mount,
         and an element `v-if` has removed is one the library holds a dead
         reference to the moment a filter empties the page. -->
    <!--
      `h-full w-full`, not `absolute inset-0`: maplibre-gl.css declares
      `.maplibregl-map { position: relative }` at the same specificity as
      Tailwind's `.absolute` and is loaded after it, so the moment the library's
      stylesheet arrives the container stops being positioned, `inset-0` stops
      meaning anything, and the height collapses to zero — a map drawn into
      MapLibre's 400x300 fallback canvas with no error said anywhere.
    -->
    <div v-show="placed && features.length" ref="canvas" class="h-full w-full" />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import EmptyState from '@/shared/components/EmptyState.vue'
import { valueTheme } from '@/modules/onespace/lib/screen/fields'
import { __ } from '@/shared/lib/runtime/translate'
import { featuresFrom } from '@/modules/onespace/lib/screen/place'
import { inkOf, tokenInk } from '@/modules/onespace/lib/screen/ink'
import { attribution, styleFor, whenLoaded } from '@/modules/onespace/lib/screen/basemap'

const props = defineProps({
  /** The resolved screen: columns, title field, states, permissions. */
  spec: { type: Object, required: true },
  /** The page of records, already fetched and shaped by the shell. */
  rows: { type: Array, default: () => [] },
  /**
   * Which fields hold the position, resolved by the server against the column
   * list and the fieldtype — handed down for the same reason the board's
   * column field is: the shell owns the request.
   */
  place: { type: Object, default: () => ({}) },
  /** Which record is open, so its pin can say so. */
  openRecord: { type: String, default: '' },
})

const emit = defineEmits(['open'])

const canvas = ref(null)
const ready = ref(false)
let map = null
let library = null
let sizes = null

const placed = computed(() => {
  const one = props.place || {}
  return Boolean(one.point_field || (one.lat_field && one.lon_field))
})

const features = computed(() =>
  featuresFrom(props.rows, props.place || {}, {
    label: (row) => String(row[props.place?.label_field] ?? row.name ?? ''),
    theme: (row) => {
      const field = props.place?.colour_field
      if (!field) return 'gray'
      return valueTheme(row[field], props.spec?.states || [])
    },
    ink: inkOf,
  })
)

/**
 * The ground, from `lib/screen/basemap.js` — the one place the product decides
 * where tiles come from. `place.style` still wins: a screen that names its own
 * style has said something more specific than the instance default.
 */
function ground(background) {
  return styleFor(background, props.place?.style || '')
}


function collection() {
  return { type: 'FeatureCollection', features: features.value }
}

function paint() {
  if (!map || !map.getSource('records')) return
  map.getSource('records').setData(collection())
}

/** Frame everything, unless there is only one thing, which frames badly. */
function frame() {
  if (!map || !library || !features.value.length) return
  const bounds = new library.LngLatBounds()
  for (const one of features.value) bounds.extend(one.geometry.coordinates)
  if (features.value.length === 1) {
    map.jumpTo({ center: features.value[0].geometry.coordinates, zoom: 13 })
    return
  }
  map.fitBounds(bounds, { padding: 48, duration: 0, maxZoom: 15 })
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
  if (map || !canvas.value || !placed.value || !features.value.length) return

  await whenSized(canvas.value)
  const module = await import('maplibre-gl')
  await import('maplibre-gl/dist/maplibre-gl.css')
  library = module.default || module

  // Through the canvas normaliser: the tokens are `oklch()`, which MapLibre's
  // style specification refuses and which fails the whole map, not one layer.
  const background = tokenInk('--surface-gray-1', '#f4f4f5')

  map = new library.Map({
    container: canvas.value,
    style: ground(background),
    center: props.place?.centre || [0, 20],
    zoom: props.place?.zoom || 1,
    attributionControl: { compact: true, customAttribution: attribution() },
  })
  map.addControl(new library.NavigationControl({ showCompass: false }), 'top-right')
  sizes = new ResizeObserver(() => map?.resize())
  sizes.observe(canvas.value)

  await whenLoaded(map, background)

  map.addSource('records', { type: 'geojson', data: collection() })
  map.addLayer({
    id: 'records-halo',
    type: 'circle',
    source: 'records',
    paint: {
      'circle-radius': ['case', ['==', ['get', 'name'], props.openRecord || ''], 13, 0],
      'circle-color': ['get', 'ink'],
      'circle-opacity': 0.25,
    },
  })
  map.addLayer({
    id: 'records',
    type: 'circle',
    source: 'records',
    paint: {
      'circle-radius': 6,
      'circle-color': ['get', 'ink'],
      'circle-stroke-width': 2,
      'circle-stroke-color': background,
    },
  })

  map.on('click', 'records', (event) => {
    const hit = event.features?.[0]
    if (hit?.properties?.name) emit('open', hit.properties.name)
  })
  map.on('mouseenter', 'records', () => { map.getCanvas().style.cursor = 'pointer' })
  map.on('mouseleave', 'records', () => { map.getCanvas().style.cursor = '' })

  frame()
  ready.value = true
}

onMounted(() => {
  ready.value = true
  draw()
})

watch(features, () => {
  if (!map) {
    draw()
    return
  }
  paint()
  frame()
})

watch(
  () => props.openRecord,
  (name) => {
    if (!map || !map.getLayer('records-halo')) return
    map.setPaintProperty('records-halo', 'circle-radius', [
      'case', ['==', ['get', 'name'], name || ''], 13, 0,
    ])
  }
)

onBeforeUnmount(() => {
  sizes?.disconnect()
  map?.remove()
  map = null
})
</script>
