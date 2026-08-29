import { ref } from 'vue'

/**
 * Settings dialog state.
 *
 * A single ref rather than a route, because settings overlay whatever you were
 * doing — closing it should put you back, not navigate you somewhere.
 */
export const showSettings = ref(false)
export const activeSettingsTab = ref('control')

export function openSettings(tab = 'control') {
  activeSettingsTab.value = tab
  showSettings.value = true
}
