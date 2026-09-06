/**
 * Putting an address's signature into a message, and taking it out again.
 *
 * The signature belongs to the address, not to the person. It goes in where
 * somebody can see it, above the quoted history, rather than being appended on
 * the way out.
 *
 * Finding it again to swap it is the hard half, and the reason this takes the
 * *previous* signature as well as the next. A marker class does not survive:
 * the rich editor normalises the body through ProseMirror's schema, which drops
 * a class it does not know. What survives is the signature's own text. So: the
 * mark where it survived, the text where it did not.
 */

/** The class the wrapper carries, for as long as it survives an edit. */
export const MARK = 'oneapp-signature'

/** The words of a signature, markup stripped, for finding it again later. */
function words(html) {
  const doc = new DOMParser().parseFromString(html || '', 'text/html')
  return (doc.body.textContent || '').replace(/\s+/g, ' ').trim()
}

/** Take out whatever is currently signing this message. */
function unsign(body, previous) {
  const marked = body.querySelector(`.${MARK}`)
  if (marked) {
    marked.remove()
    return
  }

  const said = words(previous)
  if (!said) return

  // Never inside the quote, and the last one outside it: a reply carries the
  // other person's sign-off in the quoted history, and theirs can say exactly
  // what ours says.
  const candidates = [...body.querySelectorAll('p, div')].filter(
    (one) => !one.closest('blockquote') && words(one.innerHTML) === said,
  )
  candidates[candidates.length - 1]?.remove()
}

/**
 * `html` signed by `signature`, with `previous` taken out first. Removed rather
 * than replaced when the new address signs with nothing, and added above the
 * quote when there is one.
 */
export function withSignature(html, signature, previous = '') {
  const doc = new DOMParser().parseFromString(html || '', 'text/html')
  const body = doc.body

  unsign(body, previous)

  if ((signature || '').trim()) {
    const block = doc.createElement('div')
    block.innerHTML = `<div class="${MARK}"><br>${signature}</div>`
    const quote = body.querySelector('blockquote')
    // Before the attribution line as well as the quote — "On Tuesday, Hala
    // wrote:" belongs to the quote.
    const before = quote?.previousElementSibling || quote
    if (before) body.insertBefore(block.firstChild, before)
    else body.append(block.firstChild)

    // Somewhere to type: a composer whose only content is the signature puts
    // the caret *under* it.
    if (body.firstElementChild === body.querySelector(`.${MARK}`)) {
      const room = doc.createElement('p')
      room.innerHTML = '<br>'
      body.insertBefore(room, body.firstElementChild)
    }
  }

  return body.innerHTML
}

/** Whether this body still carries the mark. Only true before an edit. */
export const hasSignature = (html) =>
  new DOMParser().parseFromString(html || '', 'text/html').body.querySelector(`.${MARK}`) !== null
