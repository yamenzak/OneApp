/**
 * Which records a workbook names.
 *
 * The half that has to be right before anything is fetched. `collect` reads
 * raw formula text, so the cases worth pinning are the ones where the text is
 * misleading: an argument that is a cell reference rather than a literal, a
 * one-argument call in a workbook that is not bound yet, and the same record
 * named from forty cells — which must be one ask, not forty.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/shared/lib/workspace', () => ({ workspace: { sheetRecordFields: vi.fn() } }))
vi.mock('@/modules/onesheet/lib/engine/formula', () => ({ setRecordResolver: vi.fn() }))

const { collect, forgetRecordFields, setOwnRecord } =
  await import('./recordFields')

beforeEach(() => forgetRecordFields())

function tabs(cells) {
  return { Sheet1: cells }
}

describe('collect', () => {
  it('reads the three-argument form', () => {
    const { asks } = collect(tabs({ A1: '=RECORD("Quotation", "Q-1", "grand_total")' }))
    expect(asks).toEqual([
      { doctype: 'Quotation', name: 'Q-1', fields: ['grand_total'] },
    ])
  })

  it('folds every mention of one record into a single ask', () => {
    // Forty cells naming the same quotation is one request, not forty.
    const { asks } = collect(tabs({
      A1: '=RECORD("Quotation", "Q-1", "grand_total")',
      A2: '=RECORD("Quotation", "Q-1", "party_name") & " Ltd"',
      A3: '=RECORD("Quotation", "Q-1", "grand_total") * 0.05',
    }))
    expect(asks).toHaveLength(1)
    expect(asks[0].fields.sort()).toEqual(['grand_total', 'party_name'])
  })

  it('means the sheet own record when only a field is named', () => {
    setOwnRecord({ doctype: 'Quotation', name: 'Q-9' })
    const { asks } = collect(tabs({ A1: '=RECORD("grand_total")' }))
    expect(asks).toEqual([
      { doctype: 'Quotation', name: 'Q-9', fields: ['grand_total'] },
    ])
  })

  it('asks for the binding when it does not know it yet', () => {
    const { asks, wantsOwn } = collect(tabs({ A1: '=RECORD("grand_total")' }))
    expect(asks).toEqual([])
    expect(wantsOwn).toBe(true)
  })

  it('does not treat a reference among the arguments as a field', () => {
    // `RECORD("Quotation", A1, "qty")` has two literals. Reading them by
    // count rather than by position would fetch a field called Quotation.
    const { asks, wantsOwn } = collect(tabs({ A1: '=RECORD("Quotation", A2, "qty")' }))
    expect(asks).toEqual([])
    expect(wantsOwn).toBe(false)
  })

  it('ignores a cell that is not a formula', () => {
    expect(collect(tabs({ A1: 'RECORD("grand_total")' })).asks).toEqual([])
  })

  it('finds a call nested inside a bigger formula', () => {
    setOwnRecord({ doctype: 'Quotation', name: 'Q-9' })
    const { asks } = collect(tabs({
      A1: '=IF(RECORD("grand_total") > 1000, "big", "small")',
    }))
    expect(asks[0].fields).toEqual(['grand_total'])
  })

  it('walks every tab', () => {
    const { asks } = collect({
      Sheet1: { A1: '=RECORD("Quotation", "Q-1", "grand_total")' },
      Working: { B2: '=RECORD("Item", "RUA-FAB", "rate")' },
    })
    expect(asks.map((one) => one.name).sort()).toEqual(['Q-1', 'RUA-FAB'])
  })

  it('answers nothing for a workbook with no formulas at all', () => {
    expect(collect(tabs({ A1: '12', B1: '=A1*2' })).asks).toEqual([])
  })
})
