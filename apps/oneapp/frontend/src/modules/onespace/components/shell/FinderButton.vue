<template>
  <!--
    The visible half of Ctrl+K.

    A shortcut nobody is told about is a shortcut two people use. This says its
    own key, so the second time somebody wants it they do not reach for the
    mouse.

    At the start of the dock, which is that row's own rule: everything at the
    start is somewhere to go or something to open. Divided off from the app
    tiles because it is not an app — and not in the corner, which is 48px tall
    with the switcher already filling it.
  -->
  <Button
    variant="subtle"
    icon-left="lucide-search"
    :label="__('Find')"
    :tooltip="__('Find anything, anywhere')"
    data-slot="finder-open"
    @click="openFinder(route.params?.spaceCode || '')"
  >
    <template #suffix>
      <KeyboardShortcut combo="Mod+K" class="hidden md:inline-flex" />
    </template>
  </Button>
</template>

<script setup>
import { useRoute } from 'vue-router'

import { Button, KeyboardShortcut } from '@/ui'

import { openFinder } from '@/modules/onespace/lib/shell/finding'
import { __ } from '@/shared/lib/runtime/translate'

const route = useRoute()
</script>
