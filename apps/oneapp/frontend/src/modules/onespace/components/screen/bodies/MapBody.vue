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
    <div v-show="placed && features.length" ref="canvas" class="absolute inset-0" />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import EmptyState from '@/shared/components/EmptyState.vue'
import { valueTheme } from '@/modules/onespace/lib/screen/fields'
import { __ } from '@/shared/lib/runtime/translate'
import { featuresFrom } from '@/modules/onespace/lib/screen/place'
import { inkOf } from '@/modules/onespace/lib/screen/ink'

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
 * A basemap, or an honest absence of one.
 *
 * The tiles are ours and self-hosted, so where they are is a deployment fact
 * rather than a workspace's choice — it arrives on the screen payload from
 * site config. With none configured the map still draws: a flat ground in the
 * surface colour, and the records on it. That is not a degraded mode to
 * apologise for, it is what a schematic looks like, and it means this works
 * offline, in a test, and on a bench nobody has pointed at a tile store.
 */
function styleFor(background) {
  const url = (props.place?.style || '').trim()
  if (url) return url
  return {
    version: 8,
    sources: {},
    layers: [{ id: 'ground', type: 'background', paint: { 'background-color': background } }],
  }
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

async function draw() {
  if (map || !canvas.value || !placed.value || !features.value.length) return

  const module = await import('maplibre-gl')
  await import('maplibre-gl/dist/maplibre-gl.css')
  library = module.default || module

  const ground = getComputedStyle(document.documentElement)
    .getPropertyValue('--surface-gray-1').trim() || '#f4f4f5'

  map = new library.Map({
    container: canvas.value,
    style: styleFor(ground),
    center: props.place?.centre || [0, 20],
    zoom: props.place?.zoom || 1,
    attributionControl: { compact: true },
  })
  map.addControl(new library.NavigationControl({ showCompass: false }), 'top-right')

  await new Promise((resolve) => map.on('load', resolve))

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
      'circle-stroke-color': ground,
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
  map?.remove()
  map = null
})
</script>
