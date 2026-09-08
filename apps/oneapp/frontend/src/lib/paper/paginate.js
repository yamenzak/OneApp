/*
 * Where the pages actually break.
 *
 * A hairline every page height was a guide: it said where a page ends and left
 * the reader to imagine the rest. This measures instead. It walks the blocks
 * the editor has laid out, finds the first one that would not fit on the page
 * it is on, and pushes it onto the next one — then says where each page
 * starts, which is where the letter head goes and where the sheets are drawn
 * apart.
 *
 * The push is a *stylesheet* rather than an inline style, and that is the whole
 * reason this file exists rather than three lines in the component. Setting
 * `style.marginTop` on a paragraph inside the editable looks like it works and
 * then silently undoes itself: ProseMirror watches the editable for mutations
 * it did not make, decides the DOM has diverged from its state, and redraws the
 * node from state — taking the margin with it. A rule in a `<style>` element
 * outside the editable is not a mutation of the editable at all.
 *
 * The browser does the measuring here and the pagination there, which is what
 * lets the two agree: the same engine lays the same blocks out at the same
 * width in the same face, and a page holds what a page holds.
 * `docs/typography.py` is the other half of that bargain.
 *
 * What it does not do is break *inside* a block. A table taller than a page
 * runs over the bottom of it here and is split by the print engine there; the
 * honest fix is a renderer of our own, and that is a bigger thing than this.
 */

/** Half a pixel. Rects are fractional, and a block that ends exactly on the
 *  boundary belongs to the page above it. */
const EPS = 0.5

/** Blocks that must not be the last thing on a page — a heading with nothing
 *  under it is the one break every reader notices. */
const ORPHANS = new Set(['H1', 'H2', 'H3', 'H4', 'H5', 'H6'])

/**
 * Lay `content`'s children out on pages, and say where each page starts.
 *
 * @param {HTMLElement} sheet    the page-width element; the origin for every y
 * @param {HTMLElement} content  the editable, whose children are the blocks
 * @param {HTMLStyleElement} rules  where the pushes are written
 * @param {string} scope         an attribute selector naming this one sheet
 * @param {object} page   { pageHeight, marginPx, stride } from `geometry()`
 * @param {number} headHeight    how much of each page the letter head takes
 * @returns {{ pages: number, tops: number[], height: number }}
 */
export function paginate(sheet, content, rules, scope, page, headHeight = 0) {
  const blocks = Array.from(content.children)
  const tops = [0]
  const pushes = []

  // Back to one continuous flow before anything is measured: last pass's
  // pushes are last pass's answer, and measuring against them compounds.
  rules.textContent = ''

  if (!blocks.length) {
    return { pages: 1, tops, height: page.pageHeight }
  }

  const origin = sheet.getBoundingClientRect().top
  const y = (node, edge) => node.getBoundingClientRect()[edge] - origin

  // Where the text may sit on page `p`: below its top margin and its letter
  // head, above its bottom margin.
  const textTop = (p) => p * page.stride + page.marginPx + headHeight
  const textEnd = (p) => p * page.stride + page.pageHeight - page.marginPx

  let current = 0
  for (let index = 1; index < blocks.length; index += 1) {
    if (y(blocks[index], 'bottom') <= textEnd(current) + EPS) continue

    // The block does not fit. Push it — or, if the block above it is a heading
    // it would be stranded from, push the heading too.
    let first = index
    if (ORPHANS.has(blocks[index - 1].tagName) && index - 1 > 0) first = index - 1

    current += 1
    const space = Math.max(0, textTop(current) - y(blocks[first - 1], 'bottom'))
    // `:nth-child` is one-based, and writing the rule re-lays the page out, so
    // every measurement after this one already accounts for it.
    pushes.push(`${scope} > :nth-child(${first + 1}) { margin-top: ${space}px; }`)
    rules.textContent = pushes.join('\n')

    tops.push(current * page.stride)
    index = first
  }

  return {
    pages: current + 1,
    tops,
    height: current * page.stride + page.pageHeight,
  }
}
