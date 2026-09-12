import { computed, ref } from 'vue'

import { notifyError, notifySuccess } from '@/shared/lib/runtime/notify'
import { saveCsv } from '@/modules/onestorage/lib/download'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'
import { number as count } from '@/shared/lib/runtime/format'

/**
 * Everything the selection bar and the footer do to more than one record.
 *
 * Each record is saved on its own on the server, so what could not take the
 * change comes back named — a submitted document, a rule the value breaks, a
 * row this person may read and not write. Said out loud rather than swallowed:
 * a bulk change that silently skipped nine of forty is worse than one that
 * failed.
 *
 * `payload` and `reloadRows` are thunks; `selection` is the rows' own ref, so
 * clearing it here is what clears the bar.
 */
export function useBulkActions({ spaceCode, spec, selection, payload, reloadRows }) {
  const bulkEditing = ref(false)
  const bulkAssigning = ref(false)
  const bulking = ref(false)
  const confirmBulkCancel = ref(false)
  const confirmDelete = ref(false)
  const deleting = ref(false)
  const exporting = ref(false)

  /** What came back refused, named rather than counted. */
  const refused = (rows) =>
    notifyError(rows.map((row) => `${row.name}: ${row.reason}`).join('\n'))

  /**
   * Run one bulk verb and say what happened.
   *
   * `said` is a function of the count rather than a word to glue a number
   * onto. `${said} ${n}` read correctly in English and nowhere else: the verb
   * and the number landed in the catalogue as two things, a translator saw
   * the verb alone, and a language that puts the count first had no way to
   * say so. It was also invisible to the i18n guard, because the reader
   * extracted quoted strings and this was a template literal —
   * `docs/UNIFICATION.md` §D2.
   */
  const through = async (work, said, close) => {
    bulking.value = true
    try {
      const result = await work()
      if (result?.refused?.length) refused(result.refused)
      if (result?.done?.length) notifySuccess(said(result.done.length))
      close.value = false
      selection.value = []
      await reloadRows()
    } catch (e) {
      notifyError(e)
    } finally {
      bulking.value = false
    }
  }

  const bulkSet = ({ field, value }) =>
    through(
      () => workspace.screenBulkSet(spaceCode, spec.value.screen, selection.value, field, value),
      (n) => __('Changed {0}', [n]),
      bulkEditing,
    )

  const bulkAssign = (users) =>
    through(
      () => workspace.screenBulkAssign(spaceCode, spec.value.screen, selection.value, users),
      (n) => __('Assigned {0}', [n]),
      bulkAssigning,
    )

  // Whether these records are submitted by *this* button. Two facts about the
  // doctype, off the screen rather than off the rows: a list does not carry
  // `_state`, and a workflow owns the transition where there is one —
  // `docflow` refuses a plain submit there on purpose, so the button would
  // fail on every record.
  const submittable = computed(() => !!spec.value?.submittable && !spec.value?.workflow)

  const bulkSubmit = () =>
    through(
      () => workspace.screenBulkSubmit(spaceCode, spec.value.screen, selection.value),
      (n) => __('Submitted {0}', [n]),
      bulkEditing,
    )

  const bulkCancel = () =>
    through(
      () => workspace.screenBulkCancel(spaceCode, spec.value.screen, selection.value),
      (n) => __('Cancelled {0}', [n]),
      confirmBulkCancel,
    )

  /**
   * The selection as one PDF.
   *
   * A window rather than fetch-and-blob, for the reason the record's own print
   * download is: the response is a real download with a filename on it, and
   * rebuilding the file in JavaScript loses the name and the progress bar both.
   * No dialog — printing forty records is "give me the paperwork".
   */
  const printSelected = () => {
    window.open(
      workspace.printManyUrl(spaceCode, spec.value.screen, selection.value),
      '_blank',
      'noopener',
    )
  }

  const removeSelected = async () => {
    deleting.value = true
    try {
      const result = await workspace.removeRecords(spaceCode, spec.value.screen, [
        ...selection.value,
      ])
      confirmDelete.value = false
      selection.value = (result?.refused || []).map((row) => row.name)
      if (result?.refused?.length) refused(result.refused)
      else notifySuccess(__('Deleted {0}', [result?.deleted?.length || 0]))
      await reloadRows()
    } finally {
      deleting.value = false
    }
  }

  /**
   * The rows, as a file.
   *
   * `names` is the selection where there is one and nothing where there is not,
   * and the server reads that difference — so the button in the footer and the
   * one in the selection bar are the same call. The whole thing arrives as text
   * and is turned into a download here: an export URL would have to carry the
   * screen, the saved view, the unsaved filters and the selection as query
   * parameters, and would be a second way into the data.
   */
  const exportRows = async (names) => {
    if (exporting.value) return
    exporting.value = true
    try {
      const file = await workspace.screenExport(
        spaceCode,
        spec.value.screen,
        payload(),
        spec.value.layout || '',
        spec.value.view_type,
        names,
      )
      saveCsv(file?.filename, file?.csv || '')
      // The cap is said out loud or not at all. A spreadsheet that quietly
      // stops at five thousand rows is the worst thing to hand somebody who is
      // about to add it up.
      notifySuccess(
        file?.capped
          ? `The first ${count(file.rows, 0)} rows — this screen has more than ` +
            `${count(file.limit, 0)}, which is the most one file carries.`
          : `${count(file?.rows || 0, 0)} rows exported`,
      )
    } catch (e) {
      notifyError(e)
    } finally {
      exporting.value = false
    }
  }

  return {
    bulkEditing, bulkAssigning, bulking, confirmBulkCancel, confirmDelete,
    deleting, exporting, submittable,
    bulkSet, bulkAssign, bulkSubmit, bulkCancel, printSelected, removeSelected,
    exportRows,
  }
}
