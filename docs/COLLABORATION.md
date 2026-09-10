# Two people in one file

The sheet and the document are the only surfaces in this product where two
people work on the same thing at the same moment. Everywhere else the framework
already answers it: a record is one form, one save, and `doc_viewers` says who
else has it open. A grid and a paragraph are different — the unit of work is
smaller than a save, and "somebody else changed this, reload" is not an answer
anybody would accept from a spreadsheet.

This is the map for that: what the transport is and why it costs nothing to
deploy, what converges and what does not, where a comment lives, and what a
stranger with a link may do.

---

## 1. The thing that changed the argument

`docs/SHEETS.md` §2 and `docs/WRITER.md` §3 both declined live editing, and
both gave the same reason: Frappe's collaboration is Yjs, Yjs needs a server
that speaks its protocol, and `frappe/sheets` ships that server as a **separate
Node process** — `collab-server/`, on `@hocuspocus/server` with Redis behind
it. A shard is one GIL-bound Python process and a second runtime is the thing
we keep declining to add.

That argument was about Hocuspocus, and it was right about Hocuspocus. It was
wrong about Yjs, because of one line in the framework:

```js
// frappe/realtime/index.js
let file = `../../${app}/realtime/handlers.js`;
```

**Frappe's socketio process loads a handler file from every installed app.**
The bench already runs that process — it is what carries `list_update`, and
`doc_viewers`, and every notification this product shows. It is already Node,
already authenticated per site, already permission-checked against the site's
own Python. Putting our handlers into it is a file, not a service.

So `apps/oneapp/realtime/handlers.js` is ours, running there. There is no
second runtime, nothing new for an operator to watch, and nothing new to
configure. `bench start` already starts it.

### What Frappe's own handlers do not have

A client may join a room and may not *speak* into one. Every message the
framework fans out originates in Python, on the Redis `events` channel. That is
right for `list_update` and wrong for a keystroke.

Frappe Sheets found this out. Its non-Hocuspocus transport publishes each Yjs
update through a whitelisted method (`sheets.api.yjs_relay`), which is an HTTP
POST into a Python worker per update. Their own comment records what happened:

> a split-text on 1100 rows × 5 columns produced ~5500 POSTs in a few seconds
> and Chrome returned `ERR_INSUFFICIENT_RESOURCES` (out of concurrent
> connection slots)

They fixed it by coalescing on a 16ms timer, which makes it survivable and does
not make it right — every keystroke still costs a round trip into the process
that is also serving the page.

Our relay adds the one primitive that was missing: a **client → room fan-out**,
in Node. A message goes browser → node → browsers. Python is asked exactly one
question, `oneapp.onespace.live.admit`, once per room per socket.

### What the relay refuses

Three, and each is the hole it would otherwise be.

**A client cannot name its room.** It names a *kind* and a record; `admit` maps
the pair and answers with the room. The relay joins the room the server named.
Without this it is an unauthenticated pub/sub bus over every row on the site.
There is one kind, `file`, and both editors use it — a sheet and a document are
both `File` rows.

**A reader cannot write.** The write flag comes back from `admit` and is kept in
the Node process, not on the client. Someone with read access to a shared sheet
watches other people's cursors and cannot move their cells.

**A message has a size and a rate.** 512KB and 240 messages per five seconds
per socket, across every room it is in. A fast typist is nowhere near either;
one socket holding the connection open and pushing is.

`src/shared/lib/live/relay.test.js` drives the handler with a fake socket and
holds all three. `tests/test_live_rooms.py` holds the permission check itself,
which is the only place a permission is actually decided.

---

## 2. What converges

Yjs, and taken from `frappe/sheets` rather than rewritten — `ydoc.js`,
`cells-binding.js` and `awareness.js` are theirs, AGPL, attributed at the top
of each file. What is ours is the transport underneath them, which is the part
that was expensive.

The shape they wrote is worth keeping because it is already right:

* **A Y.Doc per file.** Cells, formats and comments are `Y.Map`s keyed by
  sub-sheet then cell id. Two people typing in different cells both land; two
  people typing in the same cell converge on one value rather than one of them
  losing a save.
* **The engine stays the source of truth for computed state.** The Y.Doc holds
  raw values; formulas, the dependency graph and display values are the
  engine's, recomputed locally from what arrives. Nothing about the formula
  engine is on the wire.
* **Awareness is separate and volatile.** Cursors, selections and who is here
  are y-protocols' Awareness, which expires a silent peer rather than
  converging on them — a caret from a session that ended is not something to
  agree about. Frappe re-implemented the shape to avoid the dependency; we
  take it, because Tiptap's caret extension expects the real thing and two
  awareness implementations for two editors in one suite is drift.
* **What a state claims about *who* is discarded.** An awareness state is
  written by the client it describes, so a peer could put somebody else's
  name on their own caret. Every arriving frame is stamped with the user the
  relay admitted that socket as, and the name and colour come from the
  roster. A peer can lie about where its cursor is and about nothing else.
* **The stored form does not change.** The workbook is still one gzipped JSON
  blob in `Sheet Book.payload` and a document is still HTML on the `File`. The
  Y.Doc is in-memory conflict resolution and nothing else — there is no CRDT
  column, and nothing on our side that only a Yjs runtime can read. This is the
  second half of the original objection, and it is answered by not storing one.

