import { describe, expect, it, vi } from 'vitest'

import { applyPlan, cellsIn } from './aiPlan'

function harness() {
  const cells = {}
  return {
    cells,
    api: {
      setCell: vi.fn((id, value, tab) => { cells[`${tab}!${id}`] = value }),
      readCell: vi.fn((id, tab) => cells[`${tab}!${id}`]),
      pushEdit: vi.fn(),
      applyFormat: vi.fn(),
      addTab: vi.fn((name) => name),
      addNamedRange: vi.fn(),
    },
  }
}

describe('cellsIn', () => {
  it('walks a rectangle row-major', () => {
    expect(cellsIn('A1:B2')).toEqual(['A1', 'B1', 'A2', 'B2'])
  })

  it('takes a single cell', () => {
    expect(cellsIn('C7')).toEqual(['C7'])
  })

  it('does not care which corner came first', () => {
    expect(cellsIn('B2:A1')).toEqual(['A1', 'B1', 'A2', 'B2'])
  })

  it('crosses the Z boundary', () => {
    expect(cellsIn('Z1:AB1')).toEqual(['Z1', 'AA1', 'AB1'])
  })

  it('answers nothing for a reference that is not one', () => {
    expect(cellsIn('')).toEqual([])
    expect(cellsIn('nonsense')).toEqual([])
  })
})

describe('applyPlan', () => {
  it('anchors a rectangle of values at the reference', () => {
    const { api, cells } = harness()

    applyPlan([{
      op: 'set', tab: 'Costs', ref: 'B2',
      values: [['Total', 'Tax'], ['=C2*D2', '=B3*0.05']],
    }], api)

    expect(cells).toEqual({
      'Costs!B2': 'Total', 'Costs!C2': 'Tax',
      'Costs!B3': '=C2*D2', 'Costs!C3': '=B3*0.05',
    })
  })

  it('writes formulas rather than numbers, because the engine recomputes', () => {
    // The whole reason the answer is a plan: a value the server computed
    // stops being right the moment a cell it came from is edited.
    const { api, cells } = harness()
    applyPlan([{ op: 'set', tab: 'S', ref: 'A1', values: [['=SUM(B1:B9)']] }], api)
    expect(cells['S!A1']).toBe('=SUM(B1:B9)')
  })

  it('records one edit op per set, so one Undo takes the plan back', () => {
    const { api } = harness()
    applyPlan([{ op: 'set', tab: 'S', ref: 'A1', values: [['x']] }], api)

    expect(api.pushEdit).toHaveBeenCalledTimes(1)
    expect(api.pushEdit.mock.calls[0][0]).toBe('S')
    expect(api.pushEdit.mock.calls[0][2]).toBe('AI')
  })

  it('captures what was there before the writes, not after', () => {
    const { api, cells } = harness()
    cells['S!A1'] = 'old'

    applyPlan([{ op: 'set', tab: 'S', ref: 'A1', values: [['new']] }], api)

    // Keyed by the plain cell id, which is what `useEditOps` re-reads
    // against — not by the tab-qualified key this harness stores under.
    expect(api.pushEdit.mock.calls[0][1]).toEqual({ A1: 'old' })
  })

  it('applies a format over every cell of the range', () => {
    const { api } = harness()
    applyPlan([{
      op: 'format', tab: 'S', ref: 'D2:D4', style: { numberFormat: 'currency' },
    }], api)

    expect(api.applyFormat).toHaveBeenCalledWith(
      ['D2', 'D3', 'D4'], { numberFormat: 'currency' }, 'S',
    )
  })

  it('makes a tab and a named range', () => {
    const { api } = harness()
    applyPlan([
      { op: 'tab', name: 'Summary' },
      { op: 'name', label: 'Totals', tab: 'Summary', ref: 'A1:A9' },
    ], api)

    expect(api.addTab).toHaveBeenCalledWith('Summary')
    expect(api.addNamedRange).toHaveBeenCalledWith('Totals', 'Summary', 'A1:A9')
  })

  it('says what it wrote and where', () => {
    const { api } = harness()
    const done = applyPlan([
      { op: 'tab', name: 'Summary' },
      { op: 'set', tab: 'Summary', ref: 'A1', values: [['a', 'b']] },
    ], api)

    expect(done.written).toBe(2)
    expect(done.tabs).toEqual(['Summary'])
    expect(done.touched).toEqual(['Summary!A1', 'Summary!B1'])
  })

  it('does nothing with an empty plan', () => {
    const { api } = harness()
    expect(applyPlan([], api).written).toBe(0)
    expect(api.setCell).not.toHaveBeenCalled()
  })

  it('skips an operation the grid was not given a way to do', () => {
    // `addNamedRange` is optional — an editor without one still applies the
    // cells rather than throwing half-way through the plan.
    const { api } = harness()
    delete api.addNamedRange

    applyPlan([
      { op: 'name', label: 'X', tab: 'S', ref: 'A1' },
      { op: 'set', tab: 'S', ref: 'A1', values: [['x']] },
    ], api)

    expect(api.setCell).toHaveBeenCalled()
  })
})
