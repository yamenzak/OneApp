/**
 * The New menu: the four things in this product that are made rather than
 * uploaded, and the templates a workspace has made of the first two.
 *
 * A composable because the menu appears twice and the two are the same menu.
 * In the Drive a new file lands in the folder you are looking at; on a record's
 * Files tab it lands attached to the record, which is `attached_to_doctype`
 * and nothing else — the difference is four fields in one object, so it is a
 * parameter rather than a second component.
 *
 * `where` is a getter and not a value because the Drive's folder changes under
 * it as somebody navigates, and a menu built once against the folder they
 * started in creates files in the wrong place.
 */

import { computed, inject, ref } from 'vue'
import { useRouter } from 'vue-router'

import { workspace } from '@/shared/lib/workspace'
import { RETURN_TO, returnQuery } from '@/modules/onespace/lib/screen/returnTo'
import { __ } from '@/shared/lib/runtime/translate'

export function useNewFile(where, extras = () => []) {
  const router = useRouter()

  // Null in the Drive, where a new file belongs to the folder you are in and
  // there is nothing to come back to.
  const came = inject(RETURN_TO, null)

  const making = ref(false)

  // Whether the language dialog is open. Here rather than in each of the two
  // components that draw this menu, because both would otherwise carry the same
  // ref, the same import and the same handler for one shared question.
  const choosingLanguage = ref(false)
  const docTemplates = ref([])
  const sheetTemplates = ref([])

  // Both lists up front rather than when the menu opens: a menu that takes a
  // round trip to fill appears empty and then jumps. Two small queries, and a
  // failure leaves the menu without templates rather than without a menu.
  const loadTemplates = () => {
    workspace.sheetTemplates()
      .then((found) => { sheetTemplates.value = found || [] })
      .catch(() => { sheetTemplates.value = [] })
    workspace.docTemplates()
      .then((found) => { docTemplates.value = found || [] })
      .catch(() => { docTemplates.value = [] })
  }

  const target = () => where() || {}

  const run = async (work, route) => {
    making.value = true
    try {
      const made = await work()
      router.push({
        name: route,
        params: { name: made.name },
        query: returnQuery(came?.value),
      })
      return made
    } finally {
      making.value = false
    }
  }

  const newSheet = (template = '', title = '') =>
    run(() => workspace.sheetMake({ ...target(), template, title }), 'Sheet')

  const newDoc = (template = '', title = '') =>
    run(() => workspace.docMake({ ...target(), template, title }), 'Doc')

  const newText = (kind) =>
    run(() => workspace.docMakeText({ ...target(), kind }), 'Doc')

  /*
   * Grouped rather than listed flat, because a workspace with four estimator
   * templates otherwise gets a menu where "Document" is below the fold.
   *
   * And no templates in it at all any more. They were here, capped at six with
   * an "All 14 templates…" row under them, and it was the wrong place twice
   * over: a menu called New is a menu of *kinds*, and putting a workspace's
   * own files in it made the kinds hard to find; and the moment you actually
   * want a template is the moment you are looking at a blank sheet, not the
   * moment you are deciding to make one. So Load a template lives in the
   * editors — `TemplatePicker` — where the blank page is on screen.
   */
  const options = computed(() => [
    {
      group: __('Write'),
      options: [
        { label: __('Document'), icon: 'lucide-file-signature', onClick: () => newDoc() },
        { label: __('Text file'), icon: 'lucide-file-text', onClick: () => newText('txt') },
        { label: __('Markdown file'), icon: 'lucide-file-code', onClick: () => newText('md') },
      ],
    },
    {
      group: __('Calculate'),
      options: [
        { label: __('Blank sheet'), icon: 'lucide-table-2', onClick: () => newSheet() },
        ...extras(),
      ],
    },
    {
      group: __('Build'),
      options: [
        // No language on it: which one is the dialog's question, and a New menu
        // that named a default would be a menu where twenty of the twenty-one
        // are hidden behind a submenu nobody opens.
        { label: __('Code'), icon: 'lucide-file-code', onClick: () => { choosingLanguage.value = true } },
      ],
    },
  ])

  return {
    making, options, choosingLanguage, docTemplates, sheetTemplates, loadTemplates,
    newDoc, newSheet, newText,
  }
}
