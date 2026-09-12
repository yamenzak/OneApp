/**
 * What a surface can do, and why not where it cannot.
 *
 * Three findings in the audit are one finding: B1's `ListSource.capabilities`,
 * B2's "this facet is unavailable and here is why", and E1's scoped share.
 * Seen from three directions and the same underneath —
 *
 *   > A source declares what it can do, and the surface renders exactly that
 *   > much.
 *
 * A remote WebDAV mount cannot count its rows. `serviceHour` has no vehicle
 * column. A saved view of a fact table cannot be sorted by a column it does
 * not hold. In every one of those the honest answer is neither to hide the
 * control nor to offer one that fails: it is to show it, disabled, with the
 * reason. `Narrow` already does that for facets and nothing else copied it,
 * which is §F1's root cause exactly — the abstraction built at the second
 * caller and abandoned at the third.
 *
 * So: named once, here, and B1, B2 and E1 are three callers.
 *
 * ## Three states, not two
 *
 * `true`      it works — draw the control
 * `'reason'`  it cannot, and this is why — draw it disabled, say the reason
 * absent      it is not part of this surface — draw nothing
 *
 * The middle one is the whole point. "Drive has no sorting" was an omission;
 * "a mount is read over WebDAV, which returns a directory in the order the
 * server felt like" is a decision with its reason attached, and a person who
 * reads it stops looking for the control.
 *
 * `docs/UNIFICATION.md` §F1, §B1, §B2, §E1.
 */

/**
 * The vocabulary. Every list surface in the product offers some subset of
 * these, and until §B1 each one decided for itself which — the audit's table
 * is seventeen surfaces against fourteen columns, almost all of it blank
 * because nothing had a way to ask.
 *
 * Frozen and exported by name so a typo is a crash rather than a capability
 * that is silently never offered. That failure mode is §F1's second pattern:
 * a rule that is right and a scan with a hole in it.
 */
export const CAN = Object.freeze({
  /** Order the rows, by a column the reader picks. */
  SORT: 'sort',
  /** One box, across whatever the source considers searchable. */
  SEARCH: 'search',
  /** The narrowing bar, and the filter panel behind it. */
  FILTER: 'filter',
  /** Which columns, in which order, at which widths. */
  COLUMNS: 'columns',
  /** Keep a narrowing under a name, and share it. */
  SAVED: 'saved',
  /** How many there are in total, not only how many arrived. */
  COUNT: 'count',
  /** Rows beyond the first page. */
  PAGE: 'page',
  /** Render only what is on screen. */
  VIRTUAL: 'virtual',
  /** Collapse the rows under a column's values. */
  GROUP: 'group',
  /** Tick several and do one thing to all of them. */
  BULK: 'bulk',
  /** Make a new one from here. */
  CREATE: 'create',
  /** Take one away. */
  DELETE: 'delete',
  /** Rearrange by dragging, where the order is the data. */
  REORDER: 'reorder',
  /** Take the rows out as a file. */
  EXPORT: 'export',
})

const NAMES = Object.freeze(Object.values(CAN))

/**
 * Read a declaration.
 *
 * Takes `{ sort: true, filter: 'A mount answers in the server's own order.' }`
 * and answers three questions about it. A plain object rather than a class
 * because a source's declaration is data — it is written in the source's own
 * file beside what it does, and a surface only ever reads it.
 */
export function offers(declared = {}) {
  const said = { ...declared }

  for (const key of Object.keys(said)) {
    if (!NAMES.includes(key)) {
      throw new Error(
        `Unknown capability "${key}". It is one of: ${NAMES.join(', ')}.`,
      )
    }
  }

  return {
    /** Whether to draw the control at all — offered, or refused with a reason. */
    has: (what) => said[what] !== undefined && said[what] !== false,
    /** Whether it works. */
    can: (what) => said[what] === true,
    /** Why it does not, or '' where it does or where it is not here at all. */
    why: (what) => (typeof said[what] === 'string' ? said[what] : ''),
    /** The keys that are here but refused, for a bar that says so once. */
    refused: () => NAMES.filter((one) => typeof said[one] === 'string'),
    /** What was declared, for a guard that reads it back. */
    declared: () => ({ ...said }),
  }
}

/** Everything, and all of it working. The engine's own answer. */
export const everything = () =>
  offers(Object.fromEntries(NAMES.map((one) => [one, true])))
