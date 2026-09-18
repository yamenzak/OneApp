<template>
  <!--
    One box over every space.

    The gap it closes is the one `docs/FRAPPE.md` named first: somebody who
    knows a customer's name and not which space it is in had nowhere to type
    it, and every space was searched by opening it.

    **It is useful before it is answered.** The screens come out of the session
    payload the shell already holds, so the moment it opens there is a list of
    places to go — filtered on the keystroke with nothing on the wire. The
    records arrive behind that, from `onespace/finding.py`, and land in the
    same list rather than in a section of their own: a person typing `inv`
    means the Invoices screen or an invoice and should not have to say which.

    **Ctrl+K works while you are typing**, which is the one place the house
    shortcut rules do not apply and the reason this binds its own listener.
    `lib/shell/shortcuts.js` stands down inside an input and over a dialog,
    correctly — a bare `e` must not archive mail while somebody is searching
    for it. A modified key cannot be typed into anything, so the two reasons do
    not hold, and a palette you cannot reach from the box you are already in is
    a palette nobody uses twice.
  -->
  <!-- No title: the box is the title. A heading over a search field is a word
       somebody reads once and then never again, in the place the caret should
       already be. -->
  <!-- High rather than centred: the caret is at the top of it and the list
       grows downwards, so a box that centres itself moves under the hand
       every time an answer arrives. -->
  <Dialog v-model="finder.open" size="xl" position="top">
    <template #default>
      <div
        class="flex max-h-[70vh] min-h-0 flex-col p-4"
        data-slot="finder"
        @keydown.down.prevent="move(1)"
        @keydown.up.prevent="move(-1)"
        @keydown.enter.prevent="go(shown[active])"
      >
        <div class="flex shrink-0 items-center gap-2 pb-3">
          <ListSearch
            ref="box"
            v-model="finder.typed"
            class="flex-1"
            :placeholder="__('Find anything, anywhere')"
            @changed="look(finder.typed)"
          />
          <Spinner v-if="finder.looking" class="size-4 text-ink-muted" />
        </div>

        <DataList
          :source="source"
          class="min-h-0 flex-1 overflow-y-auto"
          :skeleton="4"
          body-class="gap-0.5"
        >
          <template #empty>
            <EmptyState
              :icon="waiting ? 'lucide-keyboard' : 'lucide-search-x'"
              :title="waiting ? __('Type to find something') : __('Nothing matched')"
              :description="waiting
                ? __('A screen in any space, or a record inside one.')
                : __('Try part of a name, or the id somebody sent you.')"
            />
          </template>

          <template #row="{ row, index }">
            <!-- not-a-tooltip: the pointer moves the keyboard's cursor rather
                 than revealing anything. A palette is driven by arrows and the
                 mouse has to agree with them — without this, hovering one row
                 and pressing Enter opens a different one. -->
            <Row
              :active="index === active"
              edge="rounded"
              pad="tight"
              @click="go(row)"
              @mouseenter="active = index"
            >
              <template #lead>
                <Icon :name="row.icon" class="size-4 text-ink-muted" :aria-hidden="true" />
              </template>

              <span class="flex min-w-0 items-baseline gap-2">
                <span class="truncate text-sm text-ink-primary">{{ row.title }}</span>
                <span v-if="row.id" class="shrink-0 text-xs text-ink-muted tabular-nums">
                  {{ row.id }}
                </span>
              </span>

              <template #trail>
                <!-- Where it is, which is the whole reason this box exists. A
                     record says its screen as well, because "Invoices in
                     OneBook" is the sentence that tells you what you found. -->
                <span class="text-xs text-ink-muted">
                  <template v-if="row.kind === 'record'">{{ row.label }} · </template>
                  {{ row.spaceLabel }}
                </span>
              </template>
            </Row>
          </template>
        </DataList>

        <p v-if="finder.failed" class="shrink-0 pt-2 text-xs text-ink-muted">
          {{ __('Records could not be searched just now. The screens above still work.') }}
        </p>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { Dialog, Icon, Spinner } from '@/ui'

import DataList from '@/shared/components/DataList.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import Row from '@/shared/components/Row.vue'
import ListSearch from '@/modules/onespace/components/screen/views/ListSearch.vue'
import { staticSource } from '@/shared/lib/list/source'
import { __ } from '@/shared/lib/runtime/translate'
import {
  SHORTEST,
  closeFinder,
  finder,
  look,
  openFinder,
  routeFor,
  shown,
} from '@/modules/onespace/lib/shell/finding'

const route = useRoute()
const router = useRouter()

const active = ref(0)
const box = ref(null)

const waiting = computed(() => (finder.typed || '').trim().length < SHORTEST)

const source = computed(() =>
  staticSource({ rows: shown.value, key: (row) => row.key, loading: false }),
)

// A new answer means a new first row. Without this the keyboard stays on
// whatever index it was on, which after a shorter list is a row that is no
// longer there.
watch(shown, () => { active.value = 0 })

const move = (by) => {
  const many = shown.value.length
  if (!many) return
  active.value = (active.value + by + many) % many
}

const go = (row) => {
  if (!row) return
  closeFinder()
  router.push(routeFor(row))
}

/**
 * Ctrl+K, and why it is not `useShortcuts`.
 *
 * That helper stands down inside an input and over a dialog, and both rules
 * are right for the letters it was written for. Neither holds for a modified
 * key: `mod+k` cannot be typed into a box, and the one place you most want to
 * reopen the finder is from inside it. So this is the exception, bound here,
 * where the reason for it is written down.
 */
const onKey = (event) => {
  const mod = event.metaKey || event.ctrlKey
  if (!mod || (event.key || '').toLowerCase() !== 'k') return
  event.preventDefault()
  if (finder.open) closeFinder()
  else openFinder(route.params?.spaceCode || '')
}

onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))

// The caret goes in the box, and the box is found through the wrapper for the
// same reason `ListSearch` finds it that way itself: `FormControl` renders
// whichever control it was told to, so a ref on it is the wrapper rather than
// the thing that takes focus.
watch(() => finder.open, async (open) => {
  // Closed from anywhere — Escape, the X, the backdrop — is still closed, and
  // `Dialog` does that by writing the model rather than by telling us. Without
  // this the next Ctrl+K opens on the last word somebody typed and the hits
  // for it, which reads as a box that did not clear rather than as history.
  if (!open) {
    closeFinder()
    return
  }
  active.value = 0
  await nextTick()
  box.value?.$el?.querySelector('input')?.focus()
})
</script>
