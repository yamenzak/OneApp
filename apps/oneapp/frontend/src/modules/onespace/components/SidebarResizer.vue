<template>
  <!--
    The handle on the one sidebar, and the reason it is its own component: four
    rails fill that slot — spaces, mail, files, the diary — and all four had the
    same ten lines with the same nine props. Four copies of a floor and a
    ceiling is four places for them to disagree, which is the page jumping when
    you open mail.

    Hidden while collapsed: a collapsed sidebar is one width by definition, and
    a handle that resizes something to a size it will not take does nothing.
  -->
  <Resizer
    v-if="!collapsed"
    v-model="width"
    :min="MIN"
    :default-size="DEFAULT"
    :max="MAX"
    side="right"
    :label="__('the sidebar')"
    remember="sidebar"
    slot-name="sidebar-resizer"
  />
</template>

<script setup>
import Resizer from '@/shared/components/Resizer.vue'
import { DEFAULT, MAX, MIN, useSidebar } from '@/modules/onespace/lib/shell/sidebar'
import { __ } from '@/shared/lib/runtime/translate'

const { collapsed, width } = useSidebar()
</script>
