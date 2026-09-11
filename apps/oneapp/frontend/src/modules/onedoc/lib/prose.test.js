import { describe, expect, it } from 'vitest'

import { asProse } from './prose'

describe('asProse', () => {
  it('makes a paragraph of each blank-line-separated block', () => {
    expect(asProse('One.\n\nTwo.')).toBe('<p>One.</p><p>Two.</p>')
  })

  it('keeps a line break inside a block', () => {
    // Two lines of an address are two lines, not two paragraphs.
    expect(asProse('Al Reem Consultants\nPO Box 4471')).toBe(
      '<p>Al Reem Consultants<br>PO Box 4471</p>',
    )
  })

  it('promotes a line that is one of the document own headings', () => {
    expect(asProse('Scope of works\n\nThe cladding.', ['Scope of works'])).toBe(
      '<h2>Scope of works</h2><p>The cladding.</p>',
    )
  })

  it('matches a heading loosely enough to survive a colon and a case', () => {
    expect(asProse('SCOPE OF WORKS:', ['Scope of works'])).toBe(
      '<h2>SCOPE OF WORKS:</h2>',
    )
  })

  it('promotes nothing when the document had no headings', () => {
    // The alternative is a heuristic, and a heuristic that promoted
    // "Payment terms are net 30." would be worse than no headings at all.
    expect(asProse('Scope of works')).toBe('<p>Scope of works</p>')
  })

  it('escapes what a record put in the text', () => {
    expect(asProse('Rate < 5% & rising')).toBe('<p>Rate &lt; 5% &amp; rising</p>')
  })

  it('answers with an empty paragraph rather than nothing', () => {
    // `insertContentAt` with no node places nothing, which reads as a run
    // that produced an answer and lost it.
    expect(asProse('')).toBe('<p></p>')
    expect(asProse('   \n  ')).toBe('<p></p>')
  })
})
