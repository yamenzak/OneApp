/**
 * Every query parameter this product puts in a URL, in one list.
 *
 * A URL is the only part of the interface a person can send to a colleague,
 * and it was the part nobody owned: thirteen parameters across five surfaces,
 * three naming conventions for the same idea, and no way to tell from reading
 * one what kind of thing it pointed at. A reader could not, and neither could
 * a link handler.
 *
 * So the set is declared here and a guard refuses anything outside it. The
 * list *is* the documentation — there is nowhere else to look and nowhere
 * else to add one.
 *
 * The division is the useful part, and it is the same question twice:
 *
 *   **Where you are.** The screen, the view, the place in the Drive, the
 *   folder, the order. These say what surface you are on and how it is
 *   arranged, and they keep their own names because each really is a
 *   different idea.
 *
 *   **What you have open.** One parameter — `at` — carrying a typed
 *   reference, because "which one of these am I looking at" is one question
 *   and it had five answers with five shapes. See `at.js`.
 *
 *   **What a panel is showing.** A dialog with an address is a dialog
 *   somebody can be sent to, which is what makes "open settings, then find
 *   Backups" into a link.
 *
 *   **Passing through.** What an external service sends back on a redirect.
 *   Read once and removed from the URL, never written by us.
 *
 * `docs/UNIFICATION.md` §C4.
 */

/** Where you are. */
export const PLACE = Object.freeze({
  screen: 'Which screen of a space.',
  type: 'Which view type — list, board, grid, report, calendar, tree, gantt.',
  layout: 'Which saved view.',
  place: "Which of the Drive's places — home, recents, favourites, trash.",
  folder: 'Which folder, inside a place. A `File` name, or a `remote://` mount.',
  sort: 'Which column an order is by. A key from the server\'s allowlist.',
  desc: '`1` when that order is reversed.',
  as: 'Which way the Drive draws its rows — `grid` or a list.',
  overlay: "Which layer the mobility map is showing.",
  workspace: 'Which workspace, on the account screens, for somebody who has more than one.',
})

/** What you have open. */
export const OPEN = Object.freeze({
  at: 'The one thing this surface has open, typed — see `lib/url/at.js`.',
})

/**
 * What `at` replaces, still in use until each surface moves.
 *
 * Five parameters for one question, and each answers it differently: `record`
 * is an id, `thread` a key, `chat` a session name, and `peek` needs a second
 * parameter beside it to say which screen's rules apply. They are declared
 * here rather than left undeclared so that the guard is true today, and this
 * block is meant to become empty.
 */
export const SUPERSEDED = Object.freeze({
  record: 'Which record a screen has open.',
  peek: 'Which record is open *beside* what you are doing.',
  peekScreen: "That record's own screen, because it is usually not this one.",
  thread: 'Which conversation is open in the mailbox.',
  chat: 'Which conversation with the assistant.',
})

/** What a panel is showing. */
export const PANELS = Object.freeze({
  panel: 'Which settings panel is open.',
  ask: 'The assistant, open, on this conversation. Empty for a new one.',
  filters: '`open` when the filter panel is showing.',
})

/** Where an editor goes back to — `lib/screen/returnTo.js`. */
export const RETURN = Object.freeze({
  back: 'The path a full-bleed editor closes to. Validated as same-site.',
  backLabel: 'What that place is called, for the crumb.',
})

/** Passing through, from somewhere else. */
export const INBOUND = Object.freeze({
  checkout: 'How a Stripe checkout ended — `success` or `cancelled`.',
  session: "Stripe's own id for it.",
  request: 'Which signup a new workspace is being built for, while it builds.',
})

/** The whole set, which is what the guard reads. */
export const DECLARED = Object.freeze(
  Object.keys({ ...PLACE, ...OPEN, ...SUPERSEDED, ...PANELS, ...RETURN, ...INBOUND }),
)
