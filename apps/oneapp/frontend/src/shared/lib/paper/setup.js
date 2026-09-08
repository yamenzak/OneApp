/*
 * Paper: the page a document or a sheet sits on, in the browser.
 *
 * Here rather than beside the document toolbar because a sheet's print dialog
 * needs the same nine numbers, and reaching them through `docs/toolbar.js`
 * would pull the whole tiptap toolbar into the spreadsheet's bundle.
 *
 * The same five sizes and three margins `shared/paper.py` offers, in
 * millimetres, because the editor has to draw the sheet the server will print
 * — a page that looks A4 on screen and prints Letter is worse than no page at
 * all. Kept as a copy rather than fetched: it is nine numbers that have not
 * changed since ISO 216 in 1975, and a page setup dialog that waits on a
 * request to know how wide A4 is would be a dialog that flickers.
 */

import { __ } from '@/shared/lib/runtime/translate'

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

/*
 * The type a paged document is set in — `onedoc/typography.py`,
 * mirrored, and `tests/test_paper.py` reads the two back against each other.
 *
 * A page that reflows on the way to the printer is the whole thing pagination
 * is here to prevent, so the sheet on screen is set in the face the exported
 * file is set in: the system sans rather than the app's Inter, which is a web
 * font a standalone HTML file cannot carry.
 *
 * The leading matters for a second reason. `prose-sm` sets `line-height` on
 * the element it is on and the `leading-*` class sits on the wrapper above it,
 * so picking a line spacing changed nothing; these go on inline, where they
 * win.
 */
export const FACES = {
  '': '-apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
  serif: 'Georgia, Cambria, "Times New Roman", Times, serif',
  mono: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
}

export const LEADING = { tight: 1.5, normal: 1.7142857, loose: 2 }

/** How far a measured margin may go, the same clamp `paper.setup_of` applies. */
export const MARGIN_MIN = 0
export const MARGIN_MAX = 60

/** One CSS millimetre. The browser's own number: 96dpi over 25.4mm an inch. */
export const MM = 96 / 25.4

/** The gap drawn between two sheets on screen. Nothing to do with the page. */
export const SHEET_GAP = 24

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
    // A preset name, or a number of millimetres somebody typed — the same two
    // shapes `paper.setup_of` takes, because somebody printing onto headed
    // stationery has a measurement rather than a preference.
    margin: marginMm(settings.margin),
    letterHead: settings.letter_head || '',
  }
}

/** Millimetres of margin, from a preset name or a measured number. */
export function marginMm(given) {
  const measured = Number(given)
  if (Number.isFinite(measured) && typeof given !== 'string') {
    return Math.max(MARGIN_MIN, Math.min(MARGIN_MAX, measured))
  }
  return MARGINS[given]?.mm ?? MARGINS.normal.mm
}

/** The type one document is set in, for the element that has to carry it. */
export function typeStyle(settings = {}) {
  return {
    fontFamily: FACES[settings.font] ?? FACES[''],
    lineHeight: String(LEADING[settings.spacing] ?? LEADING.normal),
  }
}

/**
 * The page, in pixels, for the editor that has to draw it.
 *
 * `stride` is where the next sheet starts and is a page plus the gap between
 * sheets — a screen decision, not a paper one, and the reason it is a separate
 * number from `height`.
 */
export function geometry(settings = {}) {
  const setup = paperSetup(settings)
  const height = setup.height * MM
  const margin = setup.margin * MM
  return {
    ...setup,
    pageWidth: setup.width * MM,
    pageHeight: height,
    marginPx: margin,
    stride: height + SHEET_GAP,
    gap: SHEET_GAP,
  }
}

/**
 * The sheet, as inline style.
 *
 * Millimetres rather than pixels, so the browser does the conversion it is
 * going to do anyway when it prints. Everything else about the page — where
 * the breaks fall, where each sheet starts — is measured, not styled, and
 * lives in `paginate.js`.
 */
export function paperStyle(settings = {}) {
  const setup = paperSetup(settings)
  if (!setup.paged) return {}
  return {
    width: `${setup.width}mm`,
    maxWidth: '100%',
    padding: `${setup.margin}mm`,
  }
}
