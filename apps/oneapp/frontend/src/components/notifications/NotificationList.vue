<template>
  <!--
    The feed, as rows.

    Its own component because it has two homes: the bell in the rail, and the
    More sheet on a phone, where there is no rail to put a bell in. The panel
    is the same thing in both — a different frame around it is a different
    product depending on which device you opened it on.
  -->
  <div class="flex max-h-[70vh] w-full flex-col">
    <header
      class="flex shrink-0 items-center gap-2 border-b border-outline-gray-1 px-3 py-2"
    >
      <span class="text-p-base font-medium text-ink-gray-8">Notifications</span>
      <Badge
        v-if="notifications.unread"
        :label="String(notifications.unread)"
        theme="blue"
        variant="subtle"
      />
      <span class="flex-1" />
      <!-- Only where there is something to mark. A control that does nothing is
           a control somebody presses once and stops trusting. -->
      <Button
        v-if="notifications.unread"
        variant="ghost"
        size="sm"
        label="Mark all read"
        @click="markRead()"
      />
    </header>

    <div class="min-h-0 flex-1 overflow-y-auto">
      <div v-if="notifications.loading && !notifications.rows.length" class="flex flex-col gap-2 p-3">
        <Skeleton v-for="n in 3" :key="n" class="h-12 w-full" />
      </div>

      <!--
        Nothing here, said the way this product says it. Not "you have no
        notifications" — a person who has just arrived has none and that is not
        a state worth explaining twice.
      -->
      <EmptyState
        v-else-if="!notifications.rows.length"
        icon="lucide-bell"
        title="Nothing yet"
        description="Assignments, mentions and alerts turn up here."
      />

      <!--
        A whole row is the control: a face, a sentence, a time and an unread
        dot, all of it clickable. `Button` lays its slot out as one line of
        label with optional icons, so this would have to fight it on every one
        of those. The rule is right, and this is the case it does not cover — a
        `<button>` wrapping content rather than a word.
      -->
      <!-- eslint-disable-next-line vue/no-restricted-html-elements -->
      <button
        v-for="row in notifications.rows"
        :key="row.name"
        type="button"
        class="flex w-full items-start gap-3 border-b border-outline-gray-1 px-3 py-2.5 text-left last:border-0 hover:bg-surface-gray-1"
        :class="row.read ? '' : 'bg-surface-blue-1'"
        @click="open(row)"
      >
        <!--
          Two glyphs, not one: whose it was, and what kind of thing happened.
          An Alert has no sender at all, which is why the type icon is the one
          that is always there and the face is the one that is sometimes.
        -->
        <span class="relative mt-0.5 shrink-0">
          <Avatar
            v-if="row.from"
            :label="row.from.label"
            :image="row.from.image"
            size="md"
          />
          <span
            v-else
            class="flex size-6 items-center justify-center rounded-full bg-surface-gray-3"
          >
            <Icon :name="icon(row)" class="size-3.5 text-ink-gray-6" />
          </span>
          <span
            v-if="row.from"
            class="absolute -bottom-1 -right-1 flex size-3.5 items-center justify-center rounded-full bg-surface-base"
          >
            <Icon :name="icon(row)" class="size-3 text-ink-gray-6" />
          </span>
        </span>

        <span class="flex min-w-0 flex-1 flex-col gap-0.5">
          <span class="text-p-sm text-ink-gray-8">{{ row.said }}</span>
          <span v-if="row.body" class="line-clamp-2 text-p-xs text-ink-gray-6">
            {{ row.body }}
          </span>
          <span class="text-p-xs text-ink-gray-5">{{ when(row) }}</span>
        </span>

        <!-- Unread, as a dot rather than as a word. The row is already tinted;
             this is what makes a tinted row scannable in a column of them. -->
        <span
          v-if="!row.read"
          class="mt-1.5 size-2 shrink-0 rounded-full bg-surface-blue-3"
          aria-label="Unread"
        />
      </button>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { Avatar, Badge, Button, Icon, Skeleton, dayjsLocal } from '@/ui'

import EmptyState from '../EmptyState.vue'

import { notificationIcon } from '../../lib/fields'
import { markRead, notifications } from '../../lib/notifications'

const emit = defineEmits(['opened'])
const router = useRouter()

const icon = (row) => notificationIcon(row.type)

// The same relative age the list rows show, and for the same reason: "2 days"
// is an age, and "2 days ago" repeated down a column is a sentence repeated.
const when = (row) => (row.when ? dayjsLocal(row.when).fromNow(true) : '')

/**
 * Open what the notification is about.
 *
 * Marking it read is not conditional on going anywhere: a notification you
 * have clicked is one you have seen, whether or not this product could work
 * out where its record lives.
 */
const open = (row) => {
  markRead(row.name)
  emit('opened')

  if (row.route?.space) {
    router.push({
      name: 'Screen',
      params: { spaceCode: row.route.space },
      query: { screen: row.route.screen, record: row.record || undefined },
    })
  } else if (row.link) {
    // A producer's own link. Inside this site, so a route push rather than a
    // navigation — and the router falls back to the not-found page rather
    // than leaving somebody on a blank screen.
    router.push(row.link)
  }
}
</script>
