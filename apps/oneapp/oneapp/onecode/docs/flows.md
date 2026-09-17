# Flows

## Opening a code file

1. Somebody presses a file in OneCloud. `onestorage/kinds.py` decides what it
   is; `languages.is_code` answers for this module by extension.
2. `Doc.vue` is the one address behind every editor. Which editor it mounts is
   what the file *is*, not which route was followed — there is no OneCode
   route and no OneCode space.
3. `languages.highlight_for` maps the extension to a CodeMirror pack.
   Unknown extensions open plain rather than refusing: a file you cannot open
   is worse than one without colours.

Markdown is the deliberate exception. `onestorage/kinds.py` matches Code
*last*, so `.md` and `.txt` are Documents — but the editor that opens is still
this one, because what somebody downloads has to be the bytes they wrote. A
markdown file round-tripped through ProseMirror comes back reflowed and
re-escaped.

## Declaring a project

1. A folder gains an `onecode.json`. Nothing else makes it a project.
2. `manifest.parse` reads it defensively — it is a file a person typed.
3. `manifest.validate` checks the six keys, then `routes.validate` normalises
   the route and refuses the platform's own prefixes.
4. `routes.check` compares the claim against every route already taken, by
   **segment**. `/shop` and `/shopping` do not collide; `/shop` and
   `/shop/admin` do. `startswith` would have said the opposite of both.
5. `engines.import_map` turns the engine name into a pinned map of module
   specifiers served from our own host.

## Building a page's context

`manifest.context(declared, reader)` is the whole of what a project gets, and
it is a **function of the declaration and the reader**. The request contributes
nothing. That is the rule that makes a declaration safe where a script is not:
a list the server checks against, rather than a list the server runs.

## What is not built

Serving. Everything above produces a validated manifest and an import map, and
nothing yet renders a page from them. The README's closing section is the
order the remaining work unblocks in.
