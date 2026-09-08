<template>
  <!--
    The one dialog in this product a person cannot dismiss.

    It is up when there is an agreement they have not made, and it does not
    close until they make it or sign out. That is the whole point: the moment a
    document's version changes, everybody who has to agree is asked before they
    do anything else.

    Two shapes, because there are two ways to be stopped. If this person can
    bind the workspace, they are shown what to agree to and a button. If they
    cannot — an invited user, and the workspace's own contract is outstanding —
    they are told whose signature is missing rather than shown a button that
    will refuse them.
  -->
  <Dialog
    :model-value="showing"
    size="3xl"
    :dismissible="false"
    :show-close-button="false"
    bare
  >
    <template #default>
      <div class="flex max-h-[80vh] flex-col p-6">
        <div class="flex items-center gap-3">
          <Icon name="lucide-scale" class="size-5 text-ink-gray-6" />
          <h2 class="text-lg font-semibold text-ink-gray-9">
            {{ __('Before you carry on') }}
          </h2>
        </div>

        <p class="mt-2 text-p-sm text-ink-gray-7">
          {{ blocking.length
            ? __('These have changed since you last agreed, or you have not agreed to them yet.')
            : __('This workspace has agreements outstanding.') }}
        </p>

        <div class="mt-4 min-h-0 flex-1 overflow-y-auto rounded-6 border border-outline-gray-2">
          <div v-if="reading" class="p-5">
            <Button
              variant="ghost"
              icon-left="lucide-arrow-left"
              :label="__('Back')"
              class="mb-3"
              @click="reading = null"
            />
            <!-- Server-assembled and server-escaped — `assemble._esc`. -->
            <article class="prose prose-sm max-w-none" v-html="reading.html" />
          </div>

          <ul v-else class="divide-y divide-outline-gray-1">
            <li
              v-for="one in blocking"
              :key="`${one.document}-${one.party}`"
              class="flex items-start justify-between gap-3 p-4"
            >
              <div class="min-w-0">
                <p class="text-p-sm font-medium text-ink-gray-8">{{ one.title }}</p>
                <p class="mt-0.5 text-p-xs text-ink-gray-6">{{ one.summary }}</p>
                <p class="mt-1 text-p-xs text-ink-gray-5">
                  {{ one.party === 'Workspace'
                    ? __('For the organisation · version {0}', [one.version])
                    : __('For you · version {0}', [one.version]) }}
                </p>
              </div>
              <Button
                variant="subtle"
                :label="__('Read')"
                :loading="opening === one.document"
                @click="read(one.document)"
              />
            </li>
            <li v-for="one in waiting" :key="one.document" class="p-4">
              <p class="text-p-sm font-medium text-ink-gray-8">{{ one.title }}</p>
              <p class="mt-0.5 text-p-xs text-ink-gray-6">
                {{ __('Waiting for the workspace owner to agree to this.') }}
              </p>
            </li>
          </ul>
        </div>

        <div class="mt-4 flex items-center justify-between gap-3">
          <p class="text-p-xs text-ink-gray-5">
            {{ __('Agreeing records the version, the date and your account.') }}
          </p>
          <div class="flex gap-2">
            <Button :label="__('Sign out')" @click="signOut" />
            <Button
              v-if="blocking.length"
              variant="solid"
              :label="__('I agree')"
              :loading="busy"
              @click="agree"
            />
          </div>
        </div>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import { Button, Dialog, Icon } from '@/ui'
import { workspace } from '@/lib/workspace'
import { __ } from '@/lib/runtime/translate'

const state = ref({ blocking: [], waiting: [], ok: true })
const reading = ref(null)
const opening = ref('')
const busy = ref(false)

const blocking = computed(() => state.value.blocking || [])
const waiting = computed(() => state.value.waiting || [])
const showing = computed(() => !state.value.ok)

async function read(key) {
  opening.value = key
  try {
    reading.value = await workspace.legalDocument(key)
  } finally {
    opening.value = ''
  }
}

async function agree() {
  busy.value = true
  try {
    state.value = await workspace.legalAccept(blocking.value.map((one) => one.document))
    reading.value = null
  } finally {
    busy.value = false
  }
}

const signOut = () => { window.location.href = '/api/method/logout' }

onMounted(async () => {
  try {
    state.value = await workspace.legalOutstanding()
  } catch {
    // A workspace that cannot answer is a workspace mid-migration, and locking
    // everybody out of it would be worse than the thing this guards against.
    state.value = { blocking: [], waiting: [], ok: true }
  }
})
</script>
