<template>
  <div class="mx-auto max-w-5xl p-8">
    <div class="flex items-center gap-2 text-sm text-gray-600">
      <router-link to="/" class="hover:text-gray-900">Apps</router-link>
      <span>/</span>
      <span class="text-gray-900">{{ app?.app_label || appCode }}</span>
    </div>

    <h1 class="mt-2 text-xl font-semibold">{{ app?.app_label || appCode }}</h1>

    <div class="mt-6 rounded-lg border border-dashed border-gray-300 p-10 text-center">
      <p class="text-sm text-gray-600">
        This app's interface hasn't been built yet.
      </p>
      <p class="mt-1 text-xs text-gray-500">Module: {{ app?.module || '—' }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { session } from '../lib/session'

const props = defineProps({ appCode: { type: String, required: true } })
const app = computed(() =>
  (session.apps || []).find((a) => a.app_code === props.appCode),
)
</script>
