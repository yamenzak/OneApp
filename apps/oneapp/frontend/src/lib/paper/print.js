/**
 * Print a whole HTML page that is not this one.
 *
 * `window.print()` prints the window, and the window is the app — its sidebar,
 * its header, its scrollbars, and `@page` rules nobody wrote. What a document
 * or a sheet wants printed is the page the server built for it: the right
 * size, the right margins, and the letter head repeating on every sheet
 * through the `<thead>` that `oneapp_core/paper.py` wraps it in.
 *
 * So the page goes into an iframe and the iframe prints itself. The same
 * mechanism `screen/record/PrintDialog.vue` uses for a record's print format,
 * and for the same reason — a page's stylesheet is written to win against a
 * blank document, so putting it in this one would restyle the app around it.
 */

/** Sandboxed the way the record's preview is: no scripts, modals allowed so
 *  the browser's print dialog can open, same-origin so `contentWindow` is
 *  reachable at all. */
const SANDBOX = 'allow-same-origin allow-modals'

export function printHtml(html) {
  return new Promise((resolve) => {
    const frame = document.createElement('iframe')
    frame.setAttribute('sandbox', SANDBOX)
    frame.setAttribute('aria-hidden', 'true')
    // Off-screen rather than `display: none`: a frame with no layout box is
    // one some engines never lay out, and an unlaid-out page prints blank.
    frame.style.cssText =
      'position:fixed;right:0;bottom:0;width:1px;height:1px;opacity:0;border:0;'

    let done = false
    const finish = () => {
      if (done) return
      done = true
      // After the print dialog has closed, which is when `print()` returns in
      // every engine but Safari — where the timeout is what saves it.
      setTimeout(() => frame.remove(), 1000)
      resolve()
    }

    frame.onload = () => {
      const view = frame.contentWindow
      if (!view) return finish()
      view.focus()
      try {
        view.print()
      } finally {
        finish()
      }
    }

    document.body.appendChild(frame)
    frame.srcdoc = html
  })
}