---

## 3. Where each piece lives

| Path | What |
|---|---|
| `apps/oneapp/realtime/handlers.js` | The relay. Runs in Frappe's socketio process. |
| `apps/oneapp/realtime/package.json` | Pins that directory to CommonJS. The app's own says `type: module`, and `require()` cannot load an ES module — without this the process warns once and joins nobody to any room. |
| `oneapp/onespace/live.py` | `admit` and `presence`. The only permission check. |
| `src/shared/lib/live/room.js` | The browser end: join, publish, tell, leave, roster. |
| `src/modules/onesheet/lib/collab/` | The Yjs layer for the grid. `ydoc.js` and `cells-binding.js` vendored; `comments-binding.js` ours. |
| `src/modules/onedoc/lib/live.js` | The document's half: Tiptap's collaboration and carets over the same room. |
| `src/shared/components/PresenceStrip.vue` | Who else is here, in a header. |
| `src/shared/components/FileChat.vue` | The conversation about a file. |
| `oneapp/onestorage/chatting.py` | Where that conversation is stored, which is Frappe's `Comment`. |

---

## 4. The stages

1. **The relay.** Done. Handlers, `admit`, the room client, and the guards.
2. **The workbook.** Done. The `useCollaboration.js` seam the vendored editor
   already had, filled with Frappe's Yjs layer over our transport.
   `e2e/live.spec.js` is two browsers, two accounts and one file: a typed cell
   and a formula both cross, and the presence strip fills and empties.

   Two ordering hazards had to be closed and neither is obvious. **Seeding**:
   exactly one client fills the room, and the relay says which — Frappe lets
   every client hydrate its own doc and relies on the merge, which converges
   on identical content and does *not* converge on a deletion. And that one
   client must not seed before `get_sheet` has answered, or the workbook
   everybody gets is the empty grid it had at mount. **Reconciling**: a late
   joiner loaded the file from the server and may be a save behind, so a cell
   the room deleted is still in its engine and its next autosave would put it
   back for everybody. Once the room answers, the cells are the room's.
3. **The document.** Done. Tiptap's own collaboration extension and carets
   over the same relay, seeded the same way, with the stored document still
   the stored document.

   The grid could take Frappe's Yjs layer whole because a workbook is cells
   in a map. Prose is not, and rebuilding that would be rebuilding
   ProseMirror's — so this is `@tiptap/extension-collaboration` and
   `@tiptap/extension-collaboration-caret`, which is the same y-prosemirror
   underneath either way.

   Three things that had to be got right:

   * **The editor must not exist before the room has answered.** frappe-ui's
     `useEditor` decides collaboration mode from the extension list at
     construction; an editor built a tick early sets its own content and then
     has the room's merged on top of it, which is the same paragraph twice.
   * **The undo has to be Collaboration's**, scoped to what this person did,
     or pressing it takes back a colleague's sentence. Turning off the kit's
     leaves the toolbar asking `can().undo()` before the view has mounted and
     the plugin exists — a `TypeError` on every open, harmless and not
     something to leave lying there. `liveDocumentToolbar` asks it safely.
   * **`DocEditor` is keyed by the document.** It used to be reused across
     files, which was fine while an editor was a box with text in it and is
     not fine now: it is bound to one file's Y.Doc and one file's room.
4. **Comments and chat.** Done, in the two halves people actually ask for.

   **Notes on a cell converge.** The engine was Frappe's and already threaded,
   resolvable and `@`-able; what was missing is that a note added in one
   browser stayed there until the next reload. `lib/collab/comments-binding.js`
   is ours, and its shape is the one thing worth knowing: a thread is a
   `Y.Array` and a reply is an insert, not a value under a key. The obvious
   binding — the whole thread object under the cell id, the way a cell value
   is bound — is right for a cell, where the loser of a concurrent write typed
   something somebody immediately overwrote, and wrong for a thread, where the
   loser wrote a reply that simply vanishes.

   **A conversation about the file.** `onestorage/chatting.py` and
   `FileChat.vue`, in both editors. Frappe's `Comment` with a
   `reference_doctype` of `File`, and the deciding reason is the third one:
   `Comment.after_insert` calls `notify_mentions`, so an `@` in a note is a
   notification with a link back for nothing. The other two are that the
   storage and the permission rule already exist, and that a remark about a
   file then lands in the same feed as one about a record rather than in a
   second feed nobody checks.

   The gate is `read` both ways and deliberately asymmetric: somebody a
   workbook was shared with read-only is exactly the person with a question
   about it, so they may say something — and being able to *change* a workbook
   is not being able to delete what somebody said about it, so a note is only
   ever its author's to remove.

   One thing this needed underneath: `joinRoom` is reference counted. A chat
   panel and an editor in one tab want the same room, and a second join would
   take the `first` flag the document seeds itself from — so the document
   would come up empty and stay that way.

   **Not built:** a comment anchored to a *paragraph*. Frappe Writer's are a
   second Yjs document with a floating layer over the prose; ours would be a
   mark in the document — which converges for free now — plus a panel. It is a
   real feature and a later one.
5. **A link a stranger can edit through.** `File Link` is read-only today and
   serves bytes through `r2.serve`. Making it editable is the one piece here
   with a real security surface, and it is last for that reason.
