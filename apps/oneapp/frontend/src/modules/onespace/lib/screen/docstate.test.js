import { describe, expect, it } from 'vitest'

import { docBadge } from './docstate'

describe('docBadge', () => {
  it('is nothing at all where there is no state', () => {
    expect(docBadge(null)).toBe(null)
    expect(docBadge({ submittable: false, status: 'Draft' })).toBe(null)
  })

  it('draws the docstatus on a submittable doctype', () => {
    expect(docBadge({ submittable: true, status: 'Submitted' }))
      .toEqual({ label: 'Submitted', theme: '' })
  })

  it('says nothing the screen is already saying beside it', () => {
    // The case that is easy to miss: a doctype whose own status Select
    // *contains* the docstatus words. `Salary Slip.status` is Draft,
    // Submitted, Cancelled, Withheld — so a submitted payslip drew
    // "Submitted" twice, side by side, in two colours.
    expect(docBadge({ submittable: true, status: 'Submitted' }, 'status', 'Submitted'))
      .toBe(null)
    // And still draws it where the two say different things, which is the
    // ordinary case: a claim that is Submitted and Unpaid is both.
    expect(docBadge({ submittable: true, status: 'Submitted' }, 'status', 'Unpaid'))
      .toEqual({ label: 'Submitted', theme: '' })
  })

  it('leaves a workflow to the field the screen badges', () => {
    const flow = { workflow: { state: 'With legal', state_field: 'status', theme: 'blue' } }
    expect(docBadge(flow, 'status')).toBe(null)
    expect(docBadge(flow, 'custom_stage'))
      .toEqual({ label: 'With legal', theme: 'blue' })
  })
})
