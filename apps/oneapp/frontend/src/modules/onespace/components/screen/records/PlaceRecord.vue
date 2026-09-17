<template>
  <!--
    A place a check-in is allowed to happen at.

    The third entry in the record-view library that exists because the form
    alone is wrong for the thing. A geofence is a position, a distance and a
    network, and typing any of the three is both tedious and the step where it
    gets set up wrong — a latitude with the sign flipped is a circle in the
    wrong hemisphere and nothing says so until somebody cannot check in.

    So both are offered rather than asked for. The position comes from the
    browser, which is standing in the office when a manager sets this up; the
    network comes from the server, which sees where the request arrived from.
    Neither is forced: they fill the fields the form below still owns, so what
    was detected is editable in the same place everything else is.
  -->
  <RecordPage name="place">
    <div
      class="flex flex-col gap-1 border-b border-outline-gray-2 bg-surface-gray-1 px-4 py-5 md:px-6"
    >
      <h2 data-slot="place-name" class="truncate text-xl-semibold text-ink-primary">
        {{ title }}
      </h2>
      <p data-slot="place-rule" class="text-sm text-ink-secondary">{{ rule }}</p>

      <!--
        The workspace-wide switch, said here because a radius with it off is a
        circle nothing reads. HRMS's own setting, and it is global rather than
        per-place: with it on, every check-in has to carry a position.
      -->
      <p v-if="radius && !tracking" class="mt-1 flex items-center gap-1.5 text-sm text-ink-amber-3">
        <Icon name="lucide-triangle-alert" class="size-3.5 shrink-0" />
        {{ __('Not checked: this workspace does not record positions.') }}
      </p>
    </div>

    <div class="flex flex-col gap-5 border-b border-outline-gray-2 px-4 py-4 md:flex-row md:gap-10 md:px-6">
      <!-- Where it is. -->
      <div class="flex min-w-0 flex-1 flex-col gap-2">
        <p class="text-xs text-ink-muted">{{ __('Where it is') }}</p>
        <p data-slot="place-position" class="text-base-medium tabular-nums text-ink-primary">
          {{ position || '—' }}
        </p>
        <Button
          v-if="canWrite"
          class="w-fit"
          data-slot="place-here"
          variant="subtle"
          icon-left="lucide-crosshair"
          :loading="locating"
          :label="position ? __('Move it to where I am') : __('Use where I am')"
          @click="useHere"
        />
        <p v-if="refused" class="text-xs text-ink-amber-3">{{ refused }}</p>
      </div>

      <!-- And which networks it answers to. -->
      <div class="flex min-w-0 flex-1 flex-col gap-2">
        <p class="text-xs text-ink-muted">{{ __('Networks it accepts') }}</p>
        <ul v-if="networks.length" data-slot="place-networks" class="flex flex-col gap-1">
          <li
            v-for="one in networks"
            :key="one"
            class="truncate text-base-medium tabular-nums text-ink-primary"
          >{{ one }}</li>
        </ul>
        <p v-else data-slot="place-networks" class="text-base-medium text-ink-gray-4">
          {{ __('Anywhere') }}
        </p>
        <Button
          v-if="canWrite"
          class="w-fit"
          data-slot="place-network"
          variant="subtle"
          icon-left="lucide-wifi"
          :loading="asking"
          :label="__('Add the network I am on')"
          @click="useNetwork"
        />
        <!--
          Said once, here, because it is the thing everybody assumes otherwise.
          A browser cannot read a wifi name — there is no web API for it — so
          what is checked is the address a request arrives from, which for an
          office is its public egress.
        -->
        <p class="text-xs text-ink-muted">
          {{ __('The address your office reaches us from. A browser cannot read a wifi name.') }}
        </p>
      </div>
    </div>
  </RecordPage>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import { Button, Icon } from '@/ui'
