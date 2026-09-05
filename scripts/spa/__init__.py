"""The SPA setup that is generated into both apps.

`scripts/gen_frontend.py` assembles what is here into files; this package holds
the content, one module per concern, layered so each may only import from the
ones above it:

  spec      what the two apps are — routes, brand, pinned versions
  ui        the component barrel every import goes through
  runtime   fetching, realtime, errors, notifications
  shell     the chrome: rail, bottom bar, account menu, usage
  screens   the libraries the shell's screens read
  build     Vite, Tailwind, PostCSS, package.json, ESLint
  browser   Playwright, and the screenshot command
  fields    every Frappe fieldtype, and what renders it

Nothing here writes to disk. That is `gen_frontend.render`, which is also the
one place that decides which files a bundle gets: `FILES` for all of them,
`SHELL_FILES` only for a bundle that declares `shell`.
"""
