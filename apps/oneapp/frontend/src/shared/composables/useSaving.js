import { ref } from 'vue'

import { errorText } from '@/shared/lib/runtime/errors'

/**
 * A write, its busy flag, and the message it leaves behind when it fails.
 *
 * Thirteen places had the same six lines around a call: set busy, clear the
 * message, try, put the message where the panel draws it, clear busy. Six lines
 * repeated thirteen times is thirteen chances to forget the `finally`, which is
 * a Save button that spins forever on the one path nobody tested.
 *
 * A message rather than a toast, deliberately, and that is the decision this
 * module is really holding: a failed save belongs beside the form that failed
 * to save, where the person can read it while fixing what caused it. The
 * request layer's own toast is for the writes nobody is watching.
 *
 * A panel with two busy flags — saving and previewing, say — calls this twice
 * and hands the second one the first's `error`, so both write to the one line
 * the panel actually draws.
 */
export function useSaving(error = ref('')) {
  const saving = ref(false)

  /** Run `work`, and answer with what it returned — or nothing, if it threw. */
  const attempt = async (work) => {
    saving.value = true
    error.value = ''
    try {
      return await work()
    } catch (raised) {
      error.value = errorText(raised)
      return undefined
    } finally {
      saving.value = false
    }
  }

  return { saving, error, attempt }
}
