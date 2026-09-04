<template>
  <!--
    Who else can see this record.

    Frappe's `DocShare`, and the reason to use it rather than invent something
    is what reads it: the framework folds shares into the permission condition
    of every list query, so a record shared with somebody becomes visible to
    them with nothing written anywhere else.

    The dialog's body is `SharePanel`, which is the same one the Drive uses on
    a file. What is here is the trigger — an avatar stack that says at a glance
    whether this record has been given away — and this screen's three calls.
  -->
  <span>
    <Button
      variant="ghost"
      data-slot="share"
      :aria-label="summary"
      @click="open()"
    >
      <span class="flex items-center gap-1.5">
        <AvatarStack v-if="people.length" :people="people" />
        <Badge
          v-else-if="everyone"
          label="Everyone"
          theme="blue"
          variant="subtle"
        />
        <Icon v-else name="lucide-plus" class="size-4 text-ink-gray-5" />
      </span>
    </Button>

    <Dialog v-model="showing" title="Share this record">
      <SharePanel
        :people="people"
        :everyone="everyone"
        :can-share="canShare"
        empty-text="Only people whose role already reaches this record can see it."
        :offer="offer"
        :save="save"
        :remove="remove"
        @shared="(result) => emit('shared', result)"
      />
    </Dialog>
  </span>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Badge, Button, Dialog, Icon } from '@/ui'
import AvatarStack from './AvatarStack.vue'
import SharePanel from '../../SharePanel.vue'
import { workspace } from '../../../lib/workspace'

const props = defineProps({
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  name: { type: String, required: true },
  people: { type: Array, default: () => [] },
  everyone: { type: Object, default: null },
  canShare: { type: Boolean, default: false },
})

const emit = defineEmits(['shared'])

const showing = ref(false)

const summary = computed(() => {
  if (props.everyone) return 'Shared with everyone on this workspace'
  if (props.people.length) {
    return `Shared with ${props.people.map((one) => one.label).join(', ')}`
  }
  return 'Share this record'
})

const open = () => {
  showing.value = true
}

const offer = (query) => workspace.shareable(props.spaceCode, props.screen, query)

const save = (what) =>
  workspace.setShare(props.spaceCode, props.screen, props.name, what)

const remove = (what) =>
  workspace.unshare(props.spaceCode, props.screen, props.name, what)
</script>
