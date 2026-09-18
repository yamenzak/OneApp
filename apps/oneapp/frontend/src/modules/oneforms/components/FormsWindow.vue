<template>
  <!--
    OneForms on the desk.

    Wider than OneTask's and for the opposite reason: a task is a one-line
    thing and a form is a row with a state, an address and two verbs on it. Not
    as wide as the Drive, because the list is short by construction — a
    workspace has a handful of doors, not a filing cabinet.
  -->
  <DeskWindow
    v-if="onDesk(FORMS)"
    :id="FORMS"
    :title="nameOf('oneforms')"
    :width="640"
    :height="560"
    :min-width="420"
    :min-height="320"
    :tint="colourOf('oneforms')"
    @close="close(FORMS)"
  >
    <template #title>
      <BrandMark name="oneforms" class="size-4 shrink-0" />
      <SpaceName brand="oneforms" class="text-base" />
    </template>

    <div class="flex min-h-0 flex-1 flex-col overflow-hidden">
      <Forms />
    </div>
  </DeskWindow>
</template>

<script setup>
import DeskWindow from '@/modules/onespace/components/desk/DeskWindow.vue'
import BrandMark from '@/shared/components/brand/BrandMark.vue'
import SpaceName from '@/shared/components/brand/SpaceName.vue'
import Forms from '@/modules/oneforms/pages/Forms.vue'
import { FORMS } from '@/modules/oneforms/lib/window'
import { close, onDesk } from '@/modules/onespace/lib/desk/windows'
import { colourOf, nameOf } from '@/shared/lib/brand/naming'
</script>
