/** Print formats and letter heads, and rendering one. */

import { callMethod } from '../resource'

export const printing = {
  printOptions: (spaceCode, screen, name) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.print_options',
      { space_code: spaceCode, screen, name },
      { silent: true, method: 'GET' },
    ),

  printPreview: (spaceCode, screen, name, { format = '', letterhead = '', language = '' } = {}) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.print_preview',
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
    return `/api/method/oneapp.oneapp_core.spaceview.print_pdf?${asked}`
  },

  // --- where a document stands ---------------------------------------------
  //
  // Submit, cancel and amend are three permissions rather than one verb, and a
  // workflow transition is checked by the workflow — so four calls rather than
  // one taking a string. See `oneapp_core/docflow.py`.

  printFormats: (doctype = '') =>
    callMethod(
      'oneapp.oneapp_core.workspace.print_formats',
      { doctype },
      { silent: true, method: 'GET' },
    ),

  printPalette: (doctype) =>
    callMethod(
      'oneapp.oneapp_core.workspace.print_palette',
      { doctype },
      { silent: true, method: 'GET' },
    ),

  printFormat: (name) =>
    callMethod(
      'oneapp.oneapp_core.workspace.print_format',
      { name },
      { silent: true, method: 'GET' },
    ),

  savePrintFormat: (doctype, label, layout, setup, name = '') =>
    callMethod(
      'oneapp.oneapp_core.workspace.save_print_format',
      {
        doctype,
        label,
        layout: JSON.stringify(layout),
        setup: JSON.stringify(setup || {}),
        name,
      },
      { successMessage: 'Format saved' },
    ),

  deletePrintFormat: (name) =>
    callMethod(
      'oneapp.oneapp_core.workspace.delete_print_format',
      { name },
      { successMessage: 'Format deleted' },
    ),

  setDefaultPrintFormat: (doctype, name) =>
    callMethod(
      'oneapp.oneapp_core.workspace.set_default_print_format',
      { doctype, name },
      { successMessage: 'Default set' },
    ),

  printFormatPreview: (doctype, layout, setup, { name = '', letterhead = '' } = {}) =>
    callMethod(
      'oneapp.oneapp_core.workspace.print_format_preview',
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
    callMethod('oneapp.oneapp_core.workspace.letter_heads', {}, { silent: true, method: 'GET' }),

  letterHead: (name) =>
    callMethod(
      'oneapp.oneapp_core.workspace.letter_head',
      { name },
      { silent: true, method: 'GET' },
    ),

  saveLetterHead: (label, values, name = '') =>
    callMethod(
      'oneapp.oneapp_core.workspace.save_letter_head',
      { label, values: JSON.stringify(values || {}), name },
      { successMessage: 'Letter head saved' },
    ),

  deleteLetterHead: (name) =>
    callMethod(
      'oneapp.oneapp_core.workspace.delete_letter_head',
      { name },
      { successMessage: 'Letter head deleted' },
    ),

  // --- tags and sharing ---------------------------------------------------
  //
  // Frappe's `_user_tags` and `DocShare`, screen-gated. See
  // `oneapp_core/collab.py` for what each one is and why neither is ours.
}
