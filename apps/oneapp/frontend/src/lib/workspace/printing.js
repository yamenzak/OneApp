/** Print formats and letter heads, and rendering one. */

import { callMethod } from '@/lib/runtime/resource'
import { __ } from '@/lib/runtime/translate'

export const printing = {
  printOptions: (spaceCode, screen, name) =>
    callMethod(
      'oneapp.onespace.spaceview.print_options',
      { space_code: spaceCode, screen, name },
      { silent: true, method: 'GET' },
    ),

  printPreview: (spaceCode, screen, name, { format = '', letterhead = '', language = '' } = {}) =>
    callMethod(
      'oneapp.onespace.spaceview.print_preview',
      { space_code: spaceCode, screen, name, format, letterhead, language },
      { silent: true, method: 'GET' },
    ),

  /**
   * A URL rather than a call.
   *
   * The PDF comes back as a download response with a filename on it, so the
   * browser should be handed the address and left to do what it does with one
   * — fetching the bytes and rebuilding a file loses the name and the
   * progress bar both.
   */

  printPdfUrl: (spaceCode, screen, name, { format = '', letterhead = '', language = '' } = {}) => {
    const asked = new URLSearchParams({
      space_code: spaceCode,
      screen,
      name,
      format,
      letterhead,
      language,
    })
    return `/api/method/oneapp.onespace.spaceview.print_pdf?${asked}`
  },

  /**
   * The same, for a whole selection: one PDF with a page break between each.
   *
   * A URL for the same reason — the response is a download with a filename on
   * it. The ids go in the query string, which is what bounds this at fifty on
   * the server as well as here: a hundred invoices is a URL nothing will
   * accept and a PDF nothing will finish building.
   */
  printManyUrl: (spaceCode, screen, names, { format = '', letterhead = '', language = '' } = {}) => {
    const asked = new URLSearchParams({
      space_code: spaceCode,
      screen,
      names: JSON.stringify(names || []),
      format,
      letterhead,
      language,
    })
    return `/api/method/oneapp.onespace.spaceview.print_many?${asked}`
  },

  // --- where a document stands ---------------------------------------------
  //
  // Submit, cancel and amend are three permissions rather than one verb, and a
  // workflow transition is checked by the workflow — so four calls rather than
  // one taking a string. See `onespace/docflow.py`.

  printFormats: (doctype = '') =>
    callMethod(
      'oneapp.onespace.workspace.print_formats',
      { doctype },
      { silent: true, method: 'GET' },
    ),

  printPalette: (doctype) =>
    callMethod(
      'oneapp.onespace.workspace.print_palette',
      { doctype },
      { silent: true, method: 'GET' },
    ),

  printFormat: (name) =>
    callMethod(
      'oneapp.onespace.workspace.print_format',
      { name },
      { silent: true, method: 'GET' },
    ),

  savePrintFormat: (doctype, label, layout, setup, name = '') =>
    callMethod(
      'oneapp.onespace.workspace.save_print_format',
      {
        doctype,
        label,
        layout: JSON.stringify(layout),
        setup: JSON.stringify(setup || {}),
        name,
      },
      { successMessage: __('Format saved') },
    ),

  deletePrintFormat: (name) =>
    callMethod(
      'oneapp.onespace.workspace.delete_print_format',
      { name },
      { successMessage: __('Format deleted') },
    ),

  setDefaultPrintFormat: (doctype, name) =>
    callMethod(
      'oneapp.onespace.workspace.set_default_print_format',
      { doctype, name },
      { successMessage: __('Default set') },
    ),

  printFormatPreview: (doctype, layout, setup, { name = '', letterhead = '' } = {}) =>
    callMethod(
      'oneapp.onespace.workspace.print_format_preview',
      {
        doctype,
        layout: JSON.stringify(layout),
        setup: JSON.stringify(setup || {}),
        name,
        letterhead,
      },
      { silent: true },
    ),

  letterHeads: () =>
    callMethod('oneapp.onespace.workspace.letter_heads', {}, { silent: true, method: 'GET' }),

  setDefaultLetterHead: (name) =>
    callMethod(
      'oneapp.onespace.workspace.set_default_letter_head',
      { name },
      { successMessage: __('Default set') },
    ),

  letterHead: (name) =>
    callMethod(
      'oneapp.onespace.workspace.letter_head',
      { name },
      { silent: true, method: 'GET' },
    ),

  saveLetterHead: (label, values, name = '') =>
    callMethod(
      'oneapp.onespace.workspace.save_letter_head',
      { label, values: JSON.stringify(values || {}), name },
      { successMessage: __('Letter head saved') },
    ),

  deleteLetterHead: (name) =>
    callMethod(
      'oneapp.onespace.workspace.delete_letter_head',
      { name },
      { successMessage: __('Letter head deleted') },
    ),

  // --- tags and sharing ---------------------------------------------------
  //
  // Frappe's `_user_tags` and `DocShare`, screen-gated. See
  // `onespace/collab.py` for what each one is and why neither is ours.
}
