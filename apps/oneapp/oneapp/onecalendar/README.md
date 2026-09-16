# OneCalendar

The week somebody actually has is a quotation due on Tuesday, a site visit on
Wednesday and the review a colleague put in their diary — and no screen in this
product holds those three. OneCalendar is where they are one grid.

So it is a **merge first and a store second**, and that ordering is the whole
design. Almost everything on the grid already belongs somewhere else and says
where; the only rows this module writes are the ones with nowhere else to live.

---

## 1. The two sources

* **Every screen the reader can open that declares a calendar.** Resolved and
  filtered through the same path the screen's own calendar view uses, so a
  record absent from that screen is absent here for the same reason, and the
  permission argument is one argument rather than two.
* **The reader's own `Event` rows** — Frappe's core doctype, which is already
  what a workspace has for "a thing in somebody's diary". *Theirs* means owned
  by them or naming them as a participant: an events **screen** shows the
  workspace's events, and the diary shows yours.

Empty rather than fatal where a source cannot be read. One screen whose doctype
was revoked between the manifest and the query is not a reason to take
somebody's whole week away.

---

## 2. The layers

    diary   the merge, and the small store under it
    legal   what this module adds to the privacy notice

`diary` and not `calendar`, because a module called `calendar` inside a package
is one import away from shadowing the standard library's — the kind of bug that
surfaces three files later.

Browser, at `frontend/src/modules/onecalendar/`: the page (`Diary.vue`), the
rail of sources, the event dialog, and the desk window.

---

## 3. The decisions that cost something

### An entry keeps its own way home

A merged entry carries where it came from — `record` or `event` — and pressing
one does the thing that source means. A record goes to the screen it belongs
to, on its own space; an event of the reader's own opens for editing where it
is, because there is no screen behind it to go to. That is why the merge
carries a source at all rather than a flat list of titles and times.

### The days on screen are the query

`agenda(since, until)` takes the range the grid is drawing, the same pair the
screen-level calendar sends. A month assembled from whichever rows sorted first
has holes in it, and a diary with holes is worse than no diary.

### The window has no bar of its own

`docs/DESKTOP.md` stage 6: the diary opens on the desk, because checking
Tuesday against the quotation you are writing is the whole use of it. It keeps
nothing — no folder, no open item — so `lib/window.js` is an id and nothing
else, and its single verb teleports into the window's title bar rather than
drawing a second band under it.

Pressing an entry in the window still moves the page underneath. That is not an
oversight: a window over a quotation, and the entry that opens the *next*
quotation, is what a diary beside your work is for.

---

## 4. What is not built

1. **An outside calendar.** Nothing connects to Google or Exchange, and the
   privacy clause says so. Two-way sync is a module of its own, not a flag.
2. **Who else is in it.** The merge reads participants, because that is one of
   the two ways an `Event` is yours — but the dialog has four fields and none
   of them names anybody, so nothing in the product can put you in somebody
   else's event yet. A people picker, and then reminders, which are an alerts
   table. Neither is a field.
3. **Recurrence.** `Event` carries repeat fields that nothing here reads or
   writes, so a weekly stand-up is written weekly.
4. **Anything leaving the workspace.** No ICS out, no RSVP in, and no outside
   calendar to sync with — the privacy clause says as much.
