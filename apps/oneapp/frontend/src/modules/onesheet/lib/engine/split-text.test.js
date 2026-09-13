// Copyright (c) Frappe Technologies Pvt. Ltd. and contributors.
// Vendored from frappe/sheets (3f9e37b5776f), frontend/src/engine/split-text.test.js, which is AGPL-3.0.
// OneSpace is AGPL-3.0 too and this file stays that way — see
// lib/VENDORED.md before editing or moving it.

import { describe, it, expect } from 'vitest'
import { parseRow, resolveSeparator } from '@/modules/onesheet/lib/engine/split-text.js'

describe('parseRow', () => {
	it('splits on a simple separator', () => {
		expect(parseRow('a,b,c', ',')).toEqual(['a', 'b', 'c'])
	})

	it('preserves quoted commas', () => {
		expect(parseRow('"a,b",c', ',')).toEqual(['a,b', 'c'])
	})

	it('handles escaped quotes inside a quoted field', () => {
		expect(parseRow('"He said ""hi""",ok', ',')).toEqual(['He said "hi"', 'ok'])
	})

	it('keeps empty tokens', () => {
		expect(parseRow('a,,b', ',')).toEqual(['a', '', 'b'])
	})

	it('returns a single token when separator is absent', () => {
		expect(parseRow('hello', ',')).toEqual(['hello'])
	})

	it('handles tab separator', () => {
		expect(parseRow('a\tb\tc', '\t')).toEqual(['a', 'b', 'c'])
	})

	it('returns input unchanged when separator is empty', () => {
		expect(parseRow('a,b,c', '')).toEqual(['a,b,c'])
	})

	it('handles null / undefined input safely', () => {
		expect(parseRow(null, ',')).toEqual([''])
		expect(parseRow(undefined, ',')).toEqual([''])
	})

	it('treats multi-char separators as plain string split (no CSV quoting)', () => {
		expect(parseRow('a||b||c', '||')).toEqual(['a', 'b', 'c'])
	})
})

// Upstream made `detectSeparator` private, so these five ask the same
// questions through `resolveSeparator(values, 'auto')` — which is the only
// caller it ever had, and the one the editor uses. The answers are the
// literal separators rather than their names, which is the other half of what
// went private.
describe('what auto picks', () => {
	const auto = (values) => resolveSeparator(values, 'auto')

	it('picks tab when present', () => {
		expect(auto(['a\tb', 'c\td'])).toBe('\t')
	})

	it('picks comma over space when both present', () => {
		expect(auto(['hello world,foo'])).toBe(',')
	})

	it('falls back to space when no other separator works', () => {
		expect(auto(['a b c'])).toBe(' ')
	})

	it('returns null when no separator produces a split', () => {
		expect(auto(['abc', 'def'])).toBeNull()
	})

	it('returns null on empty input', () => {
		expect(auto([])).toBeNull()
		expect(auto([''])).toBeNull()
	})
})

describe('resolveSeparator', () => {
	it('resolves a named key to its literal', () => {
		expect(resolveSeparator(['x'], 'comma')).toBe(',')
		expect(resolveSeparator(['x'], 'tab')).toBe('\t')
	})

	it('resolves auto by running detect', () => {
		expect(resolveSeparator(['a,b'], 'auto')).toBe(',')
	})

	it('returns null for auto when nothing matches', () => {
		expect(resolveSeparator(['abc'], 'auto')).toBeNull()
	})

	it('accepts a custom separator string', () => {
		expect(resolveSeparator(['x'], { kind: 'custom', value: '::' })).toBe('::')
	})

	it('returns null for empty custom value', () => {
		expect(resolveSeparator(['x'], { kind: 'custom', value: '' })).toBeNull()
	})
})

// `splitRange` went private and, unlike the detector, has no public door: the
// editor calls `parseRow` per row and works out its own width. So the three
// cases it held are asked of `parseRow` directly, including the widest-row
// arithmetic that was the only thing `splitRange` added.
describe('a column of rows, split', () => {
	const grid = (values, separator) => values.map((one) => parseRow(one, separator))
	const widest = (rows) => Math.max(...rows.map((one) => one.length))

	it('is a token grid whose width is the longest row', () => {
		const rows = grid(['a,b,c', 'd,e'], ',')
		expect(rows).toEqual([['a', 'b', 'c'], ['d', 'e']])
		expect(widest(rows)).toBe(3)
	})

	it('leaves the values alone when there is no separator', () => {
		const rows = grid(['hello', 'world'], null)
		expect(rows).toEqual([['hello'], ['world']])
		expect(widest(rows)).toBe(1)
	})

	it('keeps an empty cell as a row of one empty token', () => {
		const rows = grid(['a,b', '', 'c,d,e'], ',')
		expect(rows).toEqual([['a', 'b'], [''], ['c', 'd', 'e']])
		expect(widest(rows)).toBe(3)
	})
})
