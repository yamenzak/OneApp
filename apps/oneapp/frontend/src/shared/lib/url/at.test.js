import { describe, expect, it } from 'vitest'

import { KIND, allAt, atOf, peekScreenOf, popAt, pushAt, readOne, withAt, writeAt } from './at'

describe('what a surface has open', () => {
  it('round-trips every kind', () => {
    const cases = [
      [KIND.RECORD, 'TASK-0001', ''],
      [KIND.THREAD, 'a1b2c3', ''],
      [KIND.CHAT, 's-9f2', ''],
      [KIND.PEEK, 'CONT-0003', 'Contacts'],
    ]
    for (const [kind, ref, screen] of cases) {
      const written = writeAt(kind, ref, screen)
      expect(readOne(written)).toEqual({ kind, ref, screen })
    }
  })

  it('keeps a name that has a slash in it', () => {
    // `Home/Attachments` is a real `File` name, so the screen is split off at
    // the *first* slash and the rest is the name.
    const written = writeAt(KIND.PEEK, 'Home/Attachments', 'Files')
    expect(readOne(written)).toEqual({
      kind: KIND.PEEK, ref: 'Home/Attachments', screen: 'Files',
    })
  })

  it('reads nothing out of anything it does not understand', () => {
    // Every one of these lands on the list rather than on an error, which is
    // what a mistyped URL should do.
    for (const bad of ['', 'TASK-0001', 'nonsense:x', 'record:', ':x', 'peek:x',
      'peek:/x', 'peek:Contacts/', undefined, null]) {
      expect(readOne(bad)).toBeNull()
    }
  })

  it('refuses to write a kind nobody declared', () => {
    expect(() => writeAt('sheet', 'abc')).toThrow(/not a kind of thing/)
  })

  it('answers only for the kind that was asked about', () => {
    const query = { at: writeAt(KIND.THREAD, 'a1b2c3') }
    expect(atOf(query, KIND.THREAD)).toBe('a1b2c3')
    expect(atOf(query, KIND.RECORD)).toBe('')
    expect(peekScreenOf(query)).toBe('')
  })

  it('keeps a record open under the drawer over it', () => {
    // The whole reason `at` is a stack. A single slot would have had the
    // drawer erase the record underneath it, which is the one thing a drawer
    // exists not to do.
    const open = withAt({ screen: 'invoices' }, KIND.RECORD, 'INV-0007')
    const peeked = pushAt(open, KIND.PEEK, 'CL-0003', 'clients')

    expect(peeked.at).toBe('record:INV-0007|peek:clients/CL-0003')
    expect(atOf(peeked, KIND.RECORD)).toBe('INV-0007')
    expect(atOf(peeked, KIND.PEEK)).toBe('CL-0003')
    expect(peekScreenOf(peeked)).toBe('clients')

    // Closing the drawer is a pop, so the invoice is still open.
    const closed = popAt(peeked, KIND.PEEK)
    expect(closed.at).toBe('record:INV-0007')
    expect(atOf(closed, KIND.PEEK)).toBe('')

    // And a second peek stacks over the first rather than replacing it: you
    // are reading an invoice, you look at its client, then at the project that
    // client is on, and back should walk that back.
    const again = pushAt(peeked, KIND.PEEK, 'PR-0002', 'projects')
    expect(again.at).toBe('record:INV-0007|peek:clients/CL-0003|peek:projects/PR-0002')
  })

  it('raises a peek it already has rather than opening a second', () => {
    // The same client's link pressed from two different invoices is one window
    // to the person looking at it, brought forward.
    const two = pushAt(
      pushAt({ at: 'record:INV-0007' }, KIND.PEEK, 'CL-0003', 'clients'),
      KIND.PEEK, 'PR-0002', 'projects',
    )
    const raised = pushAt(two, KIND.PEEK, 'CL-0003', 'clients')
    expect(raised.at).toBe('record:INV-0007|peek:projects/PR-0002|peek:clients/CL-0003')
  })

  it('closes the peek you named and leaves the ones under it', () => {
    const two = pushAt(
      pushAt({ at: 'record:INV-0007' }, KIND.PEEK, 'CL-0003', 'clients'),
      KIND.PEEK, 'PR-0002', 'projects',
    )
    expect(popAt(two, KIND.PEEK, 'PR-0002', 'projects').at)
      .toBe('record:INV-0007|peek:clients/CL-0003')
    // The one underneath, closed from its own tile.
    expect(popAt(two, KIND.PEEK, 'CL-0003', 'clients').at)
      .toBe('record:INV-0007|peek:projects/PR-0002')
    // And all of them, which is what leaving the surface does.
    expect(popAt(two, KIND.PEEK).at).toBe('record:INV-0007')
  })

  it('reads every peek open, outermost first', () => {
    const two = pushAt(
      pushAt({ at: 'record:INV-0007' }, KIND.PEEK, 'CL-0003', 'clients'),
      KIND.PEEK, 'PR-0002', 'projects',
    )
    expect(allAt(two, KIND.PEEK)).toEqual([
      { ref: 'CL-0003', screen: 'clients' },
      { ref: 'PR-0002', screen: 'projects' },
    ])
    // A record is not stackable, so this is `atOf` in a list of one.
    expect(allAt(two, KIND.RECORD)).toEqual([{ ref: 'INV-0007', screen: '' }])
  })

  it('drops the half it cannot read and keeps the rest', () => {
    expect(atOf({ at: 'nonsense:x|record:TASK-1' }, KIND.RECORD)).toBe('TASK-1')
  })

  it('keeps the rest of the URL', () => {
    // Dropping the query to open a record is how a saved view and a folder
    // get lost, so the whole thing goes in and the whole thing comes back.
    const query = { screen: 'tasks', layout: 'mine', at: 'record:OLD' }
    expect(withAt(query, KIND.RECORD, 'NEW')).toEqual({
      screen: 'tasks', layout: 'mine', at: 'record:NEW',
    })
    expect(withAt(query, null)).toEqual({ screen: 'tasks', layout: 'mine' })
  })
})
