/**
 * The drawing half of branching.
 *
 * `oneapp/oneforms/showing.py` is the deciding half and `tests/
 * test_forms_showing.py` holds it to the same comparisons. What is here is what
 * only the browser does: redraw as somebody types, and stop sending an answer
 * to a question that stopped being asked.
 */

import { describe, expect, it } from 'vitest'

import { answered, asked, holds } from './showing.js'

const field = (fieldname, shown_when) => ({ fieldname, fieldtype: 'Data', shown_when })

describe('comparing', () => {
  it('is true when there is no condition', () => {
    expect(holds(undefined, {})).toBe(true)
    expect(holds({}, {})).toBe(true)
  })

  it('reads Yes and yes as the same answer', () => {
    const rule = { field: 'agreed', op: '==', value: 'yes' }
    expect(holds(rule, { agreed: 'Yes' })).toBe(true)
    expect(holds(rule, { agreed: ' YES ' })).toBe(true)
    expect(holds(rule, { agreed: 'no' })).toBe(false)
  })

  it('compares a number typed into a box as a number', () => {
    expect(holds({ field: 'n', op: '==', value: '3' }, { n: '3' })).toBe(true)
    expect(holds({ field: 'n', op: '>', value: '2' }, { n: 3 })).toBe(true)
    expect(holds({ field: 'n', op: '>', value: '2' }, { n: '1' })).toBe(false)
  })

  it('reads a checkbox whichever way it arrives', () => {
    for (const sent of [1, true, '1', 'true']) {
      expect(holds({ field: 'a', op: '==', value: '1' }, { a: sent })).toBe(true)
    }
    for (const sent of [0, false, '0', 'false', '']) {
      expect(holds({ field: 'a', op: '==', value: '1' }, { a: sent })).toBe(false)
    }
  })

  it('is false for an ordering against nothing rather than throwing', () => {
    expect(holds({ field: 'n', op: '>', value: '2' }, {})).toBe(false)
    expect(holds({ field: 'n', op: '>', value: '2' }, { n: '' })).toBe(false)
  })

  it('takes one of several', () => {
    const rule = { field: 'k', op: 'in', value: 'car, van' }
    expect(holds(rule, { k: 'van' })).toBe(true)
    expect(holds(rule, { k: 'boat' })).toBe(false)
  })
})

describe('what is being asked', () => {
  const FORM = [
    field('kind'),
    field('other', { field: 'kind', op: '==', value: 'other' }),
    { ...field('secret'), hidden: 1 },
  ]

  it('leaves out what the condition puts away, and what is hidden outright', () => {
    expect(asked(FORM, { kind: 'car' }).map((one) => one.fieldname)).toEqual(['kind'])
    expect(asked(FORM, { kind: 'other' }).map((one) => one.fieldname))
      .toEqual(['kind', 'other'])
  })

  it('redraws as the answer above it changes', () => {
    const values = { kind: 'other' }
    expect(asked(FORM, values)).toHaveLength(2)
    values.kind = 'car'
    expect(asked(FORM, values)).toHaveLength(1)
  })
})

describe('what is sent', () => {
  const FORM = [
    field('kind'),
    field('other', { field: 'kind', op: '==', value: 'other' }),
    { ...field('stamp'), hidden: 1 },
  ]

  it('drops the answer to a question that stopped being asked', () => {
    // Typed "a reason", then changed their mind about `kind`. Sending it would
    // file an answer to something nobody was asked.
    const sent = answered(FORM, { kind: 'car', other: 'a reason' })

    expect(sent).toEqual({ kind: 'car', stamp: undefined })
    expect('other' in sent).toBe(false)
  })

  it('keeps it once the question is being asked again', () => {
    expect(answered(FORM, { kind: 'other', other: 'a reason' }).other).toBe('a reason')
  })

  it('still sends a field the form hides outright', () => {
    // Hidden is not "not asked": it is how a form carries something it was
    // given, and the invitation's pre-filled values arrive that way.
    expect('stamp' in answered(FORM, { kind: 'car', stamp: 'x' })).toBe(true)
  })
})
