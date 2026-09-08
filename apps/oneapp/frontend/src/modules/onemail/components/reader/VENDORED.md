# The message reader is Frappe's

Everything in this directory is taken from
[`frappe/mail`](https://github.com/frappe/mail) at `0690fd5`, which is
AGPL-3.0. So is this repository, which is what makes taking it allowed — and
the three obligations that come with it are not optional:

* the copyright notice stays,
* every file says at the top what it was derived from,
* nothing here moves to a permissive licence.

## Why this and not the rest

`frappe/mail` is a mail *server* product — Stalwart, JMAP, a mailbox per
tenant — and `docs/EMAIL.md` §3 explains at length why we are not adopting it.
That argument is about the server. It was never about the renderer.

Reading somebody else's mail means putting a stranger's HTML on a screen, and
there are exactly two things that must happen to it first. Neither is worth
hand-rolling, and we had hand-rolled both:

* **It must be sanitised.** We rendered `Communication.content` with `v-html`
  into a live div and relied on whatever Frappe scrubbed on the way in. The
  sender's own `<style>` block therefore applied to *our* application.
* **Remote assets must not load until asked.** Ours held them back with a
  regex over raw HTML — `/(<img\b[^>]*?\bsrc=)(["'])(https?:\/\/[^"']*)\2/gi`.
  Measured against six ordinary tracking-pixel shapes it held two and leaked
  four: `<img src = "…">` with spaces around the equals, `srcset`,
  `style="background:url(…)"`, and `<picture><source srcset>`. The banner said
  "hidden to protect your privacy" while a CSS background pixel loaded.

Theirs parses the document instead of pattern-matching it, covers `<img>`,
inline `[style]` *and* `<style>` blocks, and renders into a `srcdoc` iframe so
the email's CSS cannot reach us. That is the whole reason this is here.

## What is theirs, and what we changed

| File | Upstream |
|---|---|
| `EmailContent.vue` | `frontend/src/components/EmailContent.vue` |
| `assets.js` | `analyzeRemoteAssets` / `blockRemoteAssets` from `frontend/src/utils/index.ts` |

Four modifications, each because their app has something ours does not:

1. **TypeScript to JavaScript.** This repository has no `tsconfig.json` and no
   other `lang="ts"` file. Keeping one would mean configuring TypeScript for a
   single component.
2. **`__()` is gone.** Their global translation function is installed by an app
   bootstrap we do not have; the strings are inline. Nothing else changed about
   them.
3. **`useTheme` became a local resolve.** Ours is `lib/appearance.js` over
   frappe-ui's `useColorScheme`, which reports the *preference* — and
   `'system'` is not a colour. The iframe needs the resolved one, so this reads
   `data-theme` off `<html>` and falls back to `prefers-color-scheme`, which is
   the same contract the rest of our CSS follows.
4. **Icons and Button come from `@/ui`.** Our single sanctioned import path,
   enforced by eslint. Theirs imports `lucide-vue-next` directly.

The `trust` emit is kept and unwired. Their Screener decides whether a sender
is trusted; we have no such model, so the button is not rendered
(`can-trust` defaults false) and the emit is left in place so wiring it later
is one prop rather than a re-port.
