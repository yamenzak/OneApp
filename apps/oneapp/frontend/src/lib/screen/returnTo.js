/**
 * Where an editor came from, so closing it goes back rather than to the Drive.
 *
 * A sheet and a document are pages, and that is right: a spreadsheet needs the
 * width and a drawer would give it four rows of chrome and no grid. But a page
 * reached *from* a record used to throw the record away — press "Open in a
 * sheet" on a quotation's line items and closing the sheet left you at the
 * Drive's root, with the quotation, its tab and its scroll position gone.
 *
 * So the record travels in the URL. `provide`/`inject` rather than four props,
 * because the thing that knows the record's name — `RecordView` — is four
 * components above the buttons that need it, and every one in between would
 * otherwise carry a prop it does not use.
 *
 * The path is checked before it is followed. It is a URL parameter, so it is
 * whatever the last person to edit the address bar put there, and a bare
 * `startsWith('/')` still admits `//evil.example` — which a router happily
 * treats as another origin.
 */

/** The injection key. A Symbol, so nothing collides with it by accident. */
export const RETURN_TO = Symbol('onespace.return-to')

export const BACK = 'back'
export const BACK_LABEL = 'backLabel'

/**
 * The query a link carries so what it opens knows the way back. Empty when
 * there is nowhere to go — a sheet made from the Drive belongs to the Drive.
 */
export function returnQuery(came) {
  if (!came?.path || !came?.label) return {}
  return { [BACK]: came.path, [BACK_LABEL]: came.label }
}

/** Where back is, read off an editor's own route. `null` for "nowhere". */
export function cameFrom(route) {
  const path = route?.query?.[BACK]
  if (typeof path !== 'string') return null
  if (!path.startsWith('/') || path.startsWith('//')) return null
  const label = String(route.query[BACK_LABEL] || '').trim()
  return label ? { path, label } : null
}
