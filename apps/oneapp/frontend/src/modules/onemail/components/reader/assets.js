// Copyright (c) Frappe Technologies Pvt. Ltd. and contributors.
// Vendored from frappe/mail (0690fd5), frontend/src/utils/index.ts, which is
// AGPL-3.0. OneSpace is AGPL-3.0 too and this file stays that way — see
// components/mail/reader/VENDORED.md before editing or moving it.

const REMOTE_URL = /^\s*(?:https?:)?\/\//i
const REMOTE_CSS_URL = /url\(\s*['"]?(?:https?:)?\/\//i

export function analyzeRemoteAssets(html) {
  if (!html) return { images: 0, hasRemote: false }

  const doc = new DOMParser().parseFromString(html, 'text/html')

  const images = Array.from(doc.querySelectorAll('img')).filter((img) =>
    REMOTE_URL.test(img.getAttribute('src') || ''),
  ).length

  const hasRemoteCss =
    Array.from(doc.querySelectorAll('[style]')).some((el) =>
      REMOTE_CSS_URL.test(el.getAttribute('style') || ''),
    ) ||
    Array.from(doc.querySelectorAll('style')).some((el) =>
      REMOTE_CSS_URL.test(el.textContent || ''),
    )

  return { images, hasRemote: images > 0 || hasRemoteCss }
}

// Blank remote url(...) in a CSS string. Regex here is unavoidable — there's no DOM API to rewrite a
// url() inside a style string without pulling in the full CSSOM.
const blankRemoteCssUrls = (css) =>
  css.replace(/url\(\s*(['"]?)(?:https?:)?\/\/[^'")]*\1\s*\)/gi, 'url()')

// Neutralize remote assets so the browser never requests them. Parses the (already-sanitized) HTML into a
// DOM and edits it there — robust against markup/attribute quirks regex would trip on: each remote <img>
// has its src stashed on data-blocked-src (and is tagged for hiding), and remote url(...) in inline styles
// and <style> blocks is blanked. Inline (cid:) and data: assets are left to load as normal.
export function blockRemoteAssets(html) {
  const doc = new DOMParser().parseFromString(html, 'text/html')

  doc.querySelectorAll('img').forEach((img) => {
    const src = img.getAttribute('src') || ''
    if (!REMOTE_URL.test(src)) return
    img.setAttribute('data-blocked-src', src)
    img.removeAttribute('src')
    img.setAttribute('data-blocked-image', '')
  })

  doc.querySelectorAll('[style]').forEach((el) => {
    const style = el.getAttribute('style') || ''
    const cleaned = blankRemoteCssUrls(style)
    if (cleaned !== style) el.setAttribute('style', cleaned)
  })

  doc.querySelectorAll('style').forEach((styleEl) => {
    const css = styleEl.textContent || ''
    const cleaned = blankRemoteCssUrls(css)
    if (cleaned !== css) styleEl.textContent = cleaned
  })

  return doc.documentElement.outerHTML
}