import RecordPage from '@/modules/onespace/components/screen/records/RecordPage.vue'
import { workspace } from '@/shared/lib/workspace'
import { notifyError } from '@/shared/lib/runtime/notify'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  record: { type: Object, required: true },
  spec: { type: Object, default: () => ({}) },
  showcase: { type: Object, default: () => ({}) },
  title: { type: String, default: '' },
  compact: { type: Boolean, default: false },
  revision: { type: Number, default: 0 },
  canWrite: { type: Boolean, default: false },
})

// `update:field` rather than a save: a record view places controls and never
// writes through them — the host owns the form and the save loop, and what
// these two buttons do is fill in fields somebody then looks at and saves.
const emit = defineEmits(['open', 'update:field'])

/** HRMS's own names for the three. */
const LATITUDE = 'latitude'
const LONGITUDE = 'longitude'
const RADIUS = 'checkin_radius'
const NETWORKS = 'custom_checkin_networks'

/** How precisely a position is written down. Five places is about a metre,
 *  which is finer than any geofence and far finer than any phone's fix. */
const PLACES = 5

const locating = ref(false)
const asking = ref(false)
const refused = ref('')

/**
 * What this workspace does about positions, and where this reader is on the
 * network — one call, because the page wants both and neither is on the record.
 *
 * Read once when the page opens. The address does not change while somebody
 * is looking at a form, and the switch is a workspace setting.
 */
const policy = ref({})
onMounted(async () => {
  policy.value = (await workspace.networkHere()) || {}
})

const radius = computed(() => Number(props.record?.[RADIUS]) || 0)
const tracking = computed(() => !!policy.value.tracking)

const position = computed(() => {
  const lat = props.record?.[LATITUDE]
  const lon = props.record?.[LONGITUDE]
  if (!Number.isFinite(Number(lat)) || !Number.isFinite(Number(lon))) return ''
  if (!Number(lat) && !Number(lon)) return ''
  return `${Number(lat).toFixed(PLACES)}, ${Number(lon).toFixed(PLACES)}`
})

const networks = computed(() =>
  String(props.record?.[NETWORKS] || '')
    .split('\n')
    .map((one) => one.trim())
    .filter(Boolean),
)

/** What this place demands, as a sentence rather than three numbers. */
const rule = computed(() => {
  const within = radius.value
    ? __('within {0} m', [String(radius.value)])
    : ''
  const on = networks.value.length
    ? __('on one of its networks')
    : ''
  if (!within && !on) {
    return __('Anyone assigned here can check in from anywhere.')
  }
  return __('Assigned here means checking in {0}.',
    [[within, on].filter(Boolean).join(__(' and '))])
})

/**
 * Where the browser thinks it is.
 *
 * Asked for on a press rather than on load: a page that demanded the location
 * permission to be *read* is a page people refuse once and then cannot use.
 * A refusal is a sentence under the button, not a toast — it is about this
 * control and nothing else on the page.
 */
const useHere = () => {
  refused.value = ''
  if (!navigator.geolocation) {
    refused.value = __('This browser will not say where it is.')
    return
  }
  locating.value = true
  navigator.geolocation.getCurrentPosition(
    ({ coords }) => {
      locating.value = false
      emit('update:field', { field: LATITUDE, value: Number(coords.latitude.toFixed(PLACES)) })
      emit('update:field', { field: LONGITUDE, value: Number(coords.longitude.toFixed(PLACES)) })
    },
    () => {
      locating.value = false
      // Not "an error". Refusing to share a position is a choice, and the
      // fields are still typeable — which is the sentence to say.
      refused.value = __('No position shared. Type one below.')
    },
    { enableHighAccuracy: true, timeout: 10_000 },
  )
}

/**
 * And where the server sees this request coming from.
 *
 * Appended rather than replacing: an office with two lines has two addresses,
 * and a control that overwrote the list would make the second one delete the
 * first.
 */
const useNetwork = async () => {
  asking.value = true
  try {
    const { address } = (await workspace.networkHere()) || policy.value
    if (!address) {
      notifyError(new Error(__('No network address seen.')))
      return
    }
    if (networks.value.includes(address)) return
    emit('update:field', {
      field: NETWORKS,
      value: [...networks.value, address].join('\n'),
    })
  } finally {
    asking.value = false
  }
}
</script>
