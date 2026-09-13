// Copyright (c) Frappe Technologies Pvt. Ltd. and contributors.
// Vendored from frappe/sheets (3f9e37b5776f), frontend/src/engine/patterns/alphabetic.test.js, which is AGPL-3.0.
// OneSpace is AGPL-3.0 too and this file stays that way — see
// lib/VENDORED.md before editing or moving it.

import { describe, it, expect } from 'vitest'
import { alphabeticDetector } from '@/modules/onesheet/lib/engine/patterns/alphabetic.js'

describe('alphabeticDetector', () => {
	it('continues uppercase single-letter sequence', () => {
		const r = alphabeticDetector.detect(['A', 'B'])
		expect(r.kind).toBe('alphabetic')
		expect(r.next(1)).toBe('C')
		expect(r.next(3)).toBe('E')
	})

	it('preserves lowercase', () => {
		const r = alphabeticDetector.detect(['a', 'b'])
		expect(r.next(1)).toBe('c')
	})

	it('wraps from Z to AA like a spreadsheet column label', () => {
		const r = alphabeticDetector.detect(['Y', 'Z'])
		expect(r.next(1)).toBe('AA')
		expect(r.next(2)).toBe('AB')
	})

	it('continues two-letter labels (AA, AB → AC)', () => {
		const r = alphabeticDetector.detect(['AA', 'AB'])
		expect(r.next(1)).toBe('AC')
	})

	it('handles step > 1', () => {
		const r = alphabeticDetector.detect(['A', 'C'])
		expect(r.next(1)).toBe('E')
		expect(r.next(2)).toBe('G')
	})

	it('single cell extends by +1', () => {
		const r = alphabeticDetector.detect(['M'])
		expect(r.next(1)).toBe('N')
		expect(r.next(5)).toBe('R')
	})

	it('backward direction decrements', () => {
		const r = alphabeticDetector.detect(['D', 'E'])
		expect(r.next(1, -1)).toBe('C')
		expect(r.next(3, -1)).toBe('A')
	})

	it('returns null for non-letter input', () => {
		expect(alphabeticDetector.detect(['A1', 'B1'])).toBeNull()
	})

	it('returns null when input is empty', () => {
		expect(alphabeticDetector.detect([])).toBeNull()
	})

	it('returns null when sequence is non-arithmetic', () => {
		expect(alphabeticDetector.detect(['A', 'C', 'F'])).toBeNull()
	})

	it('returns null when all values identical (caller copies)', () => {
		expect(alphabeticDetector.detect(['A', 'A'])).toBeNull()
	})
})

describe('the column convention it counts in', () => {
	// Upstream stopped exporting `_internal`, which these two used to reach
	// through. They are the same assertions from outside: `detect` on two
	// consecutive letters anchors on the last of them, so an offset *is* the
	// index, and the boundaries — Z→AA, AZ→BA — are where a wrong base-26
	// shows.
	const counting = () => alphabeticDetector.detect(['A', 'B'])

	it('matches Excel: A is 1, Z is 26, AA is 27', () => {
		const run = counting()
		expect(run.next(24)).toBe('Z')   // 2 + 24
		expect(run.next(25)).toBe('AA')  // 27, the carry
		expect(run.next(50)).toBe('AZ')  // 52
		expect(run.next(51)).toBe('BA')  // 53, the second carry
	})

	it('is a round trip', () => {
		const run = counting()
		// Every letter it produces, detected again, walks on from itself.
		for (const offset of [0, 11, 24, 25, 50, 51]) {
			const reached = run.next(offset)
			const again = alphabeticDetector.detect([reached])
			expect(again.next(1)).toBe(run.next(offset + 1))
		}
	})
})
