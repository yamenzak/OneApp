<template>
  <!--
    Your password, and where this account is signed in.

    Both are the framework's; this is a surface over them. The password rules
    that apply here are the ones an admin set under Sign in, which is the pair
    working as intended: one person sets the bar, everybody else meets it in
    their own dialog.
  -->
  <SettingsHeader
    title="Security"
    description="Your password, and where you are signed in."
    :class="PANEL_HEADER"
  />

  <SettingsBody :class="PANEL_BODY">
    <div v-if="!data" class="grid place-items-center py-16">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <div v-else class="flex flex-col gap-8 pt-6">
      <section class="flex flex-col gap-3">
        <h3 class="text-base-medium text-ink-gray-8">Change your password</h3>
        <!-- The current one is asked for rather than assumed from the session:
             being signed in is not proof that the person at the keyboard is the
             account holder, which is why every product asks. -->
        <FormControl
          v-model="current"
          type="password"
          label="Current password"
          data-slot="security-current"
        />
        <FormControl
          v-model="fresh"
          type="password"
          label="New password"
          data-slot="security-new"
        />
        <ErrorMessage :message="problem" />
        <div>
          <Button
            variant="solid"
            label="Change password"
            data-slot="security-change"
            :loading="changing"
            :disabled="!current || !fresh"
            @click="change"
          />
        </div>
        <p v-if="data.two_factor" class="text-p-sm text-ink-gray-5">
          This workspace also asks for a second factor when you sign in.
        </p>
      </section>

      <section class="flex flex-col gap-3">
        <h3 class="text-base-medium text-ink-gray-8">Where you are signed in</h3>
        <div class="rounded-6 border border-outline-gray-2">
          <div
            v-for="(one, at) in data.sessions"
            :key="at"
            class="flex items-center justify-between gap-3 border-b border-outline-gray-1 px-3 py-2 last:border-b-0"
            data-slot="security-session"
          >
            <div class="min-w-0">
              <p class="truncate text-p-base text-ink-gray-8">
                {{ one.from || 'Unknown address' }}
              </p>
              <p class="truncate text-p-xs text-ink-gray-5">{{ one.last_seen }}</p>
            </div>
            <Badge v-if="one.this_one" theme="green" label="This browser" />
          </div>
          <p
            v-if="!data.sessions.length"
            class="px-3 py-2 text-p-sm text-ink-gray-5"
          >
            Only here.
          </p>
        </div>

        <!-- Everywhere except here, deliberately: the reason somebody reaches
             for this is a laptop they no longer have, and a button that also
             signs you out of the browser you pressed it in is one nobody
             presses twice. -->
        <div>
          <Button
            label="Sign out everywhere else"
            data-slot="security-end-others"
            :loading="ending"
            :disabled="data.sessions.length < 2"
            @click="endOthers"
          />
        </div>
      </section>
    </div>
  </SettingsBody>
</template>

<script setup>
import { ref } from 'vue'
import {
  Badge, Button, ErrorMessage, FormControl, LoadingIndicator, SettingsBody, SettingsHeader,
} from '@/ui'
import { PANEL_BODY, PANEL_HEADER } from './geometry'
import { workspace } from '@/lib/workspace'
import { errorText } from '@/lib/runtime/errors'

const data = ref(null)
const current = ref('')
const fresh = ref('')
const problem = ref('')
const changing = ref(false)
const ending = ref(false)

async function load() {
  data.value = await workspace.security()
}

async function change() {
  problem.value = ''
  changing.value = true
  try {
    await workspace.changePassword(current.value, fresh.value)
    current.value = ''
    fresh.value = ''
  } catch (e) {
    // Said here rather than as a toast: a rejected password is a correction to
    // make in the form that is still on screen.
    problem.value = errorText(e)
  } finally {
    changing.value = false
  }
}

async function endOthers() {
  ending.value = true
  try {
    data.value = { ...data.value, ...(await workspace.endOtherSessions()) }
  } finally {
    ending.value = false
  }
}

load()
</script>
