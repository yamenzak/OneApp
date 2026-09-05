// @vitest-environment happy-dom
//
// Ours, not Frappe's — the file it tests is vendored, this is the measurement
// that made us take it. See VENDORED.md.
//
// The reader used to hold remote images back with a regex over raw HTML:
//
//     /(<img\b[^>]*?\bsrc=)(["'])(https?:\/\/[^"']*)\2/gi
//
// Against the eight shapes below it held three and leaked five, while the
// banner above it said "hidden to protect your privacy". Every one of these is
// an ordinary tracking pixel, not a contrived bypass — `srcset` and a CSS
// background are what a marketing template emits by default.
import { describe, expect, it } from 'vitest'

import { analyzeRemoteAssets, blockRemoteAssets } from './assets'

/** Whether anything in the output would still fetch from `track`. */
function leaks(html) {
  return /(?:src|url\()\s*["'(]?(?:https?:)?\/\/track/i.test(html)
}

const REMOTE = {
  'a plain image': '<img src="http://track/a.gif">',
  'spaces around the equals': '<img src = "http://track/b.gif">',
  'uppercase across a newline': '<IMG\n SRC="http://track/c.gif">',
  'a CSS background': '<div style="background:url(http://track/e.gif)">x</div>',
  'a style block': '<style>.p{background:url(http://track/g.gif)}</style><p class="p">x</p>',
  'a protocol-relative src': '<img src="//track/h.gif">',
}

const LOCAL = {
  'an inline cid: image': '<img src="cid:logo@1">',
  'a data: URI': '<img src="data:image/gif;base64,R0lGOD">',
  'a file this site holds': '<img src="/private/files/plan.png">',
}

describe('what counts as remote', () => {
  it.each(Object.entries(REMOTE))('sees %s', (_name, html) => {
    expect(analyzeRemoteAssets(html).hasRemote).toBe(true)
  })

  it.each(Object.entries(LOCAL))('leaves %s alone', (_name, html) => {
    expect(analyzeRemoteAssets(html).hasRemote).toBe(false)
    expect(blockRemoteAssets(html)).toContain('img')
  })

  it('counts the images, because the banner says how many', () => {
    const two = '<img src="http://track/a.gif"><img src="https://track/b.gif">'
    expect(analyzeRemoteAssets(two).images).toBe(2)
  })

  it('reports a CSS-only tracker as remote with no images to count', () => {
    const seen = analyzeRemoteAssets('<div style="background:url(http://track/e.gif)"></div>')
    expect(seen).toEqual({ images: 0, hasRemote: true })
  })

  it('says nothing is remote in an empty body', () => {
    expect(analyzeRemoteAssets('')).toEqual({ images: 0, hasRemote: false })
    expect(analyzeRemoteAssets(undefined)).toEqual({ images: 0, hasRemote: false })
  })
})

describe('blocking', () => {
  it.each(Object.entries(REMOTE))('stops %s reaching the network', (_name, html) => {
    expect(leaks(blockRemoteAssets(html))).toBe(false)
  })

  it.each(Object.entries(LOCAL))('still loads %s', (_name, html) => {
    expect(blockRemoteAssets(html)).not.toContain('data-blocked-image')
  })

  it('keeps the URL so showing the images is a swap, not a refetch', () => {
    const out = blockRemoteAssets('<img src="http://track/a.gif">')
    expect(out).toContain('data-blocked-src="http://track/a.gif"')
    expect(out).toContain('data-blocked-image')
  })

  it('leaves the surrounding text alone', () => {
    const out = blockRemoteAssets('<p>Hello <b>there</b></p><img src="http://track/a.gif">')
    expect(out).toContain('Hello')
    expect(out).toContain('<b>there</b>')
  })
})
