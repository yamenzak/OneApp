<template>
  <!--
    What a row is, in one cell.

    Frappe's list leads with the subject and nothing else competes with it, so
    this is the first column whatever else a person has chosen. The avatar comes
    from the doctype's own image field where it declares one; where it does not,
    Avatar draws initials from the id, which is still a more recognisable mark
    than a blank square.
  -->
  <div class="flex min-w-0 items-center gap-2">
    <Avatar :image="image" :label="plainText(title) || String(row.name)" shape="square" size="lg" />
    <!--
      A Button, still, now that the whole row opens the record (see
      `ListBody.openRow`). The row is a `div` — frappe-ui only renders it as a
      `button` when it carries its own click handler, and ours is on the cells
      — so a div is the one thing a keyboard cannot reach. This is that path,
      and it is also the visible affordance that the row leads somewhere.

      `@click.stop` because `openRow` already skips anything inside a control:
      without the stop this would open the record twice.
    -->
    <Button
      variant="ghost"
      class="min-w-0 flex-1 justify-start !px-1 !h-auto !py-1"
      :label="plainText(title) || String(row.name)"
      @click.stop="emit('open')"
    >
      <div class="flex min-w-0 flex-col items-start">
        <span class="truncate text-p-sm text-ink-gray-8">{{ plainText(title) || row.name }}</span>
        <!-- The id underneath, quietly: it is what a person quotes on the phone
             and never what they read first. Suppressed when the title is the
             id, which is most doctypes without a title field. -->
        <span v-if="title && title !== row.name" class="truncate text-p-xs text-ink-gray-5">
          {{ row.name }}
        </span>
      </div>
    </Button>
  </div>
</template>

<script setup>
import { plainText } from '../../lib/format'
import { computed } from 'vue'
import { Avatar, Button } from '@/ui'

const props = defineProps({
  row: { type: Object, required: true },
  titleField: { type: String, default: '' },
  imageField: { type: String, default: '' },
})
const emit = defineEmits(['open'])

const title = computed(() => (props.titleField ? props.row[props.titleField] : '') || '')
const image = computed(() => (props.imageField ? props.row[props.imageField] : '') || '')
</script>
