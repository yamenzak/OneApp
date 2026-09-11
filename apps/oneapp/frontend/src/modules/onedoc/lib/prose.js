/**
 * Plain text a model wrote, as the HTML tiptap will parse.
 *
 * The prompts in `onedoc/intelligence.py` ask for plain text and say why:
 * the editor owns the formatting, and a model that answers in Markdown puts
 * asterisks in a document somebody sends. So what comes back is paragraphs
 * separated by blank lines — and turning that into blocks is this file.
 *
 * The one piece of structure it does recover is the document's own headings.
 * `fill` is given the headings and told to keep them, so a line that *is* one
 * of them is a heading rather than a one-line paragraph. Matched against the
 * list the document actually has rather than guessed at from punctuation: a
 * heuristic that promoted "Payment terms are net 30." would be worse than no
 * headings at all.
 */

const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;' }

function escaped(said) {
  return String(said ?? '').replace(/[&<>]/g, (one) => ESCAPES[one])
}

/** A key two spellings of the same heading agree on. */
const key = (said) => said.trim().toLowerCase().replace(/\s+/g, ' ').replace(/[:.]+$/, '')

/**
 * @param {string} said  what the model wrote
 * @param {string[]} headings  the document's own headings, if it had any
 * @returns {string} HTML for `insertContentAt` or `setContent`
 */
export function asProse(said, headings = []) {
  const known = new Set((headings || []).map(key).filter(Boolean))
  const blocks = []
  let paragraph = []

  const flush = () => {
    if (paragraph.length) blocks.push(`<p>${paragraph.join('<br>')}</p>`)
    paragraph = []
  }

  for (const raw of String(said || '').split('\n')) {
    const line = raw.trim()
    if (!line) {
      flush()
      continue
    }
    if (known.has(key(line))) {
      flush()
      blocks.push(`<h2>${escaped(line)}</h2>`)
      continue
    }
    paragraph.push(escaped(line))
  }
  flush()

  // A paragraph, not nothing: an empty string leaves `insertContentAt` with
  // no node to place and the insert silently does not happen, which reads as
  // a run that produced an answer and lost it.
  return blocks.join('') || '<p></p>'
}
