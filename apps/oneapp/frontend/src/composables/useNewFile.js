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

import { workspace } from '@/lib/workspace'
import { RETURN_TO, returnQuery } from '@/lib/screen/returnTo'
import { __ } from '@/lib/runtime/translate'

//: How many templates a menu offers before it stops being a menu. Six is about
//: what fits under "Blank sheet" without pushing the group below it off the
//: screen; past that the list is a place to browse rather than a list to read,
//: and the Drive's Templates rail entry is that place.
const MOST = 6

export function useNewFile(where, extras = () => []) {
  const router = useRouter()

  // Null in the Drive, where a new file belongs to the folder you are in and
  // there is nothing to come back to.
  const came = inject(RETURN_TO, null)

  const making = ref(false)
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

  const copyName = (row, fallback) => __('{0} copy', [row?.file_name || fallback])

  /**
   * The templates a menu can hold, and a way to the rest.
   *
   * Uncapped, this grew to fourteen entries against three real ones — every
   * estimator anybody had ever flagged, in one flat list, with "Document" and
   * "Blank sheet" scrolled off the top. A menu is for the handful you reach for
   * daily.
   */
  const offered = (rows, icon, start) => {
    const entries = rows.slice(0, MOST).map((one) => ({
      label: one.file_name,
      icon,
      onClick: () => start(one.name, copyName(one, __('Copy'))),
    }))
    if (rows.length > MOST) {
      entries.push({
        label: __('All {0} templates…', [rows.length]),
        icon: 'lucide-bookmark',
        onClick: () => router.push({ name: 'Drive', query: { place: 'templates' } }),
      })
    }
    return entries
  }

  // Grouped rather than listed flat, because a workspace with four estimator
  // templates otherwise gets a menu where "Document" is below the fold.
  const options = computed(() => [
    {
      group: __('Write'),
      options: [
        { label: __('Document'), icon: 'lucide-file-signature', onClick: () => newDoc() },
        { label: __('Text file'), icon: 'lucide-file-text', onClick: () => newText('txt') },
        { label: __('Markdown file'), icon: 'lucide-file-code', onClick: () => newText('md') },
        ...offered(docTemplates.value, 'lucide-file-signature', newDoc),
      ],
    },
    {
      group: __('Calculate'),
      options: [
        { label: __('Blank sheet'), icon: 'lucide-table-2', onClick: () => newSheet() },
        ...extras(),
        ...offered(sheetTemplates.value, 'lucide-table-2', newSheet),
      ],
    },
  ])

  return { making, options, docTemplates, sheetTemplates, loadTemplates, newDoc, newSheet, newText }
}
