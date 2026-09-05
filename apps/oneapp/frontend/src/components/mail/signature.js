/**
 * Putting an address's signature into a message, and taking it out again.
 *
 * The signature belongs to the address, not to the person — an address here is
 * a mailbox several people share — so changing who a message is from changes
 * what signs it. It goes in where somebody can see it, above the quoted
 * history, rather than being appended on the way out: a signature nobody sees
 * before they send is one they forget they have.
 *
 * Finding it again to swap it is the hard half, and the reason this takes the
 * *previous* signature as well as the next one. A marker class was the obvious
 * answer and does not survive: the rich editor normalises the body through
 * ProseMirror's schema, which does not know our class and drops it — so a
 * message that has been typed into no longer carries the mark. What it does
 * carry is the signature's own text, which is exactly the string we put there.
 * So: the mark where it survived, the text where it did not.
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

  // Never inside the quote, and the last one outside it. A reply carries the
  // other person's sign-off in the quoted history, and theirs can say exactly
  // what ours says — one person on two addresses, or two people at the same
  // firm. Taking that out would be rewriting their message.
  const candidates = [...body.querySelectorAll('p, div')].filter(
    (one) => !one.closest('blockquote') && words(one.innerHTML) === said,
  )
  candidates[candidates.length - 1]?.remove()
}

/**
 * `html` signed by `signature`, with `previous` — what the last address signed
 * with — taken out first.
 *
 * Removed rather than replaced when the new address signs with nothing, and
 * added above the quote when there is one: a signature under three screens of
 * quoted history is a signature nobody reads.
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
    // wrote:" belongs to the quote, and a signature between the two reads as
    // part of what is being quoted.
    const before = quote?.previousElementSibling || quote
    if (before) body.insertBefore(block.firstChild, before)
    else body.append(block.firstChild)

    // Somewhere to type. A composer whose only content is the signature puts
    // the caret *under* it, and the first thing anybody writes lands after
    // their own sign-off.
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
