<template>
  <!--
    The map's controls, as a rail of buttons under the zoom.

    They used to live in the legend, and a legend that is also a control panel
    is neither: it grew a Select, three switches and a scrollbar, and what a
    reader actually wanted from it — what does this colour mean — was below the
    fold. Every web map worth using puts its controls in the corner as icons and
    keeps the key as a key, and this is that.

    Icons rather than labels because each opens a panel that says everything in
    words the moment it is touched, and a rail of four labelled buttons is a
    sidebar the map does not have room for.
  -->
  <div
    class="pointer-events-auto absolute end-4 top-[5.5rem] z-10 flex flex-col gap-2"
    data-slot="map-controls"
  >
    <div class="flex flex-col overflow-hidden rounded-6 border border-outline-gray-2
                bg-surface-elevation-2 shadow-sm">
      <Popover v-model:open="layersOpen" align="end">
        <template #trigger>
          <Button
            variant="ghost"
            icon="lucide-layers"
            :tooltip="__('Layers')"
            :aria-label="__('Layers')"
            data-slot="layers-button"
          />
        </template>
        <template #default>
          <div class="flex w-[min(17rem,90vw)] flex-col gap-3 p-3">
            <!--
              One overlay at a time and not a stack of checkboxes: two of these
              are tiled surfaces and two are graduated circles, and any two at
              once is mud.
            -->
            <div class="flex flex-col gap-1.5" data-slot="overlay-picker">
              <p class="text-xs font-medium text-ink-gray-7">{{ __('Show over the map') }}</p>
              <Select
                :model-value="overlay"
                :options="overlayOptions"
                @update:model-value="(one) => emit('update:overlay', one)"
              />
              <p v-if="overlayNow.hint" class="text-xs leading-snug text-ink-gray-5">
                {{ overlayNow.hint() }}
              </p>
            </div>

            <!--
              And these three are independent, because they are different
              *things* — routes, stops, vehicles — rather than competing answers
              to one question.
            -->
            <div class="flex flex-col gap-2 border-t border-outline-gray-1 pt-3">
              <p class="text-xs font-medium text-ink-gray-7">{{ __('The network itself') }}</p>
              <Switch
                :model-value="showRoutes" size="sm" :label="__('Routes')"
                @update:model-value="(one) => emit('update:showRoutes', one)"
              />
              <Switch
                :model-value="showStops" size="sm" :label="__('Stops')"
                @update:model-value="(one) => emit('update:showStops', one)"
              />
              <Switch
                :model-value="showVehicles" size="sm" :label="__('Vehicles')"
                @update:model-value="(one) => emit('update:showVehicles', one)"
              />
            </div>
          </div>
        </template>
      </Popover>

      <!--
        The shape picker. On the map rather than in a settings screen because
        the thing being chosen is a picture, and a picture is chosen by looking
        at the map it lands on.
      -->
      <Popover v-model:open="shapesOpen" align="end">
        <template #trigger>
          <Button
            variant="ghost"
            icon="lucide-shapes"
            :tooltip="__('Marker shapes')"
            :aria-label="__('Marker shapes')"
            data-slot="shapes-button"
          />
        </template>
        <template #default>
          <MarkerPicker :styles="styles" :may-write="mayStyle" @pick="onPick" />
        </template>
      </Popover>
    </div>

    <!--
      Standing on its own, below the rail and only while it applies: leaving
      the map isolated is the easiest state to get stuck in, so the way out is
      a button in the open rather than a second click on the thing that started
      it.
    -->
    <Button
      v-if="isolated"
      variant="solid"
      icon-left="lucide-eye"
      :label="isolatedLabel"
      class="max-w-40"
      data-slot="isolate-clear"
      @click="emit('clear-isolate')"
    />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

import MarkerPicker from '@/modules/onemobility/components/MarkerPicker.vue'
import { overlayFor } from '@/modules/onemobility/lib/layers'
import { __ } from '@/shared/lib/runtime/translate'
import { Button, Popover, Select, Switch } from '@/ui'

const props = defineProps({
  overlay: { type: String, default: 'none' },
  overlayOptions: { type: Array, default: () => [] },
  showRoutes: { type: Boolean, default: true },
  showStops: { type: Boolean, default: true },
  showVehicles: { type: Boolean, default: true },
  /** `{ kind, name, label }` for whatever is being looked at alone, or null. */
  isolated: { type: Object, default: null },
  styles: { type: Array, default: () => [] },
  mayStyle: { type: Boolean, default: false },
})

const emit = defineEmits([
  'update:overlay',
  'update:showRoutes',
  'update:showStops',
  'update:showVehicles',
  'clear-isolate',
  'style',
])

const layersOpen = ref(false)
const shapesOpen = ref(false)

const overlayNow = computed(() => overlayFor(props.overlay))

const isolatedLabel = computed(() =>
  __('Only {0}', [props.isolated?.label || '']),
)

function onPick(one) {
  emit('style', one)
}
</script>
