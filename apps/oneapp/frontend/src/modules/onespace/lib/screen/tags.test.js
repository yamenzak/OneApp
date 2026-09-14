// A word drawn as a coloured badge, with the colour read out of the word.
//
// The property that matters is not which colour any particular word gets — it
// is that the answer is the same everywhere and always. A department coloured
// one way in the list and another in the grid would be worse than no colour.
import { describe, expect, it } from 'vitest'

import { EMPTY_THEME, TAG_THEMES, seed, tagTheme } from '@/modules/onespace/lib/screen/tags'

describe('tagTheme', () => {
  it('is the same colour for the same word, every time', () => {
    const first = tagTheme('Engineer')
    for (let go = 0; go < 50; go += 1) expect(tagTheme('Engineer')).toBe(first)
  })

  it('reads a word rather than how it was typed', () => {
    // Otherwise "Engineer" and "engineer " are one job in two colours, which is
    // the commonest way a tenant's own data arrives.
    expect(tagTheme('Engineer')).toBe(tagTheme('  engineer  '))
  })

  it('gives nothing the colour that means nothing', () => {
    // Gray is what an empty value draws as, so a real value that happened to
    // hash to it would be indistinguishable from a missing one.
    expect(tagTheme('')).toBe(EMPTY_THEME)
    expect(tagTheme(null)).toBe(EMPTY_THEME)
    expect(tagTheme(undefined)).toBe(EMPTY_THEME)
    expect(TAG_THEMES).not.toContain(EMPTY_THEME)
  })

  it('only ever answers with a theme a Badge has', () => {
    const words = ['Engineer', 'Designer', 'HR Manager', 'zzDelivery - ZZN', '✓', '1']
    for (const word of words) expect(TAG_THEMES).toContain(tagTheme(word))
  })

  it('spreads the words a real workspace has', () => {
    // The point of the colour is telling a few things apart, so a hash that
    // put a department list on one colour would be worth catching. Not a
    // distribution test — just that seven ordinary job titles are not all one.
    const jobs = ['Engineer', 'Designer', 'HR Manager', 'Accounts Manager',
      'Managing Director', 'Projects Manager', 'Business Development Manager']
    expect(new Set(jobs.map(tagTheme)).size).toBeGreaterThan(2)
  })
})

describe('seed', () => {
  it('stays inside 32 unsigned bits', () => {
    // Without the `>>> 0` after each step the multiply drifts into the float
    // range and two runs can disagree — which would be a colour that changes
    // between page loads.
    for (const word of ['', 'a', 'Engineer', 'x'.repeat(200)]) {
      const found = seed(word)
      expect(Number.isInteger(found)).toBe(true)
      expect(found).toBeGreaterThanOrEqual(0)
      expect(found).toBeLessThanOrEqual(0xffffffff)
    }
  })

  it('tells apart words that differ by one letter', () => {
    // Summing character codes puts "Designer" and "Desginer" in the same
    // bucket, and clusters every word of the same length.
    expect(seed('Designer')).not.toBe(seed('Desginer'))
  })
})
