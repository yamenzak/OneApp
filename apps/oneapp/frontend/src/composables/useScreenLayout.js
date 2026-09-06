import { computed, ref } from 'vue'

import { workspace } from '@/lib/workspace'

/**
 * Where an unsaved change goes when you say to keep it, which depends on where
 * you are.
 *
 * In a named view you may write, it goes into that view; anywhere else it goes
 * into this person's own unnamed default for the screen, which is what "keep
 * this how I left it" has always meant. Frappe CRM draws the same line, and the
 * alternative is worse in both directions: a Save that silently makes a private
 * copy of a shared view, or one that quietly rewrites a view other people use.
 *
 * "In a named view" and not merely "a layout is open": this person's own
 * unnamed default is a layout row too, and the screen opens with it — so
 * reading `spec.layout` alone made Save write into the default it had just
 * resolved and left Discard with nothing to reset. The label is what makes a
 * layout a view somebody named.
 */
export function useScreenLayout({ spaceCode, spec, dirty, payload, reload }) {
  const saving = ref(false)
  const resetting = ref(false)

  const currentLayout = computed(
    () => (spec.value?.layouts || []).find((one) => one.name === spec.value?.layout) || null,
  )

  const savesIntoView = computed(
    () => !!currentLayout.value?.label && (currentLayout.value.mine || !!spec.value?.can_share),
  )

  const saveLabel = computed(() => (savesIntoView.value ? 'Save changes' : 'Save this screen'))

  const discardLabel = computed(() =>
    dirty.value ? 'Discard these changes' : 'Back to the default screen',
  )

  const saveLayout = async () => {
    saving.value = true
    try {
      await workspace.saveLayout(spaceCode, spec.value.screen, {
        ...payload(),
        ...(savesIntoView.value ? { layout: spec.value.layout } : {}),
      })
      dirty.value = false
      await reload()
    } finally {
      saving.value = false
    }
  }

  // The way back. In a view that means the view as it was saved — a reload of
  // the same layout; on the screen itself it means dropping this person's saved
  // default altogether.
  const discardChanges = async () => {
    resetting.value = true
    try {
      if (!savesIntoView.value && spec.value?.saved) {
        await workspace.resetLayout(spaceCode, spec.value.screen, spec.value.view_type)
      }
      dirty.value = false
      await reload()
    } finally {
      resetting.value = false
    }
  }

  return {
    saving, resetting, currentLayout, savesIntoView, saveLabel, discardLabel,
    saveLayout, discardChanges,
  }
}
