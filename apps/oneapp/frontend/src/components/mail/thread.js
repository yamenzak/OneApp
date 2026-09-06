// The two rules that decide the shape of a conversation, away from the markup
// that draws it — both have edges a browser pass cannot reach: folding needs a
// thread of six with four of them read, and the fixture has two.

/**
 * The read run in the middle of a thread, which is hidden behind one line.
 *
 * Frappe Mail's numbers. Fewer than four read messages and folding saves a row
 * while costing a click. The first and the last of the run stay: a fold with
 * nothing above or below it reads as mail having gone missing.
 *
 * The last message in the thread is never in the run, read or not.
 */
export function foldedRead(messages) {
  const last = messages[messages.length - 1]
  // Only the run *above* the new-mail line, which is where ours parts company
  // with Frappe's: theirs collects every read message, so a fold can swallow
  // one below the "2 new messages" mark and the count then describes messages
  // in two different places.
  const mark = firstUnread(messages)
  const above = mark
    ? messages.slice(0, messages.findIndex((one) => one.name === mark))
    : messages

  const read = above.filter((one) => one.seen && one !== last)
  if (read.length < 4) return new Set()
  return new Set(read.slice(1, -1).map((one) => one.name))
}

/**
 * The message the "N new messages" line goes above, or null. Only worth marking
 * when there is something above it to divide from.
 */
export function firstUnread(messages) {
  const unread = messages.filter((one) => !one.seen)
  if (!unread.length || unread.length === messages.length) return null
  return unread[0].name
}
