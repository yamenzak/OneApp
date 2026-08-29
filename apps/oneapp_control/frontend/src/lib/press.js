import { reactive, watch } from 'vue'

/**
 * A read from Frappe Cloud, fetched when its panel is first looked at.
 *
 * Two reasons this is not a plain `useResource`:
 *
 * - **Lazy.** A tenant page has five press panels. Fetching them all on load
 *   would make the page as slow as the slowest call to Frappe Cloud, to render
 *   four things nobody opened.
 * - **Degrading.** Press being unreachable should grey out one panel, not take
 *   down the page that would tell an operator why the site is unhappy. The
 *   endpoints report a press failure in-band as `{error}` rather than raising,
 *   and this keeps that shape so the panel can say which part is missing and
 *   why — an empty table would read as "there is nothing here".
 *
 * Returns one reactive object: `{ data, error, loading, loaded, reload() }`.
 */
export function usePress(fetcher, tabRef, tabValue) {
  const state = reactive({
    data: null,
    error: '',
    loading: false,
    loaded: false,

    async reload() {
      state.loading = true
      state.error = ''
      try {
        const result = await fetcher()
        state.data = result
        state.error = result?.error || ''
      } catch (e) {
        state.error = e.message || String(e)
      } finally {
        state.loading = false
        state.loaded = true
      }
    },
  })

  watch(
    tabRef,
    (value) => {
      if (value === tabValue && !state.loaded) state.reload()
    },
    { immediate: true },
  )

  return state
}
