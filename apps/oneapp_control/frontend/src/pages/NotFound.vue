<template>
  <div class="grid min-h-[60vh] place-items-center p-8 text-center">
    <div>
      <p class="text-p-lg font-medium">Page not found</p>
      <Button class="mt-3" label="Back to tenants" @click="$router.push('/tenants')" />
    </div>
  </div>
</template>

<script setup>
import { Button } from '@/ui'
</script>
