<template>
  <!--
    What this reads, said plainly enough to settle an argument.

    VDV is a shelf of specifications written by different committees over
    thirty years, and the expensive moment in a German integration is week six,
    when it turns out the part the customer meant is not the part that was
    built. So this screen is the shelf: every part, what it carries, and — the
    column nobody else writes down — **which door it arrives through**.

    That door column is the whole reason this is a screen and not a paragraph.
    "Do you support 301-2-15" sounds like a question about a parser. It is a
    question about a bridge on every vehicle, because IBIS-IP is device-to-
    device on one bus and a workspace never sees it directly. Answering yes
    without saying that is how a project loses a quarter.

    The rows are shipped knowledge, not the workspace's data — `onemobility/
    vdv.py` — so nothing here changes between two loads, and the honest parts
    are the unflattering ones: a part we have not established says so.
  -->
  <div class="h-full min-h-[28rem] w-full overflow-y-auto" data-slot="protocols">
    <div class="mx-auto flex max-w-5xl flex-col gap-5 p-1">
      <div class="flex flex-col gap-2">
        <p class="text-p-base text-ink-gray-7">
          {{ __('Every VDV part this reads, and every one it does not yet.') }}
        </p>
        <div class="flex flex-wrap items-center gap-2" data-slot="protocols-counts">
          <Badge
            v-for="one in tally"
            :key="one.state"
            :theme="STATE_THEME[one.state]"
            variant="subtle"
            :label="one.label"
          />
        </div>
      </div>

      <!-- The three doors, above the table rather than only as a column,
           because the distinction is the thing to read first. -->
      <div class="grid gap-3 sm:grid-cols-3" data-slot="protocols-doors">
        <div
          v-for="one in doorCards"
          :key="one.door"
          class="flex flex-col gap-1 rounded-6 border border-outline-gray-2 p-3"
        >
          <div class="flex items-center gap-2">
            <Icon :name="DOOR_ICON[one.door]" class="size-4 text-ink-gray-5" />
            <span class="text-p-sm font-medium text-ink-gray-8">{{ DOOR_LABEL[one.door] }}</span>
            <span class="ms-auto text-p-xs text-ink-gray-5">{{ one.count }}</span>
          </div>
          <p class="text-p-xs text-ink-gray-5">{{ one.says }}</p>
        </div>
      </div>

      <div v-if="!ready" class="flex flex-col gap-2">
        <Skeleton v-for="n in 6" :key="n" class="h-12 w-full" />
      </div>

      <div v-for="family in families" :key="family" class="flex flex-col gap-2">
        <p class="text-p-xs font-medium uppercase tracking-wide text-ink-gray-5">
          {{ family }}
        </p>
        <div
          v-for="one in byFamily[family]"
          :key="one.part"
          data-slot="protocol-row"
          class="flex flex-col gap-1 rounded-6 border border-outline-gray-2 p-3"
        >
          <div class="flex flex-wrap items-center gap-2">
            <span class="font-mono text-p-sm text-ink-gray-8">{{ one.part }}</span>
            <span class="min-w-0 flex-1 truncate text-p-sm text-ink-gray-7">{{ one.title }}</span>
            <Badge
              :theme="STATE_THEME[one.state]"
              variant="subtle"
              :label="STATE_LABEL[one.state]"
            />
            <Tooltip :text="DOOR_LABEL[one.door]">
              <Icon :name="DOOR_ICON[one.door]" class="size-4 text-ink-gray-5" />
            </Tooltip>
          </div>

          <p v-if="one.carries" class="text-p-xs text-ink-gray-6">{{ one.carries }}</p>
          <p v-if="one.note" class="text-p-xs text-ink-gray-5">{{ one.note }}</p>

          <div class="flex flex-wrap items-center gap-3">
            <a
              v-if="one.spec"
              :href="one.spec"
              target="_blank"
              rel="noopener noreferrer"
              class="text-p-xs text-ink-blue-3 hover:underline"
            >
              {{ __('The specification') }}
            </a>
            <!-- The flag that makes the rest of the row worth believing: a row
                 written from working knowledge is one to re-read before
                 anybody writes a parser against it. -->
            <span v-if="!one.verified" class="text-p-xs text-ink-amber-3">
              {{ __('Written from working knowledge, not from the document.') }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Badge, Icon, Skeleton, Tooltip } from '@/ui'
import { network } from '@/modules/onemobility/lib/api'
import { __ } from '@/shared/lib/runtime/translate'

const STATE_THEME = {
  read: 'green',
  recognised: 'blue',
  declared: 'gray',
  unknown: 'amber',
}

const STATE_LABEL = {
  read: __('Read'),
  recognised: __('Recognised'),
  declared: __('Not read'),
  unknown: __('Not established'),
}

const DOOR_ICON = {
  folder: 'lucide-folder',
  stream: 'lucide-radio',
  vehicle: 'lucide-bus',
}

const DOOR_LABEL = {
  folder: __('A file, in a folder'),
  stream: __('A subscription'),
  vehicle: __('On the vehicle'),
}

const shelf = ref(null)
const ready = computed(() => Boolean(shelf.value))

const parts = computed(() => shelf.value?.parts || [])
const families = computed(() => shelf.value?.families || [])

const byFamily = computed(() => {
  const out = {}
  for (const one of parts.value) {
    ;(out[one.family] ||= []).push(one)
  }
  return out
})

const tally = computed(() =>
  Object.entries(shelf.value?.counts || {}).map(([state, count]) => ({
    state,
    label: `${count} ${STATE_LABEL[state] || state}`,
  })),
)

const doorCards = computed(() =>
  Object.entries(shelf.value?.doors || {}).map(([door, says]) => ({
    door,
    says,
    count: parts.value.filter((one) => one.door === door).length,
  })),
)

onMounted(async () => {
  shelf.value = await network.coverage().catch(() => null)
})
</script>
