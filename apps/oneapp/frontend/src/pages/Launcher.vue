<template>
  <div class="mx-auto max-w-5xl p-8">
    <h1 class="text-xl font-semibold">Your apps</h1>
    <p class="mt-1 text-sm text-gray-600">
      Everything enabled for {{ session.tenant?.name || 'this workspace' }}.
    </p>

    <div v-if="apps.length" class="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <router-link
        v-for="app in apps"
        :key="app.app_code"
        :to="`/app/${app.app_code}`"
        class="group rounded-lg border border-gray-200 bg-white p-4 transition hover:border-gray-300 hover:shadow-sm"
      >
        <div class="flex items-start gap-3">
          <span
            class="grid h-9 w-9 shrink-0 place-items-center rounded bg-gray-100 text-sm font-medium"
          >
            {{ app.app_label?.[0] || '?' }}
          </span>
          <div class="min-w-0">
            <p class="truncate font-medium">{{ app.app_label }}</p>
            <p v-if="app.description" class="mt-0.5 line-clamp-2 text-xs text-gray-600">
              {{ app.description }}
            </p>
          </div>
        </div>
      </router-link>
    </div>

    <div
      v-else
      class="mt-6 rounded-lg border border-dashed border-gray-300 p-10 text-center"
    >
      <p class="text-sm font-medium">No apps yet</p>
      <p class="mx-auto mt-1 max-w-sm text-sm text-gray-600">
        Nothing has been enabled for this workspace. If you were expecting something
        here, get in touch and we'll sort it out.
      </p>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { session } from '../lib/session'

const apps = computed(() => session.apps || [])
</script>
