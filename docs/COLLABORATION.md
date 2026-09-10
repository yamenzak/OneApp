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
  expire after 25 seconds of silence with an 8-second keep-alive, so a peer
  whose laptop shut mid-sentence stops being a face in the strip.
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
| `src/modules/onesheet/lib/collab/` | The Yjs layer for the grid. Vendored. |

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
3. **The document.** Tiptap's collaboration extension over the same relay, with
   the HTML still authoritative and the Y.Doc seeded by whichever browser the
   relay says joined an empty room.
4. **Comments and chat.** The sheet already has threaded, resolvable, per-cell
   comments; make them broadcast and make an `@` notify. The document has none.
   Both get one thread panel about the file itself.
5. **A link a stranger can edit through.** `File Link` is read-only today and
   serves bytes through `r2.serve`. Making it editable is the one piece here
   with a real security surface, and it is last for that reason.
