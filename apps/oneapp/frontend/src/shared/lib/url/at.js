/**
 * What a surface has open, as one typed reference.
 *
 * Several parameters used to answer this question and each answered it
 * differently: `record` was an id, `chat` a session name, and
 * `peek` needed a second parameter beside it to say which screen's rules
 * applied. A reader could not look at a URL and tell what kind of thing it
 * pointed at, and neither could anything that had to handle a link.
 *
 * So there is one parameter and it says its own kind:
 *
 *     ?at=record:TASK-0001          the record this screen has open
 *     ?at=chat:s-9f2                a conversation with the assistant
 *
 * **It is a stack, outermost first**, because a surface really can have two
 * things open: you are reading an invoice, you glance at the client it is
 * for, and the client opens in a drawer *over* the invoice rather than
 * instead of it.
 *
 *     ?at=record:INV-0007|peek:clients/CL-0003
 *
 * That is what "peek is a modifier on `at`" means in practice, and it is the
 * part worth getting right: a single slot would have had the drawer erase the
 * record underneath it, which is exactly the thing a drawer exists not to do.
 * A peek carries its screen because what is being peeked at is usually on a
 * different one — a project's invoices are the invoices screen, and a name
 * with no screen is a name the host would look up in the wrong place.
 *
 * What is deliberately *not* here is `screen`, `type`, `layout`, `place` and
 * `folder`. Those say where you are; this says what you have open, and the
 * distinction is worth keeping in the URL's shape because it is the one a
 * reader makes anyway.
 *
 * `docs/UNIFICATION.md` §C4.
 */

/** The kinds. Another needs a line here and a surface that opens it. */
export const KIND = Object.freeze({
  RECORD: 'record',
  PEEK: 'peek',
  CHAT: 'chat',
})

const KINDS = Object.freeze(Object.values(KIND))

/**
 * The kinds you may have more than one of open.
 *
 * Only peeks. A surface has one record open, one chat — those are
 * *where you are*, and two of them is a contradiction. A peek is a glance at
 * something else, and glancing at a second thing is not a reason to forget the
 * first: you are reading an invoice, you look at its client, then at the
 * project the client is on, and pressing back should walk that back rather
 * than drop you on the invoice having lost the middle.
 *
 * `docs/DESKTOP.md` — this is the "window that tabs", with the dock as the tab
 * bar and no hibernation machinery, because a preview is read-only and has
 * nothing worth keeping alive.
 */
const STACKABLE = Object.freeze(new Set([KIND.PEEK]))

/** What separates one from the next. Not a character a name carries. */
const STACK = '|'

/**
 * Read one reference.
 *
 * Returns `null` for anything it cannot read, which is the same answer as
 * "nothing is open" on purpose: a URL somebody mistyped should land on the
 * list rather than on an error, and every caller already draws that.
 */
export function readOne(value) {
  const text = String(value ?? '')
  const cut = text.indexOf(':')
  if (cut < 1) return null

  const kind = text.slice(0, cut)
  const ref = text.slice(cut + 1)
  if (!KINDS.includes(kind) || !ref) return null

  if (kind !== KIND.PEEK) return { kind, ref, screen: '' }

  // A peek's reference is `<screen>/<name>`, and a name may itself contain a
  // slash — `Home/Attachments` is a real `File` name — so the split is on the
  // *first* one only.
  const slash = ref.indexOf('/')
  if (slash < 1) return null
  const screen = ref.slice(0, slash)
  const name = ref.slice(slash + 1)
  return name ? { kind, ref: name, screen } : null
}

/**
 * The whole stack, outermost first.
 *
 * An entry nobody can read is dropped rather than failing the rest: half a URL
 * understood is better than none, and the thing it would have opened was
 * already not going to open.
 */
export function readAt(value) {
  return String(value ?? '')
    .split(STACK)
    .map(readOne)
    .filter(Boolean)
}

/**
 * Write one.
 *
 * `undefined` rather than an empty string for nothing open: that is what tells
 * Vue Router to leave the key out altogether, and a `?at=` hanging off every
 * URL would be a URL that looks like it is holding something.
 */
export function writeAt(kind, ref, screen = '') {
  if (!kind || !ref) return undefined
  if (!KINDS.includes(kind)) {
    throw new Error(
      `"${kind}" is not a kind of thing a surface can have open. `
      + `It is one of: ${KINDS.join(', ')}.`,
    )
  }
  if (kind === KIND.PEEK) return screen ? `peek:${screen}/${ref}` : undefined
  return `${kind}:${ref}`
}

/** What this route has open of this kind, or `''`. The *outermost*, which for
 *  every kind but a peek is the only one. */
export function atOf(query, kind) {
  const found = readAt(query?.at).find((one) => one.kind === kind)
  return found ? found.ref : ''
}

/**
 * Everything open of one kind, outermost first — `[{ ref, screen }]`.
 *
 * What a stackable kind is read with. For the rest it is `atOf` in a list of
 * one, and saying so is cheaper than every caller knowing which is which.
 */
export function allAt(query, kind) {
  return readAt(query?.at)
    .filter((one) => one.kind === kind)
    .map((one) => ({ ref: one.ref, screen: one.screen }))
}

/** A peek's screen, or `''` — the half `atOf` does not return. */
export function peekScreenOf(query) {
  const found = readAt(query?.at).find((one) => one.kind === KIND.PEEK)
  return found ? found.screen : ''
}

/** The stack as it goes in a URL, or `undefined` when nothing is open. */
const stack = (open) => (
  open.length
    ? open.map((one) => writeAt(one.kind, one.ref, one.screen)).filter(Boolean).join(STACK)
    : undefined
)

/**
 * The query with one thing open, and nothing else.
 *
 * Takes the whole query so a caller does not have to remember to spread it:
 * dropping the rest of the URL to open a record is how a saved view and a
 * folder get lost. `kind` of nothing closes everything.
 */
export function withAt(query, kind, ref, screen = '') {
  const next = { ...(query || {}) }
  const value = kind ? writeAt(kind, ref, screen) : undefined
  if (value) next.at = value
  else delete next.at
  return next
}

/**
 * The query with one more thing open, over what already is.
 *
 * This is the window over the page: the record underneath stays in the URL, so
 * closing it is a pop rather than a guess about where to go back to, and the
 * browser's own back button does the same thing.
 *
 * A second one of a **stackable** kind goes on top of the first rather than
 * replacing it, and the same one twice is a raise rather than a duplicate —
 * pressing the same client's link from two different invoices should bring
 * the window you already have to the front. Everything else still replaces:
 * two records open on one surface is a contradiction, not a stack.
 */
export function pushAt(query, kind, ref, screen = '') {
  const value = writeAt(kind, ref, screen)
  if (!value) return { ...(query || {}) }
  const open = readAt(query?.at).filter((one) => (
    STACKABLE.has(kind)
      ? !(one.kind === kind && one.ref === ref && one.screen === screen)
      : one.kind !== kind
  ))
  return { ...(query || {}), at: stack([...open, { kind, ref, screen }]) }
}

/**
 * The query with one thing of this kind closed — or all of them.
 *
 * `ref` names which, for a kind you may have several of: closing the third
 * peek should not close the two under it. Without one this still closes every
 * one of the kind, which is what a surface leaving does.
 */
export function popAt(query, kind, ref = '', screen = '') {
  const next = { ...(query || {}) }
  const open = readAt(query?.at).filter((one) => (
    one.kind !== kind
    || (ref && !(one.ref === ref && one.screen === screen))
  ))
  const value = stack(open)
  if (value) next.at = value
  else delete next.at
  return next
}
