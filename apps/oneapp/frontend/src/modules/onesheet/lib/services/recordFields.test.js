/**
 * Which records a workbook names.
 *
 * The half that has to be right before anything is fetched. `collect` reads
 * raw formula text, so the cases worth pinning are the ones where the text is
 * misleading: an argument that is a cell reference rather than a literal, a
 * keyed call in a workbook whose sources are not known yet, and the same
 * record named from forty cells — which must be one ask, not forty.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/shared/lib/workspace', () => ({ workspace: { sheetRecordFields: vi.fn() } }))
vi.mock('@/modules/onesheet/lib/engine/formula', () => ({ setRecordResolver: vi.fn() }))

const { collect, forgetRecordFields, setSources } =
  await import('./recordFields')

//: What `binding.file_sources` sends back, trimmed to what this reads.
const sources = (...rows) =>
  rows.map(([key, doctype, name]) => ({
    key, reference_doctype: doctype, reference_name: name,
  }))

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

  it('means the first record when only a field is named', () => {
    setSources(sources(['record', 'Quotation', 'Q-9']))
    const { asks } = collect(tabs({ A1: '=RECORD("grand_total")' }))
    expect(asks).toEqual([
      { doctype: 'Quotation', name: 'Q-9', fields: ['grand_total'] },
    ])
  })

  it('reads the two-argument form as a source key', () => {
    // The whole reason a source has a key: two records, one workbook, and a
    // formula that says which without naming an id that could change.
    setSources(sources(
      ['record', 'Quotation', 'Q-9'],
      ['customer', 'Customer', 'Halloway'],
    ))
    const { asks } = collect(tabs({ A1: '=RECORD("customer", "credit_limit")' }))
    expect(asks).toEqual([
      { doctype: 'Customer', name: 'Halloway', fields: ['credit_limit'] },
    ])
  })

  it('sends the key itself when it does not know the sources yet', () => {
    const { asks, wantsSources } = collect(tabs({
      A1: '=RECORD("customer", "credit_limit")',
    }))
    expect(asks).toEqual([{ source: 'customer', fields: ['credit_limit'] }])
    expect(wantsSources).toBe(true)
  })

  it('answers nothing for a source that has no record yet', () => {
    // A template's slot. Not an error — nobody has started from it.
    setSources(sources(['record', 'Quotation', '']))
    expect(collect(tabs({ A1: '=RECORD("grand_total")' })).asks).toEqual([])
  })

  it('does not treat a reference among the arguments as a field', () => {
    // `RECORD("Quotation", A1, "qty")` has two literals. Reading them by
    // count rather than by position would fetch a field called Quotation.
    const { asks, wantsSources } = collect(tabs({ A1: '=RECORD("Quotation", A2, "qty")' }))
    expect(asks).toEqual([])
    expect(wantsSources).toBe(false)
  })

  it('ignores a cell that is not a formula', () => {
    expect(collect(tabs({ A1: 'RECORD("grand_total")' })).asks).toEqual([])
  })

  it('finds a call nested inside a bigger formula', () => {
    setSources(sources(['record', 'Quotation', 'Q-9']))
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
