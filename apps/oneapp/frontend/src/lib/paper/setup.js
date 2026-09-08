/*
 * Paper: the page a document or a sheet sits on, in the browser.
 *
 * Here rather than beside the document toolbar because a sheet's print dialog
 * needs the same nine numbers, and reaching them through `docs/toolbar.js`
 * would pull the whole tiptap toolbar into the spreadsheet's bundle.
 *
 * The same five sizes and three margins `oneapp_core/paper.py` offers, in
 * millimetres, because the editor has to draw the sheet the server will print
 * — a page that looks A4 on screen and prints Letter is worse than no page at
 * all. Kept as a copy rather than fetched: it is nine numbers that have not
 * changed since ISO 216 in 1975, and a page setup dialog that waits on a
 * request to know how wide A4 is would be a dialog that flickers.
 */

import { __ } from '@/lib/runtime/translate'

export const PAGE_SIZES = {
  A4: { label: 'A4', mm: [210, 297] },
  Letter: { label: __('Letter'), mm: [216, 279] },
  Legal: { label: __('Legal'), mm: [216, 356] },
  A3: { label: 'A3', mm: [297, 420] },
  A5: { label: 'A5', mm: [148, 210] },
}

export const ORIENTATIONS = {
  portrait: { label: __('Portrait') },
  landscape: { label: __('Landscape') },
}

export const MARGINS = {
  narrow: { label: __('Narrow'), mm: 12 },
  normal: { label: __('Normal'), mm: 20 },
  wide: { label: __('Wide'), mm: 30 },
}

/** One document's page setup with every gap filled — `paper.setup_of`, here. */
export function paperSetup(settings = {}) {
  const size = PAGE_SIZES[settings.page_size] ? settings.page_size : 'A4'
  const orientation = ORIENTATIONS[settings.orientation] ? settings.orientation : 'portrait'
  const [width, height] = PAGE_SIZES[size].mm
  return {
    paged: !!settings.paged,
    size,
    orientation,
    width: orientation === 'landscape' ? height : width,
    height: orientation === 'landscape' ? width : height,
    margin: MARGINS[settings.margin]?.mm ?? MARGINS.normal.mm,
    letterHead: settings.letter_head || '',
  }
}

/**
 * The sheet, as inline style.
 *
 * Millimetres rather than pixels, so the browser does the conversion it is
 * going to do anyway when it prints. `--page` is the page height, which the
 * guide lines in `DocEditor` repeat on.
 */
export function paperStyle(settings = {}) {
  const setup = paperSetup(settings)
  if (!setup.paged) return {}
  return {
    width: `${setup.width}mm`,
    maxWidth: '100%',
    padding: `${setup.margin}mm`,
    '--page-height': `${setup.height}mm`,
  }
}
