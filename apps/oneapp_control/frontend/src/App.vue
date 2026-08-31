<template>
  <!--
    Signup is a full-bleed page and always was: a visitor with no session has
    no workspaces to put in a rail and no sidebar worth showing. What changed
    is that it is now the *only* page here, so there is no shell to branch on.
  -->
  <FrappeUIProvider>
    <router-view :key="$route.fullPath" />
  </FrappeUIProvider>
</template>

<script setup>
import { FrappeUIProvider, usePageMeta } from '@/ui'
import { TENANT_APP } from './lib/brand'

// The product's name, not the app's. Somebody signing up has never heard of
// either repository and is about to get a OneSpace workspace.
usePageMeta(() => ({ title: `Sign up for ${TENANT_APP}` }))
</script>
