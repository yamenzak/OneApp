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

import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import { workspace } from '@/lib/workspace'

export function useNewFile(where, extras = () => []) {
  const router = useRouter()

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
      router.push({ name: route, params: { name: made.name } })
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

  const copyName = (row, fallback) => `${row?.file_name || fallback} copy`

  // Grouped rather than listed flat, because a workspace with four estimator
  // templates otherwise gets a menu where "Document" is below the fold.
  const options = computed(() => [
    {
      group: 'Write',
      options: [
        { label: 'Document', icon: 'lucide-file-signature', onClick: () => newDoc() },
        { label: 'Text file', icon: 'lucide-file-text', onClick: () => newText('txt') },
        { label: 'Markdown file', icon: 'lucide-file-code', onClick: () => newText('md') },
        ...docTemplates.value.map((one) => ({
          label: one.file_name,
          icon: 'lucide-file-signature',
          onClick: () => newDoc(one.name, copyName(one, 'Document')),
        })),
      ],
    },
    {
      group: 'Calculate',
      options: [
        { label: 'Blank sheet', icon: 'lucide-table-2', onClick: () => newSheet() },
        ...extras(),
        ...sheetTemplates.value.map((one) => ({
          label: one.file_name,
          icon: 'lucide-table-2',
          onClick: () => newSheet(one.name, copyName(one, 'Sheet')),
        })),
      ],
    },
  ])

  return { making, options, docTemplates, sheetTemplates, loadTemplates, newDoc, newSheet, newText }
}
