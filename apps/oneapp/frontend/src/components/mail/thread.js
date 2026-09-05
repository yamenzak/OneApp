// The two rules that decide the shape of a conversation, away from the markup
// that draws it — because both have edges a browser pass cannot reach. Folding
// needs a thread of six with four of them read; the fixture has two.

/**
 * The read run in the middle of a thread, which is hidden behind one line.
 *
 * Frappe Mail's numbers, and they are the right ones. Fewer than four read
 * messages and folding saves a row while costing a click, so it does not
 * happen. The first and the last of the run stay: a fold with nothing above or
 * below it reads as mail having gone missing rather than as mail put away.
 *
 * The last message in the thread is never in the run, read or not — it is the
 * one somebody opened the conversation to see.
 */
export function foldedRead(messages) {
  const last = messages[messages.length - 1]
  // Only the run *above* the new-mail line, which is where ours parts company
  // with Frappe's: theirs collects every read message in the thread, so a fold
  // can swallow one that sits below the "2 new messages" mark and the count
  // then describes messages in two different places. What folds here is one
  // contiguous run, and it is the one nobody has anything new in.
  const mark = firstUnread(messages)
  const above = mark
    ? messages.slice(0, messages.findIndex((one) => one.name === mark))
    : messages

  const read = above.filter((one) => one.seen && one !== last)
  if (read.length < 4) return new Set()
  return new Set(read.slice(1, -1).map((one) => one.name))
}

/**
 * The message the "N new messages" line goes above, or null.
 *
 * Only worth marking when there is something above it to divide from: in a
 * thread where everything is new the line is a header on the whole thread, and
 * in one where nothing is there is no line at all.
 */
export function firstUnread(messages) {
  const unread = messages.filter((one) => !one.seen)
  if (!unread.length || unread.length === messages.length) return null
  return unread[0].name
}
