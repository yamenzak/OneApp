/**
 * Handing the reader a file the browser made rather than one the server served.
 *
 * A download normally means a URL: the browser asks for it, the server answers
 * with a `Content-Disposition`, and the file lands. That path is wrong for
 * anything a whitelisted method computes — the URL would have to carry the
 * screen, the saved view, the unsaved filters and the selection as query
 * parameters, and it would be a second way into the data with its own
 * authentication story.
 *
 * So the method answers with the file's *contents* like any other call, and
 * this turns that into a download. Same request, same session, same permission
 * check as every other read on the page.
 */

/**
 * Save some text as a file called `filename`.
 *
 * The object URL is revoked on the next frame rather than immediately: Safari
 * has historically cancelled a download whose blob URL was revoked in the same
 * tick as the click, and a revoke one frame later costs nothing.
 */
export function saveText(filename, text, type = 'text/plain;charset=utf-8') {
  const url = URL.createObjectURL(new Blob([text], { type }))
  const link = document.createElement('a')
  link.href = url
  link.download = filename || 'download'
  // Appended before clicking: Firefox ignores a click on a link that is not in
  // the document.
  document.body.appendChild(link)
  link.click()
  link.remove()
  requestAnimationFrame(() => URL.revokeObjectURL(url))
}

/** The same, for a CSV — the one type that needs its own MIME to open right. */
export function saveCsv(filename, text) {
  saveText(filename, text, 'text/csv;charset=utf-8')
}
