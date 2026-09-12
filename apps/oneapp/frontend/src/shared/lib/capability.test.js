import { describe, expect, it } from 'vitest'

import { CAN, everything, offers } from './capability'

describe('a source declares what it can do', () => {
  it('tells the three states apart', () => {
    const can = offers({
      [CAN.SORT]: true,
      [CAN.FILTER]: 'A mount answers in the order the server chose.',
    })

    // Offered.
    expect(can.has(CAN.SORT)).toBe(true)
    expect(can.can(CAN.SORT)).toBe(true)
    expect(can.why(CAN.SORT)).toBe('')

    // Here, refused, and the reason is the point.
    expect(can.has(CAN.FILTER)).toBe(true)
    expect(can.can(CAN.FILTER)).toBe(false)
    expect(can.why(CAN.FILTER)).toMatch(/order the server chose/)

    // Not part of this surface at all: draw nothing.
    expect(can.has(CAN.GROUP)).toBe(false)
    expect(can.can(CAN.GROUP)).toBe(false)
    expect(can.why(CAN.GROUP)).toBe('')
  })

  it('names the refused ones, so a bar can say so once', () => {
    const can = offers({
      [CAN.SORT]: true,
      [CAN.COUNT]: 'A mount cannot count without walking every folder.',
      [CAN.PAGE]: 'And it cannot page what it has not counted.',
    })
    expect(can.refused()).toEqual([CAN.COUNT, CAN.PAGE])
  })

  it('refuses a capability nobody declared, rather than never offering it', () => {
    // §F1's second pattern: the rule is right and the scan has a hole. A
    // typo here used to be a control that silently never appeared.
    expect(() => offers({ sorting: true })).toThrow(/Unknown capability/)
  })

  it('gives the engine everything', () => {
    const can = everything()
    for (const one of Object.values(CAN)) expect(can.can(one)).toBe(true)
  })
})
