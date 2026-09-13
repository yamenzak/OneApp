# OneCode

The editor for a file whose content is its own bytes, and — from
`docs/UNIFICATION.md` §E9 — the rails a tenant-written application will run on.

Two halves. Today's half is an editor: make a `.py` or a `.js` or a `.yaml` in
the Drive and open it, coloured where CodeMirror has a pack for it and plain
where it does not. Tomorrow's half is a *project* — a folder of those files,
declaring a route and an engine, served as a page that knows who is looking at
it. The three modules beside this file are that second half's foundation, and
none of them runs anything: a project's code is bytes in the Drive, and this
app is not an execution environment.

Both halves are opened from the Drive. There is no OneCode space and no OneCode
route — a file belongs to the workspace's file table, not to any one Space, and
`Doc.vue` is the one address behind both editors. Which one opens is what the
file *is*.

## The model

**A file is a `File`.** The same row an attachment is, with the same versions,
the same sharing, the same bin and the same WebDAV mount. `onestorage`'s
sentence holds here too: there is no second store.

**A project is a folder with `onecode.json` in it.** Nothing else distinguishes
one. That buys versions, sharing, the bin, a VS Code mount over WebDAV, the
AI's existing file verbs and templates — all for free, and all of it would have
had to be rebuilt behind a `Project` doctype.

**A manifest is a declaration, never a script.** `manifest.py` reads six keys
and builds the page's context from them. The context is a function of the
declaration and the reader; the request contributes nothing.

**An engine is a line in the manifest.** `engines.py` maps a name to a pinned
import map served from our own host, so "buildless" is a property of the module
graph rather than a framework choice baked into a loader.

**A route is a claim, checked when it is saved.** `routes.py` refuses the
platform's own prefixes and any path that nests with another project's.

## The decisions that cost something

**`context_script` is not exposed, ever.** Frappe's `Web Page` carries a Python
field that runs with the framework in scope before the template renders. It is
precisely what a tenant app wants and precisely what a tenant may not have: a
tenant who can write server Python on their own site can write it on ours. The
cost is that everything a page needs must be declarable, which means a new
capability is a new key here rather than three lines a customer writes. That is
the trade, taken deliberately. `onestorage/linked.py` states the same doctrine
one layer in: *nothing here takes a doctype, a filter or a fieldname from the
caller.*

**The import map is ours, pinned, and complete.** Rejected: an import map
pointing at a public CDN, which is smaller, always current, and makes every
tenant page's integrity somebody else's operational decision — plus a CSP the
page could not otherwise need and an offline story that does not exist. The
version is in the filename so two projects on two versions are two files rather
than one file that changed under one of them.

**Collisions are checked at save time and on segments.** Rejected: checking at
request time, which discovers the problem on a page a customer has already
linked to. Rejected: `startswith`, which says `/shop` contains `/shopping` —
a claim refused for no reason — while segments say it does not and that
`/shop/admin` is the one that does collide.

**The editor is the shared `EditorChrome`, not its own bar.** It had its own for
a stage: a mark that was also the way out, a title input, a save state and four
buttons. Every one of those already existed in the component the document and
the workbook wear, and a copy of an editor's chrome is how a second editor gets
built without anybody deciding to build one. `tests/test_frontend_guards.py`
now parameterises over three.

**Markdown is a `Document` kind and still opens here.** `kinds.py` matches Code
last, so a `.md` and a `.txt` are Documents — what a kind answers is "show me
the drawings", and a person filtering for code does not mean the README. The
editor is the same one either way, because what somebody downloads has to be
the file they wrote: a markdown file round-tripped through ProseMirror comes
back reflowed and re-escaped and is no longer the thing anybody committed.

**`Code` is a Drive place although it is derived from a filename.** Every other
place in `PLACE_FOR` is a kind somebody *declares* by making it here. This one
is the exception because a project is a folder, and somebody looking for the
thing they are building is looking for a folder rather than for a kind.

## What is not built, in the order it blocks

1. **Serving.** The `Web Page` with the project's dynamic route, whose
   `context_script` is ours and calls `manifest.context()`, and whose head
   carries the `<script type="importmap">`. Everything below waits on it.
2. **The project surfaces.** Making a project (a folder and a manifest in one
   step), and reading `onecode.json` back into a form rather than editing JSON
   by hand.
3. **Assets from R2.** A project's non-code files served public or presigned,
   which `r2.public_url` already does for everything else.
4. **A project-scoped AI index.** `ai/verbs.js` and AI-4's retrieval already
   scope per record; a project is a folder and a folder is a scope.
5. **More than one level of file tree.** One level today, deliberately: a tree
   that recursed would be a second file manager growing beside the first.
